# 阶段二、三实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 `wenfeng-skill` 增加可靠的 Style Bundle 结构校验，并试点一个可独立调用的草稿修订 Skill。

**Architecture:** 校验器使用 Python 标准库读取现有 Bundle 形状，只检查可确定的字段、定位和证据门槛，不宣称语义安全。新增 `wenfeng-style-revision` Skill，接收用户草稿和已有证据范围写作指南，按其范围做诊断或有限修订；完整蒸馏入口保持原样。

**Tech Stack:** Python 3 标准库、Codex `SKILL.md`、Markdown。

**Spec:** `docs/superpowers/specs/2026-10-09-wenfeng-skill-design.md`

## Global Constraints

- 不复制、提交或输出来源正文、留出样本、证据摘录、书名、人物名或源名映射。
- 不增加运行依赖；验证样例使用合成内容。
- 模型自动判定规则的职责与输入授权边界保持不变。
- 阶段三每轮只试拆一个独立用户目标，不建立 Skill 间自动嵌套调用。
- 不初始化 Git 仓库，不安装新 Skill 到用户级目录。

## Review Focus

- `ready` Bundle 中有缺失声明维度或不足跨章节门槛的机制时必须拒绝。
- `limited` Bundle 可包含局部机制，但机制仍需至少两个独立场景支持。
- 坏 JSON、缺字段、错误 ID、无效行范围、重复机制 ID 均给出定位明确的错误。
- 校验器不能把结构合格误报为版权、来源隔离或语义安全合格。
- 修订 Skill 不能为了“像指南”而改动用户要求保留的事实、顺序或结尾，也不能在没有合适机会时硬加受限技巧。

### Task 1: Style Bundle 校验器

**Files:**
- Create: `tests/test_validate_bundle.py`
- Create: `scripts/validate_bundle.py`
- Modify: `README.md`

**Interfaces:**
- `validate_bundle(data: object) -> list[str]` 返回全部结构/门槛错误；空列表代表结构检查通过。
- CLI 接收一个 JSON 文件路径；通过返回码 `0`，校验失败返回非零并打印错误。
- 标准库 `unittest` 是唯一可运行自检入口，只使用合成数据。

- [x] 先写 `unittest` 用例：有效 `limited` Bundle 通过；缺字段、坏 JSON、重复 ID、错误证据定位、低证据 `model_approved` 和维度缺失的 `ready` Bundle 被拒绝。
- [x] 运行 `python -m unittest discover -s tests -v` 确认新用例按预期失败。
- [x] 实现最小校验器，不检查来源语义、内容相似度或虚构 `content_exclusions`。
- [x] 运行单测与 `python scripts/validate_bundle.py outputs/style-bundle-c5ef63446f47.json`；现有 Bundle 应通过且状态仍为 `limited`。
- [x] 在 README 说明命令、返回值和结构校验边界。

### Task 2: 修订模块基线

**Files:**
- No project files changed before baseline.
- Test inputs use fictional drafts and a synthetic evidence-scoped guide only.

- [x] 用独立新上下文运行三种任务：保持事实的轻修、缺少写作指南、局部技巧不适用时的诊断/修订。
- [x] 在设计稿中保存不含真实来源材料的匿名基线结果与观察到的具体偏差。
- [x] 基线缺少指南时出现无依据风格猜测；用户明确授权有界试拆，继续实现一个有针对性的修订 Skill。

### Task 3: 独立草稿修订 Skill 试点

**Files:**
- Create: `skills/wenfeng-style-revision/SKILL.md`

- [x] Task 2 暴露具体偏差，且修订用户目标有清晰独立输入/输出；依用户明示授权按该失败结果写入最小 Skill。
- [x] 用相同合成任务调用该 Skill，确认能保留事实/结尾、在缺指南时询问、跳过不适用的局部技巧。
- [x] 运行 `quick_validate.py` 检查新 Skill 的格式与命名。

### Task 4: 阶段状态与交付说明

**Files:**
- Modify: `docs/superpowers/specs/2026-10-09-wenfeng-skill-design.md`
- Modify: `README.md`

- [x] 记录本次显式启动覆盖了原阶段门，但不能被表述为阶段触发证据。
- [x] 记录已实现能力、验证结果、未完成的门槛和项目级试点 Skill 的状态。
- [x] 记录阶段完整退出仍需确认端到端入口回归；本轮没有宣称阶段二、三正式验收完成。

## Rulings

- **Ruling:** 用一个 `unittest` 自检入口代替脚本内 `--self-check` 分支 — 避免在生产校验器和自检入口重复维护同一验证逻辑 — 代价是自检命令需从项目根目录运行。
- **Ruling:** 阶段三仅试拆“已有写作指南的草稿修订”这一独立用户目标 — 它与来源分析有不同输入、触发条件和交付物 — 不据此拆分五个文风维度或完整蒸馏流程。
- **Ruling:** 按用户明确指令开展两个有界试点，即使真实运行次数未达到原进入门槛 — 该命令只授权当前校验器和一个修订模块试点 — 真实使用门槛对后续工具与拆分仍然有效。
