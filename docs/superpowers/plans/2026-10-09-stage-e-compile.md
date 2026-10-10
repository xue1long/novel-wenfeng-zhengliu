# 阶段 E 实施计划：确定性编译与预检

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不调用任何模型、不动 `wenfeng-distill` 入口行为的前提下，把**确定性编译器 + 字面预检 + 路径安全 + 并发锁**完整落地。**六个 Skill 目录** + 一个 `compile-manifest.json` 在私有 staging 目录中产出；任何硬门失败必须留 staging 但不写 manifest，使下游无法引用。所有产物用阶段 A 已冻结的 schema（`compile-manifest`）校验，并能经 `check_stage_a..d.py` 与 `check_stage_e.py` 同时通过。

**Architecture:** 薄本地 CLI（纯 Python 标准库）。新 CLI 子集放在 `scripts/cli_compile.py`，不动 `scripts/cli.py` 与 `scripts/cli_extract.py`。所有写操作只发生在用户传入的 `--staging-root` 之下，且经 `scripts/path_safety.py` 的 containment + symlink 逃逸阻断。`scripts/deterministic_compiler.py` 负责"同输入 → 同字节"（固定排序、UTF-8、LF、无生成时间字段、staging 内部文件按路径排序）。`scripts/preflight.py` 负责静态预检：frontmatter / UTF-8 / 链接 / 资源 containment / 未声明文件 / 二进制 / 符号链接逃逸 / 名称与 stage_id 对应。`scripts/literal_scan.py` 负责字面预检（与阶段 G 的内容扫描同源，但阶段 E 的字面预检**只**对冻结输出做精确命中 + 长度匹配）。`scripts/concurrency_lock.py` 提供进程间文件锁。

**Tech Stack:** Python 3 标准库（hashlib / pathlib / json / re / zipfile / tempfile / fcntl 或 msvcrt 锁）。阶段 A 的 `vendor/json_schema_validate.py` + 13 个 schema、阶段 B 的 `path_safety.py` / `source_fingerprint.py`、阶段 C 的 `bundle_compiler.py` / `mechanism_merger.py` / `evidence_validator.py`、阶段 D 的 `skill_template.py` / `six_stage_contract.py` / `six_stage_state_machine.py` / `stage_context_validator.py` / `template_contract_checker.py`、`scripts/state_machine.py` / `invalidation_rules.py`。

**Spec anchors:** §4.7（薄 CLI 与确定性编译器）、§6 阶段 E 验收原文。

## Global Constraints

- **绝不**调用任何模型；模型侧执行仍由 `wenfeng-distill` 工厂 Skill 完成；本地脚本只验证模板 + 契约 + 确定性。
- **绝不**复制、提交、输出**任何**真实来源正文、留出集、证据摘录、书名、作者名、人物名。所有测试夹具使用公开虚构文本。
- **绝不**新增运行时依赖；只能使用 Python 3 标准库 + 阶段 A/B/C/D 已落地的 `vendor/`、`scripts/`。
- **绝不**写用户级 Skills；编译产物只落 `--staging-root` 之下，且经 containment 校验。
- 不动 `SKILL.md` 的"运行流程"7 步；只在末尾追加阶段状态注释。
- 不动阶段 A 的 13 个 schema、状态机、失效规则、`check_stage_a.py`——Ruling-1 持续生效。
- 不动阶段 B 的 `path_safety.py` / `chunker.py` / `holdout.py` / `run_journal.py` / `scan_budget.py` / `cli.py` / `check_stage_b.py`——Ruling-2 持续生效。
- 不动阶段 C 的 `extractors/` / `mechanism_merger.py` / `bundle_compiler.py` / `cli_extract.py` / `check_stage_c.py`——Ruling-C3 持续生效。
- 不动阶段 D 的 `templates/stages/` / `skill_template.py` / `six_stage_contract.py` / `six_stage_state_machine.py` / `stage_context_validator.py` / `template_contract_checker.py` / `check_stage_d.py`——Ruling-D8 持续生效。
- 不修改阶段 A 的 `compile-manifest.schema.json`；新增字段必须升 `manifest_version`。
- 失败 staging 必须保留目录但**不**写 `compile-manifest.json`，使下游无法引用（Ruling-E3）。

