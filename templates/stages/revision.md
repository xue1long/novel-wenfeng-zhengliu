---
name: revision
description: 基于 prose_draft、style_check 的校准报告与用户硬约束，输出 final_text 与 change_log；保持事实、事件顺序、视角与用户指定结尾。
stage_id: revision
contract_version: 0.1.0
trigger_examples:
  positive:
    - input: style_check 已产出 diagnostics + 用户硬约束
    - input: 用户要求根据 diagnostics 修订
  negative:
    - input: 用户要求加入新情节
    - input: 用户要求改写结尾
required_inputs:
  - stage_context_input_refs.prose_draft
  - stage_context_input_refs.style_check_report
  - stage_context_input_refs.hard_constraints
primary_output: |
  返回 final_text 与 change_log。
missing_input_behavior: block-and-explain
stop_conditions:
  - 修改后事件顺序变化
  - 修改后用户硬约束缺失
  - 用户指定结尾被改写
  - final_text 引用来源人物名
not_allowed:
  - 加入新情节
  - 改写用户指定结尾
  - 调用其他 Skill
  - 替换 stage_id
---

# revision

## 触发条件

- 正例：style_check 已产出 diagnostics + 用户硬约束；用户要求根据 diagnostics 修订。
- 负例：要求加入新情节；要求改写用户指定结尾。

## 必读输入

- `stage_context_input_refs.prose_draft`：prose_draft 输出。
- `stage_context_input_refs.style_check_report`：style_check 诊断报告。
- `stage_context_input_refs.hard_constraints`：用户硬约束。

## 主要输出

- `final_text`：最终正文。
- `change_log`：简短变更记录（哪条 diagnostic 被应用、改动范围）。

## 缺失输入行为

`block-and-explain`：缺任一必读输入时解释缺哪条。

## 停止条件

- 修改后事件顺序变化。
- 修改后用户硬约束缺失。
- 用户指定结尾被改写。
- final_text 引用来源人物名。

## 不做事项

- 不加入新情节。
- 不改写用户指定结尾。
- 不调用其他 Skill。
- 不替换 stage_id。