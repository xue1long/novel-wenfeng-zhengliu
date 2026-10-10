---
name: character_beats
description: 基于 scene_design 的场景计划与用户提供的人物信息，输出 POV、动机、互动、对白功能与人物节拍，不把来源人物关系映射到新人物。
stage_id: character_beats
contract_version: 0.1.0
trigger_examples:
  positive:
    - input: scene_design 已产出 scene_goal / conflict / turn / resolution_plan
    - input: 用户要求为已有 scene 补充人物节拍
  negative:
    - input: scene_design 输出含来源人物名
    - input: 用户要求把来源小说人物改成新名后直接使用
required_inputs:
  - stage_context_input_refs.scene_plan
  - stage_context_input_refs.user_characters
primary_output: |
  返回 pov、motivation、interaction、dialogue_function、character_beats。
missing_input_behavior: block-and-explain
stop_conditions:
  - scene_plan 含来源人物名
  - user_characters 缺失动机或关系描述
  - character_beats 与 scene_plan 矛盾
not_allowed:
  - 把来源人物关系映射到新人物
  - 调用其他 Skill
  - 输出正文
  - 替换 stage_id
---

# character_beats

## 触发条件

- 正例：scene_design 已产出 scene_goal/conflict/turn/resolution_plan；用户要求为已有场景补充人物节拍。
- 负例：scene_design 输出含来源人物名；要求把来源人物改名直接复用。

## 必读输入

- `stage_context_input_refs.scene_plan`：scene_design 的输出。
- `stage_context_input_refs.user_characters`：用户提供的人物信息。

## 主要输出

- `pov`：视角。
- `motivation`：动机。
- `interaction`：互动。
- `dialogue_function`：对白功能。
- `character_beats`：人物节拍列表。

## 缺失输入行为

`block-and-explain`：缺任一必读输入时解释缺哪条。

## 停止条件

- scene_plan 含来源人物名。
- user_characters 缺动机或关系描述。
- character_beats 与 scene_plan 矛盾。

## 不做事项

- 不把来源人物关系映射到新人物。
- 不调用其他 Skill。
- 不输出正文。
- 不替换 stage_id。