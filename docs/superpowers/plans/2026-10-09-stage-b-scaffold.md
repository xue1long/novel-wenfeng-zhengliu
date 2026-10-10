# 阶段 B 实施计划：来源处理与私有运行骨架

> 历史计划（2026-10-09）：本计划记录初次实现时的入口授权与目录策略。现行规则以 `docs/superpowers/specs/2026-10-09-wenfeng-skill-design.md` §4.1 和根目录 `SKILL.md` 为准：保留模型处理同意，私有派生用途默认 `private_only`，run root 默认落在根目录 `out/<run-id>/`。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不调用任何模型、不动 `wenfeng-distill` 入口行为的前提下，把**来源处理与私有 run 骨架**完整落地：授权前置校验 → 来源指纹与规范化 → 稳定分块 → 抽样覆盖矩阵 → 预锁留出 → run journal + 幂等续跑 → 语义扫描预算预估与窗口清单。所有产物以阶段 A 已冻结的 schema 为契约，并能经 `check_stage_a.py` 与本阶段自建的 `check_stage_b.py` 同时通过。

**Architecture:** 薄本地 CLI（纯 Python 标准库；不调模型；只读产物以 stage A 的 vendored JSON Schema 校验 + 阶段 A 引入的 `state_machine.py` / `invalidation_rules.py` 为门禁）。所有写操作必须落入**用户指定的私有 run root**，绝不写入项目目录；CLI 只接受一次显式 `--run-root` 参数，对路径做 containment 校验。

**Tech Stack:** Python 3 标准库（hashlib / pathlib / json / re / unicodedata）、阶段 A 的 `vendor/json_schema_validate.py`、`scripts/state_machine.py`、`scripts/invalidation_rules.py`、`scripts/check_policy_gate.py`。

**Spec anchors:** §4.1（私有运行目录与清单）、§4.2（抽样与留出）、§6 阶段 B 验收原文。

## Global Constraints

- **绝不**复制、提交、输出**任何**真实来源正文、留出集、证据摘录、书名、作者名、人物名、独创意象。所有测试夹具使用公开虚构文本（合成短章 + 合成短句）。
- **绝不**调用任何模型；本阶段所有脚本都不引入网络 IO 与 HTTP 客户端。
- **绝不**新增运行时依赖；只能使用 Python 3 标准库 + 阶段 A 已落地的 `vendor/`、`scripts/`。
- **绝不**自动写用户级目录；任何 `--run-root` 必须经路径 containment 校验，且目标路径不存在时才创建；存在时要求 `--resume` 或 `--confirm-overwrite`。
- 不动 `SKILL.md` 的"运行流程"7 步；只在末尾追加阶段状态注释。
- 每个工具必须能 `--self-check`（CLI 自检）跑通并打印 PASS/FAIL；本阶段不引入新的单元测试入口协议。
- 所有产物必须用阶段 A 已冻结的 schema（`source-manifest` / `chunk-manifest` / `run-manifest`）校验通过；跨文件引用由 `scripts/check_bundle_cross_refs.py` 处理。

## Review Focus

- 相同来源 + 相同 `parser_version` 必须生成稳定 `source_id` / `chunk_id` / 字符偏移；连续两次运行差异只有 `created_at` / `last_resumed_at`。
- 来源指纹或 `normalizer_version` / `chunker_version` 任一变化 → `scripts/invalidation_rules.py` 必须报告 `sampling` / `holdout` / `extraction` 下游全部失效。
- 授权缺失或 `model_processing` 不覆盖声明的模型 → CLI 拒绝继续，且不创建任何 `run_root` 子目录或文件（除 `--dry-run` 报告）。
- 扫描预算窗口清单必须解释**每一项**预算数字如何推导；缺任一项的来源字段时 CLI 必须报错并列出缺失字段。
- 留出集**必须**在分块后、写候选前完成封存；任何未封存留出集的产物不得进入 `extract/`。
- 步骤日志必须支持基于 `(run_id, step_id)` 的幂等续跑：同一 step 第二次调用不得重复写输出；`retry_count` 上限 3。
- 私有运行根路径必须经 `pathlib.Path.resolve()` 后做 containment 校验；任何 `..` / 符号链接逃逸必须被拒绝。
- 任何工具失败必须记录 `error_type` 与错误位置；不静默跳过。

### Task 1: 私有 run 根与路径 containment

**Files:**
- Create: `scripts/path_safety.py`
- Create: `tests/test_path_safety.py`

