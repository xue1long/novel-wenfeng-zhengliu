# 阶段 A 实施计划：冻结契约、门槛与交付定义

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不动任何模型调用、不动现有 `wenfeng-distill` 入口行为的前提下，把六阶段文风蒸馏系统所需的所有**契约、数值门槛与交付定义**冻结为可被后续阶段 (B–G) 直接引用的代码与文档资产。阶段 A 完成后，仅意味着"地基已冻"，并不声称任何效果已验证或可分享。

**Architecture:** 用 Python 标准库 + JSON Schema (Draft 2020-12 或 2019-09，二选一并在阶段 A 锁定) 落地 12 个 schema、3 个 policy 文件和一份状态机表；用 `unittest` + 合成数据做门禁自检。所有契约都以「文件 + 单测 + 文档」三位一体交付，避免口头规则。

**Tech Stack:** Python 3 标准库、`jsonschema` (内置或 vendored，二选一并在任务 0 锁定)、Codex `SKILL.md`、Markdown。

**Spec:** `docs/superpowers/specs/2026-10-09-wenfeng-skill-design.md` §4.1 / §4.3 / §4.4 / §4.5 / §4.6 / §4.7 / §4.8 / §4.9 / §6 阶段 A

## Global Constraints

- 不复制、提交或输出来源正文、留出样本、证据摘录、书名、人物名或源名映射；所有合成夹具使用公开虚构文本。
- 不增加运行时依赖，除非任务 0 已锁定；锁定后必须在 `requirements.txt` 或同等位置以 vendored / 标准库方式固定。
- 不调模型、不引入网络 IO、不引入数据库；契约校验必须可在纯本地一次性跑通。
- 不修改 `SKILL.md` 与 `wenfeng-distill` 当前行为；阶段 A 只**新增**契约资产，必要时为契约写一个**只读**的 `python -m wenfeng_skill.contracts` 入口，不替换现有 CLI。
- 不安装任何 Skill 到用户级目录；不初始化 Git 仓库。
- 每个 schema 必须有：合法最小样例 + 至少 1 个非法样例 + 单测覆盖。
- 每个 policy 必须有：默认数值 + 至少 1 组覆盖"缺数值 → 不得 ready"的单测。

## Review Focus

- `ready` Bundle 在缺声明维度或不足跨章节门槛时**必须**被任一合约拒绝；`limited` Bundle 可包含局部机制但仍需 ≥2 个独立场景支持。
- 任一 schema 在缺字段、坏 JSON、错误 ID、无效行范围、重复机制 ID、跨文件引用缺失时给出定位明确错误。
- 任一 policy 缺数值 profile 时不得让对应模型进入 ready 路径；模型预算 profile 必须含「最大请求数 / 累计输入 token / 单批 token 上限 / 超限策略」四项缺一不可。
- 状态机表必须显式列出从 `incomplete / blocked / limited / ready` 出发的合法转移与硬阻断转移；非法转移必须被单测模拟。
- 哈希失效规则必须显式列出 5 类触发场景（来源/规范化/分块版本、提取提示/复核模型/候选 schema、Bundle/模板/编译器、评分模型/量表、语义扫描模型/策略）并被单测模拟。
- 任何门禁校验器都不得把结构合格误报为版权、来源隔离或语义安全合格——文案必须固定带"structural confidence only"。

### Task 0: 锁定 JSON Schema 方言与依赖策略

**Files:**
- Create: `schemas/_meta.json`（记录锁定的 schema dialect、版本与 vendoring 决策）
- Create: `tests/test_contracts_meta.py`（断言 `_meta.json` 存在且字段齐全）

**Interfaces:**
- `_meta.json` 至少包含：`schema_dialect`（"draft-2020-12" 或 "draft-2019-09"，二选一锁定）、`schema_library`（"stdlib" 或 "vendored:<path>"，二选一锁定）、`locked_at`、`owner`。
- 单测：读取 `_meta.json`，断言两个二选一字段都已确定，且没有 "TBD" 字面值。

- [x] 写 `tests/test_contracts_meta.py`：断言 `_meta.json` 存在、含必需字段、两个二选一字段值在合法集合内。
- [x] 运行 `python -m unittest tests.test_contracts_meta -v` 确认失败（文件尚不存在）。
- [x] 写 `schemas/_meta.json`，先放 `TBD` 占位字段。
- [x] 再跑单测，确认覆盖"未锁定 → 失败"的语义；然后把两个二选一字段改为确定值。
- [x] 在本文件"Rulings"追加 Ruling-1 记录：为什么选这个方言 / 为什么 stdlib。

