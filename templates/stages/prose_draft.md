---
name: prose_draft
description: 基于已确认的场景计划与人物节拍，应用 Style Bundle 中 approved/limited 机制，输出新故事初稿。
stage_id: prose_draft
contract_version: 0.1.0
trigger_examples:
  positive:
    - input: scene_design + character_beats + Style Bundle 都就绪
    - input: 用户在 revision 后要求基于校准报告重写初稿
  negative:
    - input: character_beats 含来源人物名
    - input: 用户要求使用被 excluded 的机制
required_inputs:
  - stage_context_input_refs.scene_plan
  - stage_context_input_refs.character_beats
  - stage_context_input_refs.bundle_mechanisms
primary_output: |
  返回 prose_draft（新故事初稿）与 mechanism_application_log（哪些机制被应用、范围）。
missing_input_behavior: block-and-explain
stop_conditions:
  - bundle_mechanisms 为空
  - bundle_mechanisms 含 excluded 机制被请求应用
  - 初稿加入未在 character_beats 的人物
not_allowed:
  - 应用 excluded 机制
  - 引入来源剧情或人物
  - 调用其他 Skill
  - 替换 stage_id
---

# prose_draft

## 触发条件

- 正例：scene_design + character_beats + Style Bundle 均就绪；或在 revision 后基于校准报告重写初稿。
- 负例：character_beats 含来源人物名；要求使用 excluded 机制。

## 必读输入

- `stage_context_input_refs.scene_plan`：scene_design 输出。
- `stage_context_input_refs.character_beats`：character_beats 输出。
- `stage_context_input_refs.bundle_mechanisms`：Style Bundle 中 approved 或 limited 的机制列表。

## 主要输出

- `prose_draft`：新故事初稿文本。
- `mechanism_application_log`：每条机制的 application_scope（仅适用范围内）。

## 缺失输入行为

`block-and-explain`：缺任一必读输入时解释缺哪条。

## 停止条件

- bundle_mechanisms 为空。
- 请求应用 excluded 机制。
- 初稿加入未在 character_beats 的人物。

## 不做事项

- 不应用 excluded 机制。
- 不引入来源剧情或人物。
- 不调用其他 Skill。
- 不替换 stage_id。