**接口契约：**
- `assert_within_run_root(run_root: Path, target: Path) -> None`：抛 `PathEscapeError` 当 `target.resolve()` 不在 `run_root.resolve()` 之内。
- `assert_no_symlink_escape(path: Path) -> None`：沿父链检查每个组件是真实目录且不是符号链接；遇 symlink 抛 `PathEscapeError`。
- `safe_mkdir(path: Path) -> None`：先做 containment + symlink 检查，再 `mkdir(parents=True, exist_ok=False)`；目标已存在抛 `PathExistsError`。

- [x] 写 6 个非法样例单测：`target = run_root/../etc/passwd` 拒绝、target 是 symlink 拒绝、target 已存在拒绝、target 解析后跨越盘符拒绝、target 含 NUL 字符拒绝、target 解析失败（不存在且父链含 symlink）拒绝。
- [x] 写 4 个合法样例单测：run_root 下的子目录、run_root 下的深嵌套子目录、run_root 本身、run_root 下以 `.` 开头的隐藏目录。
- [x] 先确认所有用例失败（文件尚不存在）；再实现 `path_safety.py`；再跑单测确认全过。

### Task 2: 来源指纹与规范化

**Files:**
- Create: `scripts/source_fingerprint.py`
- Create: `tests/test_source_fingerprint.py`

**接口契约：**
- `normalize(text: str, *, normalizer_version: str = "v1") -> str`：v1 规则为（**只**在阶段 B 锁定，未来变动必须升 version）：统一 `\r\n` → `\n`；剥离 BOM；剥离零宽空格 `\u200b`–`\u200d` 与 `\ufeff`；删除尾部空白；保留所有其他字符（含标点、章节标题、emoji）。
- `fingerprint_bytes(data: bytes, *, encoding: str = "utf-8") -> str`：返回 SHA-256 hex 64。
- `fingerprint_text(text: str, *, normalizer_version: str = "v1") -> str`：先 normalize 再 UTF-8 编码再 SHA-256。
- `ParserVersion`：常量 `"wenfeng-prepare-source/0.1.0"`（与 stage A example 对齐）。

- [x] 写 4 个非法 / 边界单测：BOM-only 输入的 fingerprint 等同于无 BOM；CRLF vs LF 同指纹；trailing whitespace 不影响指纹；零宽空格被剥离。
- [x] 写 2 个合法单测：纯 ASCII 段与含 CJK + emoji 的段各自产生稳定的 64 位 hex。
- [x] 写"normalizer_version 变化则 fingerprint 必变化"反向断言：用 `v1` 与 `v1+no_bom_strip` 算同一文本的 hash 必须不同。
- [x] 跑通。

### Task 3: 稳定分块器（章节 → 场景 → 窗口）

**Files:**
- Create: `scripts/chunker.py`
- Create: `tests/test_chunker.py`

**接口契约：**
- `Chunker(normalizer_version, chunker_version) -> ChunkManifestBuilder`。
- 输入：已规范化的文本（来自 `source_fingerprint.normalize`）。
- 切分规则（**只**在阶段 B 锁定）：
  1. 章节切分：识别 `^第[一二三四五六七八九十百千万零〇两\d]+章[\s\S]*$` 与 `^Chapter\s+\d+[\s\S]*$` 与 `^#\s+.+$`（Markdown 标题）三组正则，**先到先得**；无匹配则整篇视为单一虚拟章节 `C000`。
  2. 场景切分：每章内按"硬转场"标记切——空行 ≥ 2、时间地点指示词（中英文双限定词集合各 8 个；阶段 B 锁定的固定词表）、章节起始；保留 scene_id 形如 `SC0001`。
  3. 窗口切分：每个 scene 内按 ≤ 5000 个 Unicode 码点切；不得在句中截断——句子边界正则 `(?<=[。！？!?…\.])\s+`；无句末标点则取最近的硬换行；仍无法定位则报 `boundary_confidence=low` 并整 scene 作为一个 window。
  4. `chunk_id = "{scene_id}-{window_index:03d}"`，全文档唯一。
  5. `char_offset` 必须满足阶段 A 的 `x-wenfengRange=open` 契约。
- 输出：`chunks: list[ChunkRecord]`，每条含 `chunk_id`、`chapter_id`、`scene_id`、`char_offset`、`window_hash`、`boundary_confidence`、`text`（**仅留在内存，不写入 manifest**；manifest 仅写哈希与定位）。

