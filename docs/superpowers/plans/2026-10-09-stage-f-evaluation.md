# 阶段 F 实施计划：冻结候选并执行评测

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不调用任何模型、不动 `wenfeng-distill` 入口行为的前提下，把**触发评测 + 阶段输出评测 + 端到端盲评 + 效果门 + 脱敏报告**完整落地。所有结果以阶段 A 已冻结的 schema（`eval-suite` / `eval-report` / `eval-cases` / `content-scan-report` 复用 stage E 的字面预检）记录，并能经 `check_stage_a..e.py` 与 `check_stage_f.py` 同时通过。

**Architecture:** 薄本地 CLI（纯 Python 标准库）。评测输入来自阶段 E 的 staging（已通过 `validate-dist`）——评测只读不写。模型侧调用仍由 `wenfeng-distill` 工厂 Skill 完成；本地脚本验证：
- 触发评测：`compute_trigger_metrics(suite, results)` 返回 `precision` / `recall`；stage F 自带合成触发用例（不依赖真实模型）；
- 阶段输出评测：`assert_output_contract(stage_id, output)` 跑机械断言；
- 端到端盲评：`evaluate_effect_gate(pairs, disagreements)` 与 stage A 的 `effect_gate.py` 同源；
- 脱敏：`redact_eval_report(report, bundle, source_id)` 把私钥/解盲映射剥离；
- 评测日志冻结：所有 skill body + eval generation text + 报告都有 SHA-256；
- 状态机：`state_machine.compute_final_state(gates_passed, authorization_purpose)` 走 stage A 同源。

**Tech Stack:** Python 3 标准库（hashlib / pathlib / json / re / statistics）。阶段 A 的 `vendor/json_schema_validate.py` + 13 个 schema、阶段 B 的 `path_safety.py` / `run_journal.py`、阶段 C 的 `evidence_validator.py` / `bundle_compiler.py`、阶段 D 的 `six_stage_contract.py` / `six_stage_state_machine.py` / `stage_context_validator.py` / `template_contract_checker.py`、阶段 E 的 `preflight.py` / `literal_scan.py` / `deterministic_compiler.py` / `cli_compile.py` / `check_stage_e.py`、`scripts/state_machine.py` / `invalidation_rules.py` / `effect_gate.py`。

**Spec anchors:** §4.8（评测系统）、§6 阶段 F 验收原文。

## Global Constraints

- **绝不**调用任何模型；模型侧执行仍由 `wenfeng-distill` 工厂 Skill 完成；本地脚本只验证评测结果 + 脱敏。
- **绝不**复制、提交、输出**任何**真实来源正文、留出集、证据摘录、书名、作者名、人物名。所有测试夹具使用公开虚构文本。
- **绝不**新增运行时依赖；只能使用 Python 3 标准库 + 阶段 A/B/C/D/E 已落地的 `vendor/`、`scripts/`。
- **绝不**写用户级 Skills；评测只读阶段 E 的 staging，**不**修改 staging 字节。
- 不动 `SKILL.md` 的"运行流程"7 步；只在末尾追加阶段状态注释。
- 不动阶段 A 的 13 个 schema、状态机、失效规则、`effect_gate.py`、`check_stage_a.py`——Ruling-1 持续生效。
- 不动阶段 B/C/D/E 已落地的脚本——Ruling-2/C3/D8/E8 持续生效。
- 阶段 F **不**修改 `eval-suite` / `eval-report` / `eval-cases` schema；任何新增字段必须升 `schema_version`。
- 阶段 F **不**引入 release-manifest 或安装命令（阶段 G）；阶段 F 只产出 `eval-report.json` + `eval-suite.json` + `eval-cases.json` + 脱敏聚合摘要。

## Review Focus

