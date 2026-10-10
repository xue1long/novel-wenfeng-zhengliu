# 阶段 D 实施计划：六阶段 Skill 与上下文状态机

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不调用任何模型、不动 `wenfeng-distill` 入口行为的前提下，把**六个写作阶段 Skill 模板 + stage-context 状态机 + 合法 handoff + 回退 + 三次熔断**完整落地。每个 Skill 是独立 SKILL.md 文件，含触发正负例、输入输出 schema、缺失输入行为与停止条件；本地脚本只验证模板形式、契约、跳转合法性。所有产物用阶段 A `stage-context.schema.json` 与现有状态机/失效规则（同源 `scripts/state_machine.py` 与 `scripts/invalidation_rules.py`）校验，并能经 `check_stage_a.py` / `check_stage_b.py` / `check_stage_c.py` / `check_stage_d.py` 同时通过。

**Architecture:** 六个 **TextMate-style Skill 模板**放在 `templates/stages/`，每个是 YAML frontmatter + Markdown body；纯本地静态文件，**不**携带任何可执行逻辑。本地 `scripts/six_stage_state_machine.py` 用阶段 A 已冻结的 `stage-context` schema 校验每次写作调用，提供：
- `validate_transition(current, next)` — 合法 handoff / `return_to` 检查
- `validate_retry(retry_count)` — 三次熔断
- `validate_snapshot(snapshot, contract_version)` — 输入/输出引用与 `changed_fields` 一致性
- `invalidate_stage_context(context, invalidation_class)` — 下游引用失效传播

每个 Skill 的 SKILL.md 由 `scripts/skill_template_validator.py` 做形式校验（frontmatter YAML + 必填字段 + 六个 stage_id 之一）。

**Tech Stack:** Python 3 标准库（json / re / pathlib / yaml 仅在 Python ≥ 3.10 时无需依赖；本版不使用 PyYAML，frontmatter 解析用 `tomllib` 或纯字符串解析）。阶段 A 的 `vendor/json_schema_validate.py` + 13 个 schema、阶段 B 的 `path_safety.py` / `chunker.py`、阶段 C 的 `bundle_compiler.py` / `mechanism_merger.py` / `evidence_validator.py`、`scripts/state_machine.py` / `invalidation_rules.py`。

**Spec anchors:** §4.5（六阶段 Skill 契约）、§4.6（stage-context 与状态/失效规则）、§6 阶段 D 验收原文。

## Global Constraints

- **绝不**调用任何模型；模型侧执行仍由 `wenfeng-distill` 工厂 Skill 完成；本地脚本只验证模板 + 契约 + 跳转合法性。
- **绝不**复制、提交、输出**任何**真实来源正文、留出集、证据摘录、书名、作者名、人物名。所有测试夹具使用公开虚构文本。
- **绝不**新增运行时依赖；只能使用 Python 3 标准库 + 阶段 A/B/C 已落地的 `vendor/`、`scripts/`。
- **绝不**写用户级 Skills；模板仅落 `templates/stages/` 与单测资源目录；阶段 D 不写 `--run-root`（阶段 E 接管）。
- 不动 `SKILL.md` 的"运行流程"7 步；只在末尾追加阶段状态注释。
- 不动阶段 A 的 13 个 schema、状态机、失效规则、`check_stage_a.py`——Ruling-1 持续生效。
- 不动阶段 B 的 `path_safety.py` / `chunker.py` / `holdout.py` / `run_journal.py` / `scan_budget.py` / `cli.py` / `check_stage_b.py`——Ruling-2 持续生效。
- 不动阶段 C 的 `extractors/` / `mechanism_merger.py` / `bundle_compiler.py` / `cli_extract.py` / `check_stage_c.py`——Ruling-C3 持续生效。
- 六个 stage_id 在本计划锁定：`write_entry` / `scene_design` / `character_beats` / `prose_draft` / `style_check` / `revision`；终端状态 `completed` 仅在 stage-context.stage_id 与 stage_id 枚举中。
- 阶段 D 不生成 `style-bundle.json`；模板从阶段 C 编译产物读取，只做形式校验。

## Review Focus

