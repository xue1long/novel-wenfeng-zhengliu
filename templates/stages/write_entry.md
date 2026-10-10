---
name: write_entry
description: 接收用户写作简报与硬约束，输出 trace_id、阶段顺序、约束清单与首阶段上下文，不调用其他 Skill。
stage_id: write_entry
contract_version: 0.1.0
trigger_examples:
  positive:
    - user_brief: 写一个 800 字的开场段落，主角走进旧书店
    - user_brief: 写一段侦探首次出现的长镜头，3 段以内
  negative:
    - user_brief: 把前面写过的章节翻译成中文
    - user_brief: 直接产出第三稿正文
required_inputs:
  - user_brief
  - hard_constraints
  - format_constraints
primary_output: |
  返回 trace_id、STAGE_ORDER 序列化、约束清单与首阶段 stage-context。
missing_input_behavior: block-and-explain
stop_conditions:
  - user_brief 为空
  - hard_constraints 与 brief 互相矛盾
  - requested_purpose 与 derivative_use 不匹配
not_allowed:
  - 改写或推断用户 brief
  - 调用其他 Skill
  - 引入来源剧情或来源人物
  - 替换 stage_id
---

# write_entry

总入口 Skill。接收用户写作简报，输出**只读**的 stage-context，不调用任何其他 Skill（spec §4.5 第一行）。

## 触发条件

- 正例：用户提供明确的写作意图（题材、长度、人物视角）与可验证的硬约束（事实清单、必须出现的句子）。
- 负例：纯翻译、改写既有文本、要求直接出正文。

## 必读输入

- `user_brief`：用户原始请求原文（不改写、不补全）。
- `hard_constraints`：用户声明的事实、必须保留的事件或结尾、不可替换的人物名。
- `format_constraints`：长度限制、段落数、语言、目标读者。

## 主要输出

- `trace_id`：本次写作链唯一标识。
- `STAGE_ORDER`：六个 stage_id 的有序数组。
- `constraints`：标准化后的约束清单。
- `stage-context`：含 `bundle_id`、`stage_id='write_entry'`、`stage_snapshot` 只记录输入引用与 `changed_fields=['trace_id','stage_order','constraints']`。

## 缺失输入行为

`block-and-explain`：返回错误并解释缺哪条输入；不进入后续阶段。

## 停止条件

- `user_brief` 为空。
- `hard_constraints` 互相矛盾。
- `requested_purpose` 不匹配 `authorization.scope.derivative_use`。

## 不做事项

- 不改写 `user_brief`。
- 不调用其他 Skill；六个 Skill 互相独立，调用顺序由 `wenfeng-distill` 工厂 Skill 按 stage-context 编排。
- 不引入来源剧情或来源人物。
- 不替换 stage_id。