- 每个 stage 触发评测 ≥ 10 positive + 10 negative + 5 boundary；precision/recall ≥ 0.90（spec §4.8 (2)）。
- 每个 stage 输出评测覆盖正常 / 缺失 / 负向 / 停止条件；schema / 必需输出 / 硬约束机械断言 100%（spec §4.8 (3)）。
- 端到端盲评 ≥ 6 组配对 × ≥ 3 类场景；同模型同参数；基线不获得 Bundle；候选随机匿名 + 随机顺序 + 冻结（spec §4.8 (4)）。
- 效果门：≥ 4 组胜出、median delta ≥ +0.5、Skill 风格贴合 median ≥ 4、文本质量 delta ≥ -0.5。
- 评审分歧 > 1 分 → 该维度不确定 → 整体降 limited。
- 缺输出 / 格式错误 / 运行中断 → `incomplete`（不计通过）。
- 硬门失败（缺失输入、负向示例失败、误触发）→ `blocked`。
- 状态机：阶段 A 的 `state_machine.compute_final_state` 同源；无模型调用。
- 脱敏报告：不携带解盲映射、逐案例评测文本、评分密钥；只留脱敏聚合摘要 + 哈希。
- 冻结：所有 eval generation text 与最终 Skill body 都保存 SHA-256。
- 阶段 F 不修改 staging 字节（只读）；`validate-dist` 在阶段 F 之前已通过。

### Task 1: 触发评测指标计算器

**Files:**
- Create: `scripts/trigger_metrics.py`
- Create: `tests/test_trigger_metrics.py`

**接口契约：**
- `compute_trigger_metrics(suite: dict, results: list[dict]) -> dict`：suite 是 `eval-suite.schema.json` 形态（cases 含 must_trigger / must_not_trigger / boundary），results 是 `[{"case_id", "stage_id", "triggered"}]` 列表；返回 `{"stage_id": {"precision", "recall", "total_must_trigger", "total_must_not_trigger", "missing_required_inputs": False}}`。
- precision / recall：spec §4.8 (2) "各阶段 precision 与 recall 均不低于 0.90"。
- 必备输入缺失（`required_inputs` 为空）→ `missing_required_inputs: True` → stage `blocked`。
- 缺少 positive / negative 用例 → `missing_cases: "positive"|"negative"`。
- 边界用例只统计通过率，不计入 precision/recall。

- [x] 写 5 个非法 / 边界单测：precision < 0.90 → 失败；recall < 0.90 → 失败；positive 数 < 10 → 失败；negative 数 < 10 → 失败；缺 required_inputs → blocked。
- [x] 写 3 个合法单测：六阶段 precision=1.0 / recall=1.0 通过；边界用例通过率不影响 precision/recall；空 results → precision=1.0/recall=0.0 的安全默认。
- [x] 跑通。

### Task 2: 阶段输出机械断言

**Files:**
- Create: `scripts/output_assertions.py`
- Create: `tests/test_output_assertions.py`

**接口契约：**
- `assert_output_contract(stage_id: str, output: dict, *, bundle: dict | None = None) -> list[str]`：根据阶段 D `six_stage_contract.STAGE_DATA_CONTRACT` 校验：
  - `required_inputs` 必填字段必须在 `output` 内；
  - `primary_output` 字段名匹配 `primary_output`；
  - `stop_conditions` 至少 1 条被显式命中（即 output 含 `stop_condition_hit` 字段，且值在 contract 的约束中）；
  - 若 `bundle` 提供，output 不应包含 excluded 机制的引用。
- `evaluate_all_stages(results: dict[str, dict], *, bundle: dict | None = None) -> dict`：返回 `{"mechanical_pass_rate", "passed", "failed", "missing_outputs": [stage_id]}`。
- 缺输出 → 返回 `incomplete`（spec §4.8 (3) "缺输出、格式错误或运行中断一律为 incomplete"）。

- [x] 写 6 个非法单测：六个阶段分别缺 required input；硬约束失败（output 含 excluded 机制引用）；输出格式错（schema 失败）；缺输出 → `incomplete`；stop_conditions 未命中；unknown stage_id。
- [x] 写 3 个合法单测：六阶段全部通过；missing_outputs 列表准确；mechanical_pass_rate = 1.0。
- [x] 跑通。

### Task 3: 端到端盲评框架

**Files:**
- Create: `scripts/end_to_end_eval.py`
- Create: `tests/test_end_to_end_eval.py`

