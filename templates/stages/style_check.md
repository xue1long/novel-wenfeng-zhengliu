---
name: style_check
description: 对 prose_draft 的初稿与 Style Bundle 做按机制 ID 的诊断，输出诊断报告；只诊断，不擅自改正文或添加情节。
stage_id: style_check
contract_version: 0.1.0
trigger_examples:
  positive:
    - input: prose_draft 已产出初稿 + Style Bundle 已编译
    - input: revision 后再次校准
  negative:
    - input: 用户要求直接修订正文
    - input: 用户要求添加新情节
required_inputs:
  - stage_context_input_refs.prose_draft
  - stage_context_input_refs.bundle_mechanisms
  - stage_context_input_refs.hard_constraints
primary_output: |
  返回 diagnostics 列表，每条带 mechanism_id 与 evidence 引用。
missing_input_behavior: block-and-explain
stop_conditions:
  - prose_draft 含来源人物名
  - hard_constraints 与初稿不一致
  - diagnostics 为空且机制已应用
not_allowed:
  - 擅自改正文
  - 添加情节
  - 调用其他 Skill
  - 替换 stage_id
---

# style_check

## 触发条件

- 正例：prose_draft 已产出初稿 + Style Bundle 已编译；或在 revision 后再次校准。
- 负例：要求直接修订正文；要求添加新情节。

## 必读输入

- `stage_context_input_refs.prose_draft`：prose_draft 输出。
- `stage_context_input_refs.bundle_mechanisms`：Style Bundle 机制列表。
- `stage_context_input_refs.hard_constraints`：用户硬约束。

## 主要输出

- `diagnostics`：每条带 `mechanism_id`、`location`（初稿偏移）、`severity`（`ok` / `minor` / `major`）、`note`。

## 缺失输入行为

`block-and-explain`：缺任一必读输入时解释缺哪条。

## 停止条件

- prose_draft 含来源人物名。
- hard_constraints 与初稿不一致。
- diagnostics 为空且机制已应用（表示漏检）。

## 不做事项

- 不擅自改正文。
- 不添加情节。
- 不调用其他 Skill。
- 不替换 stage_id。