### Task 1: 来源契约三件套 (source / chunk / run manifest)

**Files:**
- Create: `schemas/source-manifest.schema.json`
- Create: `schemas/chunk-manifest.schema.json`
- Create: `schemas/run-manifest.schema.json`
- Create: `schemas/examples/source-manifest.example.json`
- Create: `schemas/examples/chunk-manifest.example.json`
- Create: `schemas/examples/run-manifest.example.json`
- Create: `tests/test_source_contracts.py`（按 spec §4.1 范围）

**契约要点（spec §4.1）:**
- `source-manifest`: `source_id` 必须是 12 位小写十六进制；`source_fingerprint` 必须是 64 位 hex；`encoding` ∈ {`utf-8`}; `format` ∈ {`txt`, `markdown`}; `authorization.scope.model_processing` 与 `authorization.scope.derivative_use` 必须存在；缺任一授权字段 → 拒绝。
- `chunk-manifest`: 每条 chunk 必须有稳定 `chunk_id`、`chapter_id`、`scene_id`、`char_offset` ∈ `[start,end)` 且 `start < end`、`window_hash`、`boundary_confidence` ∈ {`high`, `medium`, `low`}; `parser_version` 必填；不得保存正文。
- `run-manifest`: `model_budget_policy_version` 必填、`step_log[]` 每条含 `step_id` / `input_hash` / `prompt_template_version` / `model_id` / `output_path` / `output_hash` / `status` / `retry_count` / `error_type`。

- [x] 写 6 个非法样例单测：缺 `source_id`、错位 hex、缺 `authorization.model_processing`、chunk `start >= end`、chunk 包含 `body` 字段、run-manifest 缺 `model_budget_policy_version`。
- [x] 写 3 个合法最小样例单测：source/chunk/run 各一个 happy path。
- [x] 运行 `python -m unittest tests.test_source_contracts -v` 先确认全部失败。
- [x] 实现 3 个 schema JSON。
- [x] 写 3 个 example JSON（合成内容，绝不引用真实小说）。
- [x] 再跑单测，确认全部通过。
- [x] 校验器在错误消息中必须包含字段路径（如 `chunk_manifest[0].char_offset.start`）——单测断言错误信息含路径。

### Task 2: 候选机制与证据账本 schema

**Files:**
- Create: `schemas/candidate-mechanism.schema.json`
- Create: `schemas/evidence-ledger.schema.json`
- Create: `schemas/examples/candidate-mechanism.example.json`
- Create: `schemas/examples/evidence-ledger.example.json`
- Create: `tests/test_candidate_contracts.py`

**契约要点（spec §4.3 + §4.4）:**
- `candidate-mechanism`: 必填 `mechanism_id`、`dimension` ∈ 五个枚举值（`narrative_voice` / `sentence_rhythm` / `scene_transition` / `dialogue_subtext` / `imagery_rhetoric`）、`rule`（非空字符串）、`applies_when`、`do_steps[]`、`forbidden_when`、`stage_bindings[]` ⊂ 六个 `stage_id`、`evidence_refs[]`、`counterexample_refs[]`、`extraction_prompt_version`、`review_status` ∈ {`pending`, `supported`, `limited`, `unsupported`}。
- 每条 `evidence_ref` 只允许 `chunk_id` + `scene_id` + `chapter_id` + `char_offset` 闭开区间 + `excerpt_hash`，**不得**保存 `excerpt_body`。
- `evidence-ledger`: 单条摘录正文 `≤ 200` 个 Unicode 码点（按 Unicode 码点而非字符计），含 `position`、`scope`、`counter_examples[]` 与 `decision`。

- [x] 写 7 个非法样例单测：缺 `mechanism_id`、`dimension` 越界、`review_status` 越界、`evidence_ref` 含正文、摘录超 200 码点、`stage_bindings` 含未知 stage、`counterexample_refs` 缺字段。
- [x] 写 2 个合法样例单测：`approved` 候选 + `limited` 候选各一。
- [x] 运行单测先确认失败。
- [x] 实现 2 个 schema + 2 个 example。
- [x] 再跑单测确认通过。
- [x] 单测中准备一段恰好 201 码点的合成摘录，断言被拒；同时准备 200 码点版本，断言通过。

### Task 3: Style Bundle 与 stage-context schema