- 每个 Skill 必须有 frontmatter（`name` / `description` / `stage_id` / `contract_version`）+ 正文段（触发正例 / 触发负例 / 必需输入 / 主要输出 / 缺失输入行为 / 停止条件 / 不做事项）。
- 阶段间数据契约表与 spec §4.5 表一致；每个契约字段在 stage-context schema 中可表达。
- `validate_transition` 拒绝非 handoff 边（如 `write_entry → prose_draft`）、跨阶段跳号、终态继续前进；`return_to` 必须 ≤ 当前阶段索引且重跑路径不超出范围。
- `validate_retry(retry_count > 3)` 抛 `RetryExhausted`；retry_count 必须在 `stage-context` 中单调递增。
- `invalidate_stage_context` 必须返回"下游引用失效时不能继续写作"——具体到：机制 Bundle 的 mechanism_id 不在 stage-context.stage_snapshot.input_refs → 拒绝；已通过机制被 evidence_validator 拒绝 → 整链 `incomplete`。
- `compute_stage_review_status(stage_id, trace_history)` 必须区分"合法 handoff"与"非合法回退"；非法边 → `blocked`。
- 模板文件必须 UTF-8 / LF / 唯一 stage_id（六个）；模板名必须以 stage_id 命名（`templates/stages/<stage_id>.md`）；模板之间**不**互相 import / 引用（自包含）。
- 阶段间"必读输入"必须出现在 stage-context.stage_snapshot.input_refs；缺任一必读输入 → stage-context 校验抛 `MissingInput`。
- `check_stage_d.py` 必须能加载六个模板、跑所有合法 + 非法用例、产出聚合报告；阶段 D 报告强调"模板就绪"而非"效果验证"。

### Task 1: 六个 Skill 模板目录 + frontmatter 解析器

**Files:**
- Create: `templates/stages/write_entry.md`
- Create: `templates/stages/scene_design.md`
- Create: `templates/stages/character_beats.md`
- Create: `templates/stages/prose_draft.md`
- Create: `templates/stages/style_check.md`
- Create: `templates/stages/revision.md`
- Create: `scripts/skill_template.py`
- Create: `tests/test_skill_template.py`

**接口契约：**
- 每个模板文件以 YAML frontmatter 开头（`---` 分隔），必填字段：
  - `name`：唯一字符串，与 stage_id 同。
  - `description`：单行描述，含触发条件。
  - `stage_id`：枚举之一（`write_entry` / `scene_design` / `character_beats` / `prose_draft` / `style_check` / `revision`）。
  - `contract_version`：semver X.Y.Z。
  - `trigger_examples`：列表，至少 1 正例 + 1 负例。
  - `required_inputs`：列表，命名 Stage 受众决定。
  - `primary_output`：单行描述。
  - `missing_input_behavior`：单行描述（默认 `block-and-explain`）。
  - `stop_conditions`：列表，至少 1 条。
  - `not_allowed`：列表（"不调用其他 Skill"、"不引入来源剧情"等）。
- 正文段（Markdown）必须含 `## 触发条件` / `## 必读输入` / `## 主要输出` / `## 缺失输入行为` / `## 停止条件` / `## 不做事项` 六个二级标题。
- `scripts/skill_template.parse_template(path)` 返回 `dict` 含所有字段；解析失败抛 `TemplateParseError`。
- `scripts/skill_template.list_stage_templates(root)` 返回六个模板路径，按 stage_id 排序。

- [x] 写 5 个非法样例单测：缺 frontmatter、缺 `name`、缺 `stage_id`、`stage_id` 不在六阶段枚举、`trigger_examples` < 2。
- [x] 写 2 个合法样例单测：六个模板都能解析；模板唯一性（无重复 stage_id）。
- [x] 写"模板自包含"反向断言：`grep -l "templates/stages/" templates/stages/*.md` 必须无输出（任何模板都不引用其他模板）。
- [x] 跑通。

### Task 2: 阶段间数据契约表

**Files:**
- Create: `scripts/six_stage_contract.py`
- Create: `docs/contracts/six-stage-data-contract.md`
- Create: `tests/test_six_stage_contract.py`

**接口契约：**
- `STAGE_ORDER = ("write_entry", "scene_design", "character_beats", "prose_draft", "style_check", "revision")`。
- `STAGE_DATA_CONTRACT`: `dict[stage_id, StageContract]`，每个含 `required_inputs` / `primary_output` / `constraints` 三个键，严格对应 spec §4.5 表。
- `validate_stage_contract(stage_id, input_keys) -> list[str]`：检查输入键是否覆盖 `required_inputs`；缺一 → 报错。
- `assert_contract_compatibility(current_stage, next_stage) -> None`：spec §4.5 表的"约束"列转代码校验（如 `prose_draft` 仅应用 approved/limited 机制 → 在 `next_stage=prose_draft` 时检查 `current_stage=character_beats` 的输出引用）。