**接口契约：**
- `class PairResult`：含 `pair_id` / `scenario_class` / `baseline_score` / `six_stage_score` / `style_fit_delta` / `quality_delta`。
- `evaluate_effect_gate(pairs: list[PairResult], *, disagreement_per_dimension: dict[str, float] | None = None) -> dict`：复用 stage A `effect_gate.evaluate_effect_gate` 同源；返回 `{"verdict", "winning_pairs", "style_fit_median", "pairing_median_delta", "quality_median_delta", "undetermined_dimensions"}`。
- `redact_eval_report(report: dict, *, source_id: str, bundle_id: str) -> dict`：剥离 `pair_results` / `per_pair_unblinding_map` / `rating_secrets` / `unredacted_text`；保留 `gate_results` / `aggregate_summary` / `frozen_hashes`。
- `freeze_evaluation_artifacts(staging_root: Path, eval_text: dict) -> dict`：对 `eval_text` 每个 `case_id` 的 generation 文本与每个 stage body 算 SHA-256；返回 `{stage_id: hash, case_id: hash, ...}`。

- [x] 写 5 个非法单测：pairs < 6 → 拒；winning_pairs < 4 → limited；median delta < +0.5 → limited；quality delta < -0.5 → limited；disagreement > 1 → 该维度 undetermined → limited。
- [x] 写 4 个合法单测：6 组配对全胜出 → ready；脱敏后 report 不含解盲映射；冻结哈希与 staging 字节一一对应；同一份 eval 文本两次冻结哈希一致。
- [x] 写"评审分歧 > 1 分"反向断言：明确构造 disagreement > 1 → 报告含 `undetermined_dimensions`。
- [x] 跑通。

### Task 4: 状态机聚合（阶段 A 同源）

**Files:**
- Create: `scripts/final_state_evaluator.py`
- Create: `tests/test_final_state_evaluator.py`

**接口契约：**
- `compute_run_state(gates_passed: set[str], authorization_purpose: str) -> str`：复用 stage A `state_machine.compute_final_state`；返回 `incomplete / blocked / limited / ready`。
- `record_state_transition(run_journal_path: Path, *, from_state: str, to_state: str, evidence: dict)`：在 `run-manifest.json` 的 `step_log` 追加一条；幂等（按 `(from_state, to_state, evidence_hash)` 去重）。
- `evaluate_evaluation_state(trigger: dict, output_eval: dict, end_to_end: dict, *, has_unredacted_artifacts: bool, missing_outputs: list[str]) -> str`：聚合三个门 + 脱敏门 + 缺输出门 → run state。

- [x] 写 4 个非法单测：缺输出 → incomplete；未脱敏 → blocked；硬约束失败 → blocked；trigger 不达标 → limited。
- [x] 写 3 个合法单测：全门通过 + 授权允许分享 → ready；全门通过但授权仅 private_only → limited；trigger 100% 但 end_to_end 没数据 → limited。
- [x] 跑通。

### Task 5: 评测冻结与脱敏报告写入

**Files:**
- Create: `scripts/evaluation_freezer.py`
- Create: `tests/test_evaluation_freezer.py`

**接口契约：**
- `write_eval_suite(staging_root: Path, suite: dict) -> Path`：把 suite 写到 `staging_root/eval-suite.json`，以 stage A `eval-suite.schema.json` 校验。
- `write_eval_cases(staging_root: Path, cases: dict) -> Path`：cases → `staging_root/eval-cases.json`。
- `write_eval_report(staging_root: Path, report: dict, *, redacted: bool = True) -> Path`：report → `staging_root/eval-report.json`；脱敏模式下自动 strip 私密字段。
- `freeze_all_artifacts(staging_root: Path, eval_generation_text: dict[str, str], *, report: dict) -> dict`：对 staging 内每个 SKILL.md、eval generation text、eval-suite.json、eval-cases.json、eval-report.json 算 SHA-256；写 `eval-report.json.frozen_hashes` 字段。

- [x] 写 5 个非法单测：suite 缺必填字段被拒；cases 缺 precision/recall 字段被拒；未脱敏报告含解盲映射 → blocked；缺输出的 stage 进入 incomplete；写失败 staging 不变。
- [x] 写 3 个合法单测：完整 cycle 跑通；脱敏报告不含 private_* 字段；冻结哈希幂等。
- [x] 跑通。

### Task 6: 薄 CLI `run-evaluation` / `validate-evaluation`

**Files:**
- Create: `scripts/cli_evaluate.py`
- Create: `tests/test_cli_evaluate.py`