**Files:**
- Create: `schemas/style-bundle.schema.json`
- Create: `schemas/stage-context.schema.json`
- Create: `schemas/examples/style-bundle.example.json`
- Create: `schemas/examples/stage-context.example.json`
- Create: `tests/test_bundle_contracts.py`

**契约要点（spec §4.4 + §4.6）:**
- `style-bundle`: 必填 `schema_version`、`bundle_version`、`source_id`（12 位 hex）、`evidence_status` ∈ {`pending`, `approved`, `limited`, `unsupported`}、`claimed_dimensions[]`（必须 ⊆ 五维集合）、`mechanisms[]`、`stage_bindings`（六个 `stage_id` 全列，允许空数组）、`content_exclusions[]`（只允许通用类别枚举）、`evaluation_ref`。
- `stage-context`: `contract_version`、`trace_id`、`bundle_id`、`stage_id` ∈ 六阶段枚举、`retry_count` ∈ {0,1,2,3}、`stage_snapshot`（只存输入/输出**引用**与 `changed_fields`）、`error_report`（可空）、`next_stage`（可空）、`return_to`（可空）。

- [x] 写非法样例：`claimed_dimensions` 包含未知维度、`stage_bindings` 引用不存在的 `mechanism_id`、`stage_bindings` 含未知 stage、Bundle 含原句字段、`stage_context.retry_count = 4`。
- [x] 写合法样例：`limited` Bundle 含一个 `limited` 机制 + 一个 `approved` 机制，stage_bindings 把 `approved` 绑给 `prose_draft`；`stage-context` 处于 `scene_design` 中间状态。
- [x] 实现 schema + example。
- [x] 单测断言：所有错误信息含字段路径；`stage_bindings` 引用不存在的 mechanism 时错误明确说"missing mechanism"。
- [x] 单测断言：`content_exclusions` 若含 `book_name` / `author_name` / `character_name` 等来源专属类别，**必须被拒**——这一项 spec §4.4 明确禁止。

### Task 4: 评测三件套 schema

**Files:**
- Create: `schemas/eval-suite.schema.json`
- Create: `schemas/eval-report.schema.json`
- Create: `schemas/eval-cases.schema.json`（阶段 A 锁定用例结构；具体用例留阶段 F 填充）
- Create: `schemas/examples/eval-suite.example.json`
- Create: `schemas/examples/eval-report.example.json`
- Create: `tests/test_eval_contracts.py`

**契约要点（spec §4.8）:**
- 每个评测结果必填 `model_id` / `model_version` / `prompt_version` / `generation_params` / `budget` / `tool_version` / `case_version` / `input_hash` / `output_hash` / `completion_status` ∈ {`complete`, `incomplete`} / `incomplete_reason`（可空）。
- 端到端盲评样例必须能表达「baseline vs six-stage pairing、相同 brief / 模型 / 生成参数 / 总 token 预算」。
- `eval-report` 必填 `pairing_diffs`、`pairing_median`、`disagreement_flags`、`gate_results`（触发 / 输出 / 端到端三门）。

- [x] 写非法样例：缺 `model_version`、`completion_status = "partial"`、`pairing_diffs` 不是对象数组。
- [x] 写合法样例：6 组配对的端到端盲评骨架 + 触发评测 precision/recall 字段骨架。
- [x] 实现 schema + example。
- [x] 单测断言：效果门计算函数能识别 spec §4.8 的所有硬条件（≥4 组胜出、差值中位数 ≥ +0.5、风格贴合中位数 ≥ 4、文本质量差值 ≥ -0.5、评审分歧 > 1 → 不确定）。

### Task 5: 内容扫描与编译/发布三件套 schema

**Files:**
- Create: `schemas/content-scan-report.schema.json`
- Create: `schemas/compile-manifest.schema.json`
- Create: `schemas/release-manifest.schema.json`
- Create: `schemas/examples/content-scan-report.example.json`
- Create: `schemas/examples/compile-manifest.example.json`
- Create: `schemas/examples/release-manifest.example.json`
- Create: `tests/test_scan_compile_contracts.py`

**契约要点（spec §4.4 + §4.7 + §4.9）:**
- `content-scan-report`: 每个窗口必填 `window_id`、`chunk_id`、结果 ∈ {`checked`, `risk`, `inconclusive`, `failed`}；必含 `policy_version`、`coverage_summary`。
- `compile-manifest`: 六个 Skill 目录哈希、模板哈希、Schema 版本、编译器版本；含 `staging_path`；明确**不含**生成时间字段（spec §4.7 要求 LF/UTF-8/无时间戳）。
- `release-manifest`: 含 `shareable` 布尔字段（仅在 `ready` 且授权允许分享时为 true）、`authorization_purpose`、`zip_hash`（可空）、`policy_versions`、`eval_summary_hash`、`content_scan_summary_hash`。