## Review Focus

- 相同 Bundle + 模板 + schema + 工具版本 → 相同 staging 字节（重复构建完全一致）。
- 副本被改（任何 staged 文件 hash 不匹配 manifest）→ `validate-dist` 拒绝。
- 路径逃逸（任何 staging 内文件路径解析到 `--staging-root` 之外）→ `compile` 与 `validate-dist` 拒绝。
- 硬性来源命中（字面预检在冻结输出中发现与来源正文 / 摘录 / 人物名的精确匹配或长段连续匹配）→ 拒绝。
- 目标冲突（`--staging-root` 已存在且非空）→ 拒绝。
- 并发锁：同一 `--lock-key` 下两个 `compile` 同时跑，第二个立即拒绝（不静默等待）。
- 未声明文件（staging 出现 manifest 没列出的文件）→ 拒绝。
- 名称与 stage_id 对应（staging 子目录名必须 = 六个 stage_id 之一）→ 拒绝。
- frontmatter / UTF-8 / 链接 / 资源 containment / 二进制 / 符号链接逃逸 → 任一硬门失败，staging 不写 manifest。
- 退出码：`0` 通过 / `1` 数据或契约错误 / `2` 路径或 IO 错误。

### Task 1: 并发锁

**Files:**
- Create: `scripts/concurrency_lock.py`
- Create: `tests/test_concurrency_lock.py`

**接口契约：**
- `acquire(lock_root: Path, key: str, *, timeout_seconds: float = 0.0) -> LockHandle`：基于 `lock_root/<key>.lock` 的进程间文件锁；`timeout_seconds=0` 表示非阻塞，立即返回。Windows 用 `msvcrt.locking`；POSIX 用 `fcntl.flock`。
- `LockHandle.release() -> None`：幂等释放。
- 锁目录 `lock_root` 自动 `mkdir(parents=True, exist_ok=True)`。

- [x] 写 5 个非法 / 边界单测：相同 key 二次 acquire 返回 `LockBusy`、release 后可再 acquire、释放未持有的锁不抛错、`timeout_seconds > 0` 在 Windows 上允许短轮询（条件 skip）、`lock_root` 不存在时自动创建。
- [x] 写 1 个并发单测：两个线程并发 acquire 同一 key，恰好 1 个成功。
- [x] 跑通。

### Task 2: 确定性 Skill 投影器（不写盘）

**Files:**
- Create: `scripts/skill_projector.py`
- Create: `tests/test_skill_projector.py`

**接口契约：**
- `class ProjectedSkill`：含 `stage_id` / `body`（确定性的最终 Markdown 字符串）/ `file_name`（`SKILL.md`）/ `required_mechanism_ids`。
- `project_skill(stage_id: str, template_path: Path, mechanism_subset: list[str], *, contract_version: str) -> ProjectedSkill`：
  - 读取模板 frontmatter + body，按阶段 D 契约 + 阶段 C 的 `mechanism_subset` 替换占位（`{{mechanism_ids}}`、`{{bundle_id}}`、`{{generated_at}}` 之类）。
  - **`{{generated_at}}` 永远渲染为空**——保证确定性（spec §4.7 "无生成时间字段"）。
  - 排序：占位替换后 body 仍是单字符串，按 stage_id 排，文件按路径排。
- 占位集合在 `scripts/skill_projector.py` 顶部常量 `_PLACEHOLDER_RE` 锁定为单一正则 `\{[a-z_]+\}`。

- [x] 写 4 个非法 / 边界单测：未知 stage_id 抛错、未声明占位符抛错、`{{generated_at}}` 必须渲染为空、相同输入两次调用产生相同字节字符串。
- [x] 写 2 个合法单测：六个 stage_id 都跑通、`{{mechanism_ids}}` 替换为排序后的 mechanism 列表（保证确定性）。
- [x] 跑通。

