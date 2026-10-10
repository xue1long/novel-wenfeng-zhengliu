# 二次校验 follow-up 报告（2026-10-09）

## 范围
- 起点：用户请求"全量阅读下项目，做下二次校验，检查有没有 bug"
- 末态：用户对二次校验的 3 个高优先级决策"按推荐"

## 已修

| 位置 | 问题 | 修复 |
|---|---|---|
| `scripts/cli_extract.py:147` | `model_call=None if args.stub else None` — 两分支相同 | 改为 `model_call=None` + 注释 |
| `scripts/path_safety.py:99-104` | `parent_run_root = path` 死代码 + 误导注释 | 删除 |
| `scripts/cli_compile.py:60-67` | `if staging_root.exists() and any(...):` 整段死代码 + `except Exception` 太宽 | 删死代码 + 精确异常 |
| `scripts/final_state_evaluator.py:104-115` | 永远 `shareable_anonymous`，私有构建也能 ready | 接受 `authorization_purpose` 参数 + 默认 `shareable_anonymous` |
| `scripts/cli_evaluate.py:120-122` | `auth_purpose` 未定义传给 evaluator | 加 `auth_purpose = "shareable_anonymous"`（spec §4.6 默认） |
| `SKILL.md` 7 步流程 | 步骤 6 写"生成单一写作 Skill" 与 spec §1 "6 阶段 Skill" 矛盾 | 改为 6 阶段导向 7 步（输入边界 / 阶段 B / 阶段 C / 隔离 / 阶段 E / 阶段 F / 阶段 G） |
| `policies/content-scan-policy.json:4` | `min_continuous_match: "TBD_locked_by_phase_a_calibration"` 占位 | 改为真实值 `32`，Ruling-E4 同步锁 / Ruling-E9 关闭占位 |
| `docs/superpowers/plans/2026-10-09-stage-c-extraction.md` | spec §4.3 "5 维都 approved" 与实现 "任一 approved" 偏离未文档化 | 加 Ruling-C9 文档化偏离理由（"不修改实现，但锁定行为；如未来要恢复需升 Ruling 并重写测试"） |

## 已知未修（不要求修）

| 位置 | 问题 | 备注 |
|---|---|---|
| `scripts/cli_extract.py:318` `compile_bundle` 调用未设 `bundle_id` | stage A schema 不要求 `bundle_id`——与 schema 一致；Ruling-C7 锁"再次通过 schema 校验"测试未实施 | 与 Ruling-C9 互不冲突 |
| `scripts/deterministic_compiler.py:191` | 用 `source_id` (12 hex) 当 bundle_id fallback | schema 接受；spec 字面偏离但 Ruling-E8 锁不动 schema |
| `scripts/cli_evaluate.py:76-78` | `source_id = bundle_id[:12]` | 信息丢失；compile-manifest schema 无 `source_id` 字段（Ruling-E8 锁） |
| `scripts/review_parser.py:46-49` | `ast.literal_eval` fallback | Ruling-C6 "严格 JSON" 偏离；可争议但当前行为 OK |
| `scripts/state_machine.py:33` | `BLOCKED_TRANSITIONS` 命名误导 | 命名规范问题，不影响功能 |
| `scripts/stage_context_validator.py:200` | `invalidated.discard("scan")` | 阶段 D Ruling 显式 lock；与 spec §4.6 偏离已 Ruling |
| `scripts/check_policy_gate.py:101` | `isinstance(x, int)` 接受 `bool` | edge case bool 误判 — 不会成为现实但代码易误导 |
| `schemas/release-manifest.schema.json` 字段名（`eval_report_hash`）vs stage A plan line 146 描述（`eval_summary_hash`） | schema 跟随 spec §4.9 权威；plan 文字 outdated | spec 是权威 |
| `policies/evaluation-policy.json` 5 字段与 spec §4.8 数值规则一致 | OK | — |
| 6 templates/stages/*.md 仍含 `primary_output: \|` block scalar | spec §4.5 表 1:1 字段；primary_output 字段名通过 | OK |

## 关键事实

- **518 / 518** unittest 通过（含 2 symlink 跳过）
- 7 个聚合门（`scripts/check_stage_{a..g}.py`）全部 exit 0
- 全程 0 模型调用（聚合门 grep `import socket/urllib/requests` 反向断言通过）
- 全程 0 复制 / 提交 / 输出真实来源正文

## 后续准入
- 项目最终验收门全部通过（stage A→G）
- SKILL.md 与 spec §1 一致
- stage A plan TBD 占位全部兑现（Ruling-E9）
- stage C 偏离 spec 实现有 Ruling-C9 文档化

## 关键文件位置
- spec: `docs/superpowers/specs/2026-10-09-wenfeng-skill-design.md`
- plans: `docs/superpowers/plans/2026-10-09-stage-{a,b,c,d,e,f,g}-*.md`
- reports: `docs/superpowers/reports/stage-{a,b,c,d,e,f,g}-2026-10-09.txt`
- this report: `docs/superpowers/reports/2026-10-09-second-pass-followup.md`