- [x] 写非法样例：扫描结果缺 `policy_version`、compile-manifest 含 `generated_at` 字段、release-manifest `shareable=true` 但无授权允许分享、release-manifest 含 `body_excerpt` 字段。
- [x] 写合法样例：每个 schema 一个 happy path（合成）。
- [x] 实现 schema + example。
- [x] 单测断言：compile-manifest 任何含 `generated_at` / `timestamp` / `created_at` 的额外属性**必须被拒**（additionalProperties 限制 + 字段黑名单测试）。

### Task 6: 三份 policy 文件

**Files:**
- Create: `policies/evaluation-policy.json`
- Create: `policies/content-scan-policy.json`
- Create: `policies/model-budget-policy.json`
- Create: `tests/test_policy_gates.py`
- Create: `scripts/check_policy_gate.py`（只读检查器，不修改任何状态）

**契约要点（spec §4.8 + §4.4 + §4.1）:**
- `evaluation-policy.json`: 锁定触发评测 `must_trigger ≥ 10` / `must_not_trigger ≥ 10` / `boundary ≥ 5`，precision/recall 阈值 `≥ 0.90`；端到端 `pairs ≥ 6` / `min_winning_pairs ≥ 4` / `pairing_median_min ≥ +0.5` / `style_median_min ≥ 4` / `quality_delta_min ≥ -0.5` / `disagreement_threshold = 1.0`。
- `content-scan-policy.json`: 锁定 `shingle_size = 12`、`min_continuous_match` 连续匹配阈值（具体数值在阶段 A 设为 `TBD_locked_by_phase_a_calibration`，但文件结构必须含此字段与版本号字段）；控制集要求 `positives ≥ 20` / `negatives ≥ 20` / `negative_misblock_max ≤ 1`。
- `model-budget-policy.json`: 必须为**每个**被支持模型列一个 `profiles[model_id]`：`max_requests`、`max_input_tokens_total`、`max_tokens_per_batch`、`overlimit_policy` ∈ {`block`, `degrade_to_limited`, `retry`}。缺任一字段或任一支持模型 → 该模型不得 ready。

- [x] 写 6 个非法样例单测：触发评测少 1 个用例、阈值 < 0.90、控制集负例不足、模型缺 `max_input_tokens_total`、`overlimit_policy` 越界、`positives < 20`。
- [x] 写合法样例单测：完整三份 policy 通过门禁。
- [x] 实现 `check_policy_gate.py`：CLI 入口 `python scripts/check_policy_gate.py`，返回 0/1/2 与 `validate_bundle.py` 保持一致；只读检查、不写文件、不调模型。
- [x] 单测断言：缺数值 profile 时调用方**不得**得到 "ready" 状态（用一个 `compute_readiness(policy, model_id)` 函数证明）。
- [x] README 增加"Policy 门禁"段落，说明命令与退出码。

### Task 7: 状态机与哈希失效规则文档 + 代码化

**Files:**
- Create: `docs/contracts/state-machine.md`（人读 + 表格）
- Create: `docs/contracts/invalidation-rules.md`
- Create: `scripts/state_machine.py`（纯函数：`transition(current, event) -> next | Blocked`）
- Create: `tests/test_state_machine.py`
- Create: `tests/test_invalidation.py`

**契约要点（spec §4.6）:**
- 状态集合：`incomplete / blocked / limited / ready`；来源、抽取、编译、扫描、授权门任一失败 → `blocked`；`ready` 必须显式列出 6 个通过的子门。
- 失效规则 5 类：(1) 来源/规范化/分块版本变化 → 抽样、留出、下游全失效；(2) 提取提示/复核模型/候选 schema 变化 → 提取结果 + 下游失效；(3) Bundle/模板/编译器变化 → 编译/评测/扫描/发布失效；(4) 评分模型/量表变化 → 评测/发布失效；(5) 语义扫描模型或策略变化 → 受影响窗口 + 发布失效。增加扫描预算**不**使已完成窗口失效（仅续跑未完成）。