### Task 3: 静态预检（frontmatter / UTF-8 / 链接 / 资源 containment / 未声明文件 / 二进制 / 符号链接逃逸 / 名称与 stage_id 对应）

**Files:**
- Create: `scripts/preflight.py`
- Create: `tests/test_preflight.py`

**接口契约：**
- `preflight_skill(staging_root: Path, stage_id: str, body: str, *, manifest_version: str) -> list[str]`：
  - frontmatter：必须存在且含 `stage_id` / `contract_version` / `trigger_examples` / `required_inputs` / `primary_output` / `missing_input_behavior` / `stop_conditions` / `not_allowed`。
  - UTF-8：body 必须是合法 UTF-8（已是字符串，可编码回字节后解码）。
  - 链接：body 中不得含 `https?://`、`<script`、`javascript:`、`onerror=`（防止硬门）。
  - 资源 containment：body 中不得引用本地路径（`templates/`、`scripts/`、`docs/`、`schemas/`）。
  - 未声明文件：调用 `preflight_skill` 时不查 staging 内文件——这由 T5 的 `preflight_staging_directory` 查。
  - 二进制：当前 Skill 是单 Markdown 文件；如未来加二进制资源需走 T5。
  - 符号链接逃逸：每个子目录的路径必须在 `--staging-root` 之内（复用 `path_safety`）。
  - 名称与 stage_id 对应：staging 内的目录名 == stage_id。
- `preflight_staging_directory(staging_root: Path, *, declared_files: dict[str, str]) -> list[str]`：
  - `declared_files` 是 `{相对路径: 字节内容}`；staging 内的 fs-only 等价（路径 + bytes）必须完全匹配；未声明文件 → 报错。
  - 资源 containment：任何 symlink 逃逸 → 报错。
  - 二进制文件：若声明文件以 `null` 开头 4 字节，视为二进制并跳过 UTF-8 校验。

- [x] 写 6 个非法样例单测：缺 frontmatter 字段、含 `https://` 链接、含 `<script>` 标签、含 `templates/stages/` 路径引用、目录名 ≠ stage_id、staging 出现未声明文件。
- [x] 写 4 个合法样例单测：完整 Skill 通过预检、`{{mechanism_ids}}` 替换后无残留占位、空 staging 仅含 `compile-manifest.json` 也算未声明、未声明的 hidden 文件被报告。
- [x] 跑通。

### Task 4: 字面预检（精确命中 + 长段连续匹配）

**Files:**
- Create: `scripts/literal_scan.py`
- Create: `tests/test_literal_scan.py`

**接口契约：**
- `freeze_reference_corpus(reference_corpus: str, *, min_continuous_match: int = 32, shingle_size: int = 12) -> FrozenReference`：将 `reference_corpus` 切成 shingles 与最长连续子串缓存。
- `literal_preflight_scan(text: str, frozen: FrozenReference) -> list[str]`：
  - 精确命中：text 中的任何 12-codepoint shingle 与 frozen 中任一 shingle 完全相同 → 报错（精确复制）。
  - 连续匹配：text 中长度 ≥ `min_continuous_match` 的连续子串在 frozen 中出现 → 报错。
  - 返回错误列表；空列表代表通过。
- 不引入相似度比例（spec §4.4："仅按精确命中与长段连续匹配"；比例可能被通用文本稀释）。
- 不发起任何 IO；所有引用文本由调用方传入。

- [x] 写 5 个非法样例单测：精确 shingle 命中、长段连续命中（≥32）、短引用（<32 连续）通过、完全不相关文本通过、空字符串通过、Unicode 跨 4 字节字符的命中。
- [x] 写 3 个合法样例单测：合法 Skill 文本通过、改一处字符破坏 shingle 但保留连续 → 仍通过 / 视配置而定。
- [x] 跑通。

### Task 5: 确定性编译器

**Files:**
- Create: `scripts/deterministic_compiler.py`
- Create: `tests/test_deterministic_compiler.py`