- [x] 写 3 个非法样例单测：缺 `required_inputs` 关键字段、`constraints` 字段类型错、`STAGE_ORDER` 长度 ≠ 6。
- [x] 写 4 个合法样例单测：六阶段两两 handoff 合法、终端 `revision → completed` 合法、`write_entry` 直接跳 `prose_draft` 被拒、跨 `return_to` 非法被拒。
- [x] 写"约束表覆盖 spec §4.5 表"反向断言：逐行校验 STAGE_DATA_CONTRACT 与 spec §4.5 一致；差异即单测 fail。
- [x] 跑通。

### Task 3: stage-context 状态机（合法 handoff / return_to / 三次熔断）

**Files:**
- Create: `scripts/six_stage_state_machine.py`
- Create: `tests/test_six_stage_state_machine.py`

**接口契约：**
- `LEGAL_HANDOFF = {(write_entry→scene_design), (scene_design→character_beats), (character_beats→prose_draft), (prose_draft→style_check), (style_check→revision), (revision→completed)}`。
- `validate_transition(current_stage, next_stage, *, return_to=None) -> None`：合法 handoff → 通过；`return_to` 必须 ∈ `{stages with index < current_stage.index}` 且 `next_stage` 必须 ∈ 合法 handoff 链；非法边 → 抛 `IllegalTransitionError`。
- `validate_retry_count(retry_count) -> None`：`retry_count > 3` 抛 `RetryExhausted`；`retry_count < 0` 抛 `ValueError`。
- `compute_stage_review_status(stage_id, trace_history)`：返回 `incomplete / blocked / limited / ready`，与阶段 A `state_machine.compute_final_state` 同源。
- `record_illegal_transition(trace_id, from_stage, to_stage, error_type)`：写 `stage-context` 风格的 `error_report`，含 `error_type='illegal_transition'`、`conflicting_stage`、`note`。
- 重跑语义：`return_to` 后只重跑受影响阶段（`return_to` 本身 + 之后所有 stage），不自动重跑整链——`partial_replay_targets(return_to, current_stage) -> list[stage_id]` 返回 `[return_to, ...STAGE_ORDER[STAGE_ORDER.index(return_to):]]`。

- [x] 写 5 个非法转移单测：跨阶段跳号（`write_entry → prose_draft`）、终态继续前进（`revision → prose_draft`）、`return_to` 指向当前阶段、`return_to` 指向当前阶段之后、`retry_count > 3`。
- [x] 写 4 个合法转移单测：`write_entry → scene_design`、`scene_design → character_beats` 回退到 `write_entry`、`prose_draft → style_check`、`revision → completed`。
- [x] 写"三次熔断"反向断言：retry_count = 4 抛 RetryExhausted；retry_count = 3 通过。
- [x] 写"重跑语义"单测：`return_to=character_beats` 且 current=`prose_draft` → 重跑列表 = `[character_beats, prose_draft]`。
- [x] 跑通。

### Task 4: 下游引用失效传播

**Files:**
- Create: `scripts/stage_context_validator.py`
- Create: `tests/test_stage_context_validator.py`

**接口契约：**
- `validate_stage_context(context: dict, *, bundle: dict | None = None) -> list[str]`：用阶段 A `stage-context.schema.json` 校验 + 业务校验：
  - `stage_snapshot.input_refs` 引用必须存在（`bundle_id` 在 run 内已知）。
  - 当 `bundle` 提供时，`stage_snapshot.input_refs` 中的 `mechanism_id` 必须在 `bundle.mechanisms[].mechanism_id` 中；否则 → `error_report.error_type='stale_mechanism_reference'`。
  - 当 `stage_snapshot.output_refs` 包含 `mechanism_id` 时同理。
- `invalidate_stage_context(context, invalidation_class) -> list[stage_id]`：复用 `scripts/invalidation_rules.compute_invalidation` 返回的下游阶段范围；返回"在 stage-context 中需要重跑的阶段"列表。
- `MissingInput` 异常 + `StaleMechanismReference` 异常。

- [x] 写 4 个非法样例单测：`stage_id` 不在六阶段枚举、`retry_count = 4`、`stage_snapshot.input_refs` 引用不存在的 mechanism_id、`stage_snapshot.changed_fields` 为空。
- [x] 写 3 个合法样例单测：完整 stage-context 通过、return_to=null 通过、`stage_id='completed'` 通过。
- [x] 写"下游引用失效时不能继续写作"反向断言：构造一个 stage-context 引用 `mechanism_id="M99"`（不在 bundle 中）→ 验证器返回含 `stale_mechanism_reference` 错误。
- [x] 跑通。

### Task 5: 模板与契约一致性检查器

**Files:**
- Create: `scripts/template_contract_checker.py`
- Create: `tests/test_template_contract_checker.py`