**接口契约：**
- `python scripts/cli_evaluate.py run-evaluation --staging-root <path> --suite <suite.json> --cases <cases.json>`：跑 trigger / output / end-to-end 三个门的合成评测；写 `eval-suite.json` / `eval-cases.json` / `eval-report.json`（脱敏）；返回运行状态 `ready/limited/blocked/incomplete`。
- `python scripts/cli_evaluate.py validate-evaluation --staging-root <path>`：只读校验 `eval-report.json` 的 schema 与脱敏合规性；缺任何文件 → exit 1。
- 不修改阶段 E 的 `cli_compile.py`、阶段 C 的 `cli_extract.py`、阶段 B 的 `cli.py`。
- 退出码：`0` / `1` / `2`。

- [x] 写 5 个 `run-evaluation` 单测：合法 staging → ready（合成 happy path）；trigger 不达标 → limited；end-to-end 不达标 → limited；缺输出 → incomplete；未脱敏输入 → blocked。
- [x] 写 3 个 `validate-evaluation` 单测：合法脱敏报告通过；含解盲映射被拒；缺 `eval-report.json` → exit 1。
- [x] 跑通。

### Task 7: 阶段 F 聚合验收门 + 报告

**Files:**
- Create: `scripts/check_stage_f.py`
- Create: `tests/test_stage_f_gates.py`

**接口契约：**
- `check_stage_f.py`：
  - 调 `check_stage_a..e.py` 不退化。
  - 跑合成 happy path：staging → run-evaluation → ready；产出脱敏报告；冻结哈希与 staging 字节一致。
  - 跑 trigger 不达标 → limited；end-to-end 不达标 → limited；缺输出 → incomplete；未脱敏 → blocked。
  - 退出码 `0` / `1` invariant / `2` 端到端。
- 输出："Stage F aggregate gate PASSED" 或失败列表。
- 在 `docs/superpowers/reports/stage-f-YYYYMMDD.txt` 留报告。

- [x] 写 5 个聚合单测：阶段 A/B/C/D/E 不退化；happy path 产出 ready；trigger 不达标 → limited；end-to-end 不达标 → limited；缺输出 → incomplete。
- [x] 写"0 模型调用"反向断言：grep `stage_f` 全部脚本无 socket / urllib / requests import。
- [x] 跑通。

### Task 8: 阶段 F 状态与交付说明

**Files:**
- Modify: `docs/superpowers/specs/2026-10-09-wenfeng-skill-design.md`（追加"阶段 F 完成报告"段）
- Modify: `README.md`（追加"阶段 F 已交付"段）
- Modify: `SKILL.md`（末尾追加阶段状态注释，不改 7 步运行流程）

- [x] 列出本阶段交付的脚本、评测报告与各自路径；明确**本阶段不声称效果已验证、不声称可分享**；精度/recall 数字仅限本评测任务范围内的工程放行（spec §4.8 "N=6 只支持本评测任务范围内的工程放行，不支持统计显著性或普遍有效声明"）。
- [x] README 同上。
- [x] SKILL.md 末尾追加阶段状态注释。
- [x] 跑一次 `python scripts/check_stage_f.py` 把输出保存为 `docs/superpowers/reports/stage-f-YYYYMMDD.txt`。

## Rulings

- **Ruling-F1:** 阶段 F **不**调模型；所有评测输入由 spec 锁定（10+10+5 / 6+ 类场景），本地合成用例保证 reproducible。
- **Ruling-F2:** 阶段 F **不**修改任何阶段 A 的 schema；新增字段必须升 `schema_version`。
- **Ruling-F3:** `compute_run_state` 与 stage A 的 `state_machine.compute_final_state` 完全等价；不在 stage F 重写状态机。
- **Ruling-F4:** 脱敏报告是**唯一**可发布物；`eval-report.json` 写入 staging 之前必须经 `redact_eval_report`。
- **Ruling-F5:** 解盲映射、逐案例评测文本、评分密钥留在私有 run root（spec §4.8 最后一段）；阶段 F 仅把它们写到 `run_root` 而非 staging。
- **Ruling-F6:** N=6 端到端配对只支持本评测任务范围内的工程放行；不写"统计显著"或"普遍有效"声明。
- **Ruling-F7:** 阶段 F 不实现 `package` / `install` / `purge-run` / `eval-report` 的实际运行（这些是 stage G 的 CLI 子命令；阶段 F 仅产出 `eval-report.json` 数据）。
- **Ruling-F8:** 阶段 F 不修改 staging 字节；只读 `validate-dist` 已通过的结果。