**接口契约：**
- `compile_six_skills(bundle: dict, *, templates_root: Path, staging_root: Path, contract_version: str, lock_key: str, lock_root: Path) -> dict`：返回 `compile-manifest.json` dict（满足 stage A `compile-manifest.schema.json`）。
- 实现步骤（顺序固定）：
  1. 用 `concurrency_lock.acquire(lock_root, lock_key)`。
  2. `path_safety.assert_within_run_root` 对 staging_root 做 containment 检查。
  3. 若 staging_root 已存在且非空 → `raise ExistingStagingRootError`。
  4. 创建 staging_root/`six-skills/` 临时目录（atomic），把六个 projected SKILL.md 写入；同时把 `compile-manifest.json` 写入 staging_root/`compile-manifest.json`。
  5. `preflight_skill` 与 `preflight_staging_directory` 全过 → atomic rename 到 staging_root。
  6. 失败时：清理临时目录，staging_root 保留空状态，**不**写 `compile-manifest.json`。
  7. 返回 `compile-manifest.json` 内容。
- `validate_dist(staging_root: Path, *, manifest_path: Path | None = None) -> list[str]`：
  - 若 manifest 不存在 → `["compile-manifest.json missing at {path}"]`。
  - 列出 staging_root 下的所有文件，按路径排序。
  - 对每个文件重算 SHA-256，与 manifest 中 `skill_hashes[stage_id]`（及可能的辅助文件）对比；任一不匹配 → 报错。
  - 对每个 Skill 文件跑 `preflight_skill` + 字面预检（调用方传入 reference corpus）。
- 相同输入两次 `compile_six_skills` 必须生成相同 staging 字节 → 单测断言两个 staging 的 tar 字节相同。

- [x] 写 5 个非法 / 边界单测：staging_root 已存在 → 拒绝、bundle 来源 / 机制状态 banned → 拒绝、模板文件缺失 → 拒绝、字面预检命中 → 拒绝、并发 lock 被占用 → 拒绝。
- [x] 写 3 个合法单测：六个 Skill 都被写出 + manifest 完整、相同输入两次构建字节一致、失败 staging 不写 manifest。
- [x] 跑通。

### Task 6: 薄 CLI `compile` / `validate-dist`

**Files:**
- Create: `scripts/cli_compile.py`
- Create: `tests/test_cli_compile.py`

**接口契约：**
- `python scripts/cli_compile.py compile --staging-root <path> --bundle <bundle.json> --templates-root <templates/stages> --lock-root <path>`：调 `compile_six_skills`；退出码 `0` / `1` / `2`。
- `python scripts/cli_compile.py validate-dist --staging-root <path> [--manifest <compile-manifest.json>]`：调 `validate_dist`；列出 staging_root 下文件与每个文件的 SHA-256（只读校验，不改）。
- 不修改阶段 B 的 `cli.py`、阶段 C 的 `cli_extract.py`。

- [x] 写 5 个 `compile` 单测：合法 bundle → staging + manifest；staging 已存在 → exit 2；bundle 缺字段 → exit 1；并发 lock 被占 → exit 2；模板文件缺失 → exit 1。
- [x] 写 3 个 `validate-dist` 单测：合法 staging 通过；副本被改 → 报告不匹配；manifest 缺失 → exit 1。
- [x] 跑通。

### Task 7: 阶段 E 聚合验收门 + 报告

**Files:**
- Create: `scripts/check_stage_e.py`
- Create: `tests/test_stage_e_gates.py`

**接口契约：**
- `check_stage_e.py`：
  - 调 `check_stage_a..d.py` 不退化。
  - 跑 `compile_six_skills` 两次，断言 staging tar 字节一致。
  - 跑 `validate_dist` 在原 staging 上通过；在副本被改后失败。
  - 字面预检在包含精确复制的 source corpus 的 Skill 上阻断。
  - 并发 lock 测试（单线程模拟）。
  - 退出码 `0` / `1` invariant / `2` 端到端。
- 输出："Stage E aggregate gate PASSED" 或失败列表。
- 在 `docs/superpowers/reports/stage-e-YYYYMMDD.txt` 留报告。