- [x] 写 5 个非法 / 边界单测：5001 码点的句末不切分（必须有句号位置）、单章单 scene 单 window、跨章节的 chunk_id 唯一、Markdown 标题切分、超长章节 ≥ 5000 码点按句号切分。
- [x] 写"同输入同版本 → 同 chunk 列表"幂等单测：连续两次 `chunk(normalized)` 输出必须完全一致（含 chunk_id / char_offset / window_hash / boundary_confidence）。
- [x] 写"改版本 → 不同 chunk 列表"反向断言。
- [x] 跑通。

### Task 4: 抽样覆盖矩阵 + 预锁留出

**Files:**
- Create: `scripts/sampling.py`
- Create: `scripts/holdout.py`
- Create: `tests/test_sampling.py`
- Create: `tests/test_holdout.py`

**接口契约：**
- `SamplingStrategy`：7 类场景枚举（`opening` / `character_intro` / `daily` / `dialogue` / `conflict_climax` / `reveal` / `chapter_end`）× 3 段位置（`front` / `middle` / `end`）；阶段 B 锁定覆盖矩阵为至少 7×3 = 21 个目标，**每行 1 个可空缺**，缺则记 `uncovered`。
- `sample_by_strategy(chunks, strategy) -> dict[str, list[chunk_id]]`：先按 chunk 的 scene 元数据（阶段 B 仅按位置 front/middle/end 与场景标签）筛；标签未标则按 `chunk_id` 字典序兜底；返回每类 1 个 chunk_id。
- `CoverageMatrix`：JSON 可序列化；含每类的 chunk_id 与 front/middle/end 覆盖布尔。
- `lock_holdout(coverage_matrix, *, holdout_fraction=0.20, seed=...) -> HoldoutManifest`：从 non-front / non-end 的"中段"chunk 选 20% 封存；返回 manifest 含 `holdout_chunk_ids` 与 `holdout_locked_at`；**封存哈希必须落盘**，以便后续阶段校验。
- `HoldoutManifest` schema：`holdout_version`、`run_id`、`fingerprint`、`normalizer_version`、`chunker_version`、`holdout_chunk_ids[]`、`holdout_locked_at`、`holdout_lock_hash`。

- [x] 写 5 个抽样单测：7×3 覆盖矩阵完整生成、未覆盖的 chunk 记 `uncovered`、front/middle/end 三段各有至少 1 个、同一 chunk_id 不可在不同类重复出现（边界冲突）、seed 改变但输入不变 → 同输出。
- [x] 写 4 个留出单测：留出集全在中段、留出占比 20% ± 1 个、`holdout_lock_hash` 同输入同 seed 稳定、`chunker_version` 变化 → `holdout_lock_hash` 必变。
- [x] 跑通。

### Task 5: 授权前置校验

**Files:**
- Create: `scripts/authorization_gate.py`
- Create: `tests/test_authorization_gate.py`

**接口契约：**
- `check_authorization(authorization: dict, *, requested_model_id: str, requested_purpose: str) -> list[str]`：
  - `authorization.scope.model_processing ∈ {local_only, hosted_with_consent, hosted_only}`；`authorization.scope.derivative_use ∈ {private_only, shareable_with_attribution, shareable_anonymous}`；`authorization.evidence_basis ∈ {user_declaration, license_file, publisher_grant}`。
  - `requested_model_id == "local"` 时必须 `model_processing ∈ {local_only, hosted_with_consent}`。
  - `requested_model_id` 为 hosted 模型时必须 `model_processing ∈ {hosted_with_consent, hosted_only}`。
  - `requested_purpose == "shareable_anonymous"` 时必须 `derivative_use ∈ {shareable_anonymous, shareable_with_attribution}`。
  - 任一不满足 → 返回具体错误 + 字段路径；返回空列表代表通过。
- 集成入口：`assert_authorized_or_block(...)`：若有错则向 `run-manifest.step_log` 写一条 `authorization_missing` 事件并抛 `AuthorizationBlocked`。
- **不**自动启动 run root 创建；只在 CLI 显式调 `init-run` 后才落盘。

- [x] 写 5 个非法单测：缺 `model_processing`、缺 `derivative_use`、model_id=hosted 但 scope=local_only、purpose=shareable 但 derivative_use=private_only、空字典。
- [x] 写 3 个合法单测：local model + private_only、hosted_with_consent + shareable_anonymous、hosted_only + shareable_with_attribution。
- [x] 跑通。

### Task 6: run journal + 幂等续跑

