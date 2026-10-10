# 六阶段数据契约（Stage D 锁定）

本表把 spec §4.5 的"输入 / 输出 / 约束"翻译为机器可校验的契约，并标出哪些 key 在阶段间传递。

| 阶段 | 必读输入 (`stage_context_input_refs.*`) | 主要输出 | 约束 |
|---|---|---|---|
| write_entry | (none — 链顶) | stage-context | 不调用其他 Skill；不改写 user_brief |
| scene_design | user_brief, constraints | scene_plan | 不引入来源剧情；不引入来源人物 |
| character_beats | scene_plan, user_characters | character_beats | 不把来源人物关系映射到新人物；不输出正文 |
| prose_draft | scene_plan, character_beats, bundle_mechanisms | prose_draft | 只用 approved/limited 机制；不用 excluded 机制；不引入来源剧情或人物 |
| style_check | prose_draft, bundle_mechanisms, hard_constraints | diagnostics | 只诊断，不改正文，不添加情节 |
| revision | prose_draft, style_check_report, hard_constraints | final_text | 保持事实/事件顺序/视角/用户指定结尾；不引入来源人物 |

## 数据传递规则

每次阶段切换时，stage-context 把上一阶段的 `primary_output` 加入 `stage_snapshot.input_refs`，与 `bundle_id`、`trace_id`、`stage_id`、`retry_count` 一起进入下一阶段。

下列 key 在契约层视为总是可用：
- `user_brief` / `constraints` / `user_characters` / `hard_constraints` — 由 `write_entry` 入口录入
- `bundle_mechanisms` / `stage-context` — 由 bundle 与 wenfeng-distill 工厂 Skill 提供
- `style_check_report` ≡ `diagnostics` — `style_check` 的输出在 contract 层视为同义 key

## 边界

- 阶段 D **不**写可执行 Python；模板是契约，模型侧执行仍由 `wenfeng-distill` 工厂 Skill 完成。
- 契约层只检查**数据 context**；**handoff 合法性**（跨阶段跳号、return_to 等）由 `scripts/six_stage_state_machine.py`（任务 T3）负责。
- 模板自包含：任何模板不得在正文中引用其他模板路径；模板间数据通过 stage-context 传递。

## 引用

- 代码：[scripts/six_stage_contract.py](../../scripts/six_stage_contract.py)
- 单测：[tests/test_six_stage_contract.py](../../tests/test_six_stage_contract.py)
- 模板目录：[templates/stages/](../../templates/stages/)