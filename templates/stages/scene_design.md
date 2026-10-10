---
name: scene_design
description: 基于 write_entry 的简报与约束清单，输出场景目标、冲突、行动、转折与收束计划，不引入来源剧情或来源人物。
stage_id: scene_design
contract_version: 0.1.0
trigger_examples:
  positive:
    - input: write_entry 已产出 trace_id + brief + constraints
    - input: 用户要求重新规划场景顺序
  negative:
    - input: 用户提供一段来源小说要求照搬
    - input: 用户要求输出最终正文
required_inputs:
  - stage_context_input_refs.user_brief
  - stage_context_input_refs.constraints
primary_output: |
  返回 scene_plan（含 scene_goal、conflict、turn、resolution_plan 四个字段），外加可选 scene_list。
missing_input_behavior: block-and-explain
stop_conditions:
  - user_brief 含来源剧情元素
  - constraints 含来源人物名
  - scene_goal 与 brief 不一致
not_allowed:
  - 引入来源剧情或来源人物
  - 输出最终正文
  - 调用其他 Skill
  - 替换 stage_id
---

# scene_design

根据 write_entry 的简报与约束清单，设计场景目标、冲突、行动、转折与收束计划。

## 触发条件

- 正例：write_entry 已产出 trace_id + brief + constraints；或用户明确要求重新规划场景。
- 负例：要求照搬来源小说或直接产出正文。

## 必读输入

- `stage_context_input_refs.user_brief`：来自 write_entry 的原始简报。
- `stage_context_input_refs.constraints`：约束清单。

## 主要输出

- `scene_goal`：场景目的。
- `conflict`：冲突点。
- `turn`：转折点。
- `resolution_plan`：收束计划。
- `scene_list`：可选的场景列表。

## 缺失输入行为

`block-and-explain`：缺少上述任一必读输入时，解释缺哪条。

## 停止条件

- brief 含来源剧情元素。
- constraints 含来源人物名。
- scene_goal 与 brief 不一致。

## 不做事项

- 不引入来源剧情或来源人物。
- 不输出最终正文。
- 不调用其他 Skill。
- 不替换 stage_id。