**接口契约：**
- `check_template_matches_contract(template: dict) -> list[str]`：模板正文与 `STAGE_DATA_CONTRACT[template.stage_id]` 是否一致（`required_inputs` / `primary_output` / `constraints` 在模板正文均能找到）。
- `check_all_templates(root) -> dict[str, list[str]]`：返回 `{stage_id: [errors]}`，空集合通过 = true。
- `assert_no_template_circular_dep(root)`：深度扫描模板正文，无任何 `templates/stages/<other>.md` 引用。

- [x] 写 3 个非法样例单测：`required_inputs` 与正文不符、模板正文缺 `## 必读输入` 段、模板正文引用其他模板路径。
- [x] 写 1 个合法样例单测：六个模板全部通过 `check_all_templates`。
- [x] 跑通。

### Task 6: 阶段 D 聚合验收门 + 报告

**Files:**
- Create: `scripts/check_stage_d.py`
- Create: `tests/test_stage_d_gates.py`

**接口契约：**
- `check_stage_d.py` 跑：阶段 A/B/C 聚合门不退化；六个模板形式校验全过；六个模板与契约一致；状态机合法 + 非法用例全过；下游引用失效传播正确。
- 退出码：`0` / `1` invariant 失败 / `2` 端到端失败。
- 输出："Stage D aggregate gate PASSED" 或失败列表。
- 在 `docs/superpowers/reports/stage-d-YYYYMMDD.txt` 留报告。

- [x] 写 4 个聚合单测：阶段 A/B/C 不退化、六个模板形式校验全过、状态机合法 + 非法用例全过、下游引用失效传播正确。
- [x] 写"模板就绪而非效果验证"反向断言：check_stage_d.py 输出文案明确不含"validated"/"ready"等效果词。
- [x] 跑通。

### Task 7: 阶段 D 状态与交付说明

**Files:**
- Modify: `docs/superpowers/specs/2026-10-09-wenfeng-skill-design.md`（追加"阶段 D 完成报告"段）
- Modify: `README.md`（追加"阶段 D 已交付"段）
- Modify: `SKILL.md`（末尾追加阶段状态注释，不改 7 步运行流程）
- Create: `docs/contracts/six-stage-data-contract.md`（人读表）

- [x] 列出本阶段交付的模板、脚本、契约文档与各自路径；明确**本阶段不声称效果已验证、不声称可分享**。
- [x] README 同上。
- [x] SKILL.md 末尾追加阶段状态注释。
- [x] 跑一次 `python scripts/check_stage_d.py` 把输出保存为 `docs/superpowers/reports/stage-d-YYYYMMDD.txt`。

## Rulings

- **Ruling-D1:** 六个 stage_id 在本计划锁定为 `write_entry` / `scene_design` / `character_beats` / `prose_draft` / `style_check` / `revision`；`completed` 仅作为终态，不作为新模板的 stage_id。任何后续阶段需要新增模板必须升 `contract_version`。
- **Ruling-D2:** 模板正文只描述触发 / 输入 / 输出 / 停止条件 / 不做事项；**不**写可执行 Python、**不**写 `wenfeng-distill` 命令、**不**写前端嵌入代码。模板是契约，模型侧执行仍由 `wenfeng-distill` 工厂 Skill 完成。
- **Ruling-D3:** 模板自包含——任何模板不得引用其他模板路径；模板之间的数据传递通过 stage-context 完成；模型侧可通过 stage_id 知道"下一个合法阶段"，但模板文件本身**不**做这件事。
- **Ruling-D4:** `state_machine.compute_final_state` 与 `invalidation_rules.compute_invalidation` 仍由阶段 A 提供；阶段 D 不重写，只**复用**。`six_stage_state_machine.py` 仅做"六阶段 handoff + return_to + 三次熔断"的薄封装，所有非法边汇总回阶段 A 状态机。
- **Ruling-D5:** `check_stage_d.py` 强调"模板就绪 + 契约就绪"，**不**测触发 precision/recall、**不**跑端到端盲评；那些是阶段 F。
- **Ruling-D6:** 模板不写"调用其他 Skill"——六个 Skill 是独立可发现单元（spec §4.5 第一句），调用顺序由总入口编排；阶段 D 不实现总入口（总入口是 `wenfeng-distill` 工厂 Skill 的一部分，阶段 E 的 `compile` 才把它绑定到 `write_entry`）。
- **Ruling-D7:** 阶段 D 不引入 PyYAML；frontmatter 用 `---` 分隔纯字符串解析；不依赖任何第三方库。
- **Ruling-D8:** `stage-context.schema.json` 是阶段 A 已冻结的 schema；阶段 D 不修改它，新增字段必须升 `contract_version` 并重跑所有聚合门。