- [x] 写 4 个聚合单测：阶段 A/B/C/D 不退化、相同输入两次构建字节一致、副本被改 `validate-dist` 报告不匹配、字面预检在含精确复制 Skill 上阻断。
- [x] 写"失败 staging 不被识别"反向断言：故意触发编译失败 → 检查 `compile-manifest.json` **不**存在。
- [x] 跑通。

### Task 8: 阶段 E 状态与交付说明

**Files:**
- Modify: `docs/superpowers/specs/2026-10-09-wenfeng-skill-design.md`（追加"阶段 E 完成报告"段）
- Modify: `README.md`（追加"阶段 E 已交付"段）
- Modify: `SKILL.md`（末尾追加阶段状态注释，不改 7 步运行流程）

- [x] 列出本阶段交付的脚本、CLI 子命令、确定性保证与各自路径；明确**本阶段不声称效果已验证、不声称可分享**。
- [x] README 同上。
- [x] SKILL.md 末尾追加阶段状态注释。
- [x] 跑一次 `python scripts/check_stage_e.py` 把输出保存为 `docs/superpowers/reports/stage-e-YYYYMMDD.txt`。

## Rulings

- **Ruling-E1:** 六个 Skill 目录是**目录 + 一个 SKILL.md** 的最简形态（spec §4.7 "恰好六个自包含 Skill"）。阶段 E 不增加额外资源文件；后续阶段 G 的 release-manifest 才引入更多文件。
- **Ruling-E2:** `{{generated_at}}` 永远渲染为空字符串（spec §4.7 "无生成时间字段"）；当前 Skill 不记录 build 时刻；任何"何时编译"的元数据由 `compile-manifest.json` 的 stage A schema 字段承担（manifest_version、tool_version 等）。
- **Ruling-E3:** 失败 staging 必须保留目录但**不**写 `compile-manifest.json`，使下游 `package` / `install` / `verify-package` 等阶段 G 的命令无法识别 staging 为有效版本。
- **Ruling-E4:** 字面预检不引入相似度比例（spec §4.4 显式排除）。精确命中（shingle_size=12 codepoint）+ 长段连续匹配（≥ 32 codepoint，默认值，policy-versioned）是阶段 E 的硬门；后续阶段 G 的内容扫描可使用更宽的窗口与阈值。**policy 同步锁**：`policies/content-scan-policy.json` 的 `min_continuous_match` 当前锁定值为 `32`（= `_DEFAULT_MIN_CONTINUOUS_MATCH` in `scripts/literal_scan.py`）。任何变更必须：(a) 升 `policy_version`；(b) 同步更新 `literal_scan.py` / `cli_compile.py` / `cli_evaluate.py` 等调用方；(c) 重跑全量聚合门（`check_stage_a..g.py`）。阶段 A plan 留 `TBD_locked_by_phase_a_calibration` 占位已**由 Ruling-E9 兑现**为 `32`。
- **Ruling-E5:** 阶段 E 不实现 `package` / `install` / `purge-run` / `eval-report`；它们属于阶段 G（与 spec §4.7 子命令对齐，但不在阶段 E 验收门内）。阶段 E 只产出 staging + compile-manifest。
- **Ruling-E6:** 路径 containment 仍由阶段 B 的 `scripts/path_safety.py` 提供；阶段 E 不引入新的路径校验逻辑。
- **Ruling-E7:** 并发锁基于 `--lock-key` 派生的 `<lock-root>/<lock-key>.lock` 文件，进程间互斥；同一进程重入 `acquire` 必须报 `LockBusy`（防止无限递归）。
- **Ruling-E8:** 阶段 E 不改 `compile-manifest.schema.json`；任何新增字段必须升 `manifest_version` 并由 stage A 的 schema 校验通过。
- **Ruling-E9:** 阶段 A plan 锁定的 `min_continuous_match` 数值**已**在 `policies/content-scan-policy.json` 中兑现为 `32`（阶段 A plan 草案中的 `TBD_locked_by_phase_a_calibration` 占位被 Ruling-E9 关闭）。后续变更需升 `policy_version`、重跑全量门禁（见 Ruling-E4 同步锁）。