- [x] 写非法转移单测：`incomplete → ready`（缺门）、`blocked → ready`（已硬阻断）、`limited → shareable`（必须经 `ready` 中转）。
- [x] 写合法转移单测：`incomplete → incomplete`（续跑）、`incomplete → blocked`（授权缺失）、`limited → ready`（所有门通过 + 授权允许分享）。
- [x] 实现 `state_machine.py` 的 `transition()` 与 `requires_authorization_for_share(state, authz)` 两个纯函数。
- [x] 写失效规则单测：5 类触发各一例；增加扫描预算一例反向断言（不得触发失效）。
- [x] 在两份 markdown 中嵌入与代码同名的表格与公式，便于交叉 review。

### Task 8: 阶段 A 验收门自检总入口

**Files:**
- Create: `tests/test_stage_a_gates.py`（聚合门）
- Create: `scripts/check_stage_a.py`（聚合 CLI）
- Modify: `README.md`（新增"阶段 A 验收"段；不改既有段落）

**契约要点（spec §6 阶段 A 验收原文）：**
> 状态转移表、哈希失效规则、各门的输入/输出和阻断条件无矛盾；测试夹具覆盖正常、失败、超预算、断点续跑和授权不足。

- [x] 写 `check_stage_a.py`：依次跑所有 schema 单测 + policy 门禁 + 状态机 + 失效规则；任一失败退出码 1；输出汇总表（人读）。
- [x] 写 `test_stage_a_gates.py`：从单测角度断言——当某份 policy 故意缺 `max_tokens_per_batch` 时，跑全套门禁会失败并报告"model X missing profile field"；该用例必须通过且可定位。
- [x] 写 5 个合成场景夹具（fixtures/fixtures_stage_a/）：正常 / 失败 / 超预算 / 断点续跑 / 授权不足 各一；只放在 `tests/fixtures/`，绝不放真实来源。
- [x] README 增加：`python scripts/check_stage_a.py` 命令、退出码表、阶段 A 范围声明。
- [x] 在 SKILL.md 末尾追加阶段状态注释：阶段 A 资产已冻结；阶段 B–G 尚未启动；本入口行为不变。

### Task 9: 阶段 A 状态与交付说明

**Files:**
- Modify: `docs/superpowers/specs/2026-10-09-wenfeng-skill-design.md`（追加"阶段 A 完成报告"段）
- Modify: `README.md`（追加"阶段 A 已交付"段，不改既有段落）

- [x] 在 spec 末尾追加"阶段 A 完成报告"，列出本阶段交付的 schema/policy/state-machine/invalidation/聚合门清单与各自路径，并明确：**本阶段不声称效果已验证、不声称可分享、入口行为不变**。
- [x] README 同上。
- [x] 不改动 `SKILL.md` 的"运行流程"7 步；只在末尾追加阶段状态注释。
- [x] 跑一次 `python scripts/check_stage_a.py`，把输出保存为 `docs/superpowers/reports/stage-a-YYYYMMDD.txt`。

## Rulings

- **Ruling-1 (T0 已确认):** 选用 `draft-2020-12` 方言 + 单文件 vendored 自写校验器（`vendor/json_schema_validate.py`）。自写而非引入 `jsonschema` 的原因：(1) spec §3.1 明确"无新增运行时依赖"；(2) 阶段 A 实际只用 ~25 个关键字的子集，vendored 单文件 < 250 行即可覆盖；(3) 自写版本对字段路径错误信息能保持人读稳定。
- **Ruling (待任务 0 确认):** 选定 JSON Schema 方言 + 库策略后写入 `schemas/_meta.json`；阶段 A 内不再切换。
- **Ruling:** 阶段 A 只交付**契约**与**只读**门禁，不写任何"会改 run 状态"的可写 CLI，避免与阶段 E 的 `compile / package / install` 提前耦合。
- **Ruling:** 所有 example / fixture 使用公开虚构文本（如自创三段假小说），不引用任何真实作品；fixtures 只放在 `tests/fixtures/`。
- **Ruling:** `content-scan-policy.json` 的 `min_continuous_match` 数值在阶段 A 允许 `TBD_locked_by_phase_a_calibration` 占位，但**文件结构与字段约束**必须冻结；阶段 G 校准后升版本。
- **Ruling:** 不引入 `jsonschema` pip 依赖；如需 Draft 2020-12 支持，优先用 vendored 单文件或自写最小校验子集；如 stdlib 已够用则直接使用并在 `_meta.json` 标记 `stdlib`。
- **Ruling:** 阶段 A 完成后必须能在干净环境一次性 `python scripts/check_stage_a.py` 通过；这是后续阶段 B–G 准入的前置条件。