**Files:**
- Create: `scripts/run_journal.py`
- Create: `tests/test_run_journal.py`

**接口契约：**
- `RunJournal(run_root: Path, run_id: str, *, source_fingerprint: str)`：构造时落盘 `run-manifest.example.json` 等价的真实 manifest（含 `step_log: []`、`status="incomplete"`、`scan_budget` 从 `model-budget-policy.json` 解析的 profile 拷贝）。
- `record_step(step_id, *, input_hash, prompt_template_version, model_id, output_path, output_hash, status, retry_count=0, error_type="")`：幂等——若 `step_id` 已存在则更新对应记录而不新增；写入后立刻 fsync 一次。
- `record_end_step(step_id, ..., status, output_hash, error_type="")`：专用于完成态；`retry_count` 必须 `<= 3`，否则抛 `StepRetryExhausted`。
- `load_step(step_id) -> StepRecord | None`：从磁盘读取。
- `set_status(status: str)`：仅允许 `incomplete / blocked / limited / ready`；与 `state_machine.transition()` 集成。

- [x] 写 5 个单测：首次写 step、同一 step 重复写不增行（计数 == 1）、retry_count=4 抛错、`set_status` 拒绝非法状态、磁盘重启后再次 `record_step` 仍幂等。
- [x] 写"未先 lock 留出集时 step `extract-*` 不可记录"反向断言：留出集未封存时调 `record_step("extract-narrative-voice", ...)` 必须抛 `HoldoutNotLockedError`。
- [x] 跑通。

### Task 7: 语义扫描预算预估 + 窗口清单

**Files:**
- Create: `scripts/scan_budget.py`
- Create: `tests/test_scan_budget.py`

**接口契约：**
- `estimate_scan_budget(chunks: list, policy: dict) -> ScanBudgetPlan`：
  - 输入阶段 A 锁定的 `content-scan-policy.json` 与 chunk 列表。
  - 估算：`estimated_requests = ceil(total_codepoints / batch_window_codepoints)`（默认 batch window 800，与阶段 A 的 `model-budget-policy` 默认值一致）；`estimated_input_tokens_total` 由 `total_codepoints` 按 1 token ≈ 4 字符估算（仅解释性估算，不是合同数值）；`estimated_tokens_per_batch` 直接复用 profile；`overlimit_policy` 从 policy 透传。
  - **缺任一来源字段**（如 chunk 缺 `chunk_id`、policy 缺 `policy_version`）→ 抛 `ScanBudgetIncompleteError`，列出缺失字段。
  - 返回 `ScanBudgetPlan` 含字段：`policy_version` / `fingerprint` / `chunker_version` / `windows: list[WindowPlan]` / `aggregate: AggregatePlan`。
  - `WindowPlan` 含 `window_id` / `chunk_id` / `estimated_codepoints` / `estimated_tokens`。
- `write_window_manifest(plan, run_root)`：落盘 `private:scan-budget-plan.json`（**写**到 run root 而非项目目录；schema 与 `run-manifest.scan_budget` 对齐）。
- `resume_windows(plan, completed_ids) -> list[WindowPlan]`：返回 `completed_ids` 之外的窗口，便于续跑。

- [x] 写 5 个单测：估计缺字段报错、estimated_requests 单调性（codepoints 增 → 请求增）、completed_ids 全在 → resume 返回空、completed_ids 空 → resume 返回全窗口、WindowPlan 字段齐全。
- [x] 写"可解释"反向断言：plan 的每个字段都必须能从输入推导——单测断言 `aggregate` 的每个数字都能从 `chunks` 与 `policy_version` 直接算出，不允许魔法数。
- [x] 跑通。

### Task 8: 薄 CLI（`prepare-source` / `init-run` / `resume-run`）

**Files:**
- Create: `scripts/cli.py`（仅 `prepare-source` / `init-run` / `resume-run` 三个子命令）
- Create: `tests/test_cli_prepare_source.py`
- Create: `tests/test_cli_init_run.py`
- Create: `tests/test_cli_resume_run.py`

**接口契约（与 spec §4.7 的薄 CLI 边界一致）：**
- `python scripts/cli.py prepare-source --source <path> --normalizer-version v1 --chunker-version v1 --out <run_root>`：只做 fingerprint + 规范化 + 分块；输出 `private:source-manifest.json` / `private:chunk-manifest.json`；不调模型、不创建 release 产物。
- `python scripts/cli.py init-run --run-root <path> --authorization <auth.json> --requested-model-id <id> --requested-purpose <shareable_anonymous|shareable_with_attribution|private_only> [--dry-run]`：先做授权前置校验；通过则创建 run root 与 `run-manifest.json`；不通过则不创建任何目录。
- `python scripts/cli.py resume-run --run-root <path> --step-id <id> --retry-count <n>`：幂等续跑；`retry_count > 3` 报错。

- [x] 写 4 个 `prepare-source` 单测：合法源 → 落盘 manifest、缺源文件 → 退出码 2、`--run-root` 不存在父链 → 退出码 2、源文本里 CRLF/BOM 被规范化。
- [x] 写 5 个 `init-run` 单测：缺授权字段 → 不创建 run root、授权通过 → 创建并写入 `run-manifest.json`、授权不覆盖 model_id → 退出码 1、dry-run 不创建任何目录、已存在 run_root 拒绝。
- [x] 写 4 个 `resume-run` 单测：已知 step 二次调用幂等、`retry_count=4` 报错、未知 step_id 可记录、`--run-root` 不存在 → 退出码 2。
- [x] 跑通。

### Task 9: 阶段 B 聚合验收门 + 报告

**Files:**
- Create: `scripts/check_stage_b.py`
- Create: `tests/test_stage_b_gates.py`

**接口契约：**
- `check_stage_b.py` 跑通：所有阶段 B 单测全过 + 阶段 A 聚合门不退化 + 端到端合成 run 在 `--dry-run` 下走完 fingerprint → 规范化 → 分块 → 抽样 → 留出锁 → budget plan → init-run 链。
- 输出："Stage B aggregate gate PASSED" 或 "FAILED" 列表；退出码 0/1/2。
- 在 `docs/superpowers/reports/stage-b-YYYYMMDD.txt` 留报告。

- [x] 写合成端到端 run 测试：从 7 章合成 TXT（含 BOM+CRLF）走完 B 的整条链。
- [x] 写"阶段 A 聚合门不退化"测试：先跑 `check_stage_a.py` 必须退出码 0。
- [x] 写"run root 路径逃逸被拒"端到端测试（实际改为 NUL 字符 + parent 不存在 + run_root 已存在三种显式拒绝）。
- [x] 跑通。

### Task 10: 阶段 B 状态与交付说明

**Files:**
- Modify: `docs/superpowers/specs/2026-10-09-wenfeng-skill-design.md`（追加"阶段 B 完成报告"段）
- Modify: `README.md`（追加"阶段 B 已交付"段）
- Modify: `SKILL.md`（末尾追加阶段状态注释，不改 7 步运行流程）

- [x] 列出本阶段交付的脚本、产物与各自路径；明确**本阶段不声称效果已验证、不声称可分享**。
- [x] README 同上。
- [x] SKILL.md 末尾追加阶段状态注释。
- [x] 跑一次 `python scripts/check_stage_b.py` 把输出保存为 `docs/superpowers/reports/stage-b-YYYYMMDD.txt`。

## Rulings

- **Ruling-1 (T0 锁定):** `vendor/json_schema_validate.py` + `scripts/state_machine.py` + `scripts/invalidation_rules.py` + `scripts/check_policy_gate.py` + `scripts/check_bundle_cross_refs.py` 是阶段 B 唯一可复用的阶段 A 资产；**不**允许在阶段 B 内修改其字段集合或语义。
- **Ruling-2 (T0 锁定):** 阶段 B 引入的所有新脚本**只**能调用阶段 A 已落地的工具；阶段 B 内部不写共享状态——任何落盘产物只写 `--run-root` 之下。
- **Ruling-3 (T3 锁定):** 场景标签的 8 中/8 英时间地点指示词由阶段 B 在 `scripts/chunker.py` 顶部以常量方式固定；后续需要扩展必须升 `chunker_version`。
- **Ruling-4 (T7 锁定):** "可解释"具体落实为 `aggregate` 字段每个数字都能由 `(chunks, policy_version)` 推导；估算常数（如 token-per-char）以常量形式固定在 `scripts/scan_budget.py` 顶部，可改但需伴随 `policy_version` 变更。
- **Ruling-5:** 阶段 B 不引入 `--self-check` 内嵌分支；`check_stage_b.py` 是唯一聚合门，单测是唯一自检入口。
- **Ruling-6:** 任何工具失败必须把 `error_type` 写入 `run-manifest.step_log` 的对应 step，便于阶段 D–G 排查；阶段 B 不替用户决策。
