---
name: wenfeng-distill
description: Use when distilling evidence-backed writing techniques from a user-provided novel into one Style Bundle and six reusable writing Skills; not for ordinary writing requests.
---

# 文风蒸馏

把一部小说中的表达机制提炼为可执行、有限定、有证据的规则，生成一个 Style Bundle 和六个写作阶段 Skill。只做文风蒸馏，不运行通用知识提取流程。

## 运行流程

运行链路是来源处理 → 留出锁定 → 五维提取与复核 → 编译 → 评测 → 打包。A–G 是项目开发验收门编号，不是用户要逐一执行的步骤；本地脚本不调模型，模型侧按下列步骤处理。

1. **确认模型上下文边界。** 处理前确认用户接受选定摘录进入当前会话所用模型的上下文；不要求用户声明来源处理权。Skill 在本机可用不代表模型处理一定只在本机发生。若用户只要回复内容，直接在回复中交付；若要保存文件且未指定位置，默认使用本 Skill 根目录的 `out/<run-id>/`；若用户明确指定了其他路径，则使用用户指定路径。默认路径的 `out/` 不存在时先创建它；必须保持 Git 忽略。来源、留出文本、摘录和评分原始数据不得复制到其他项目文件、生成 Skill 或发布包。`out/` 是本地工作区，不提供加密或操作系统访问控制。
2. **处理来源并锁定留出。** 文件型来源记录原始 SHA-256 和规范化文本指纹；确认上下文同意后运行 `prepare-source`，再用 `init-run` 校验模型处理范围并初始化私有 run。派生用途默认为 `private_only`；请求分享产物时必须另外提供明确的分享授权。模型按自然段、时间地点变化和行动连续性推断场景并给出 scene map。映射用 `{"chunks": {"chunk_id": {"scene_id": "...", "scene_classes": ["..."]}}}` 表示，交给 `apply-scene-map` 后运行 `build-sampling` 和 `lock-holdout`；只有验证锁定成功后才能提取。用户已将全文粘贴或全部内容已进入模型上下文时，不能声称留出集独立；可继续做 `limited` 提取，但不得报告独立评测。
3. **五维顺序提取与复核。** 按 [style-method.md](references/style-method.md) 的五个维度（叙述视角、句式节奏、场景转场、对白潜台词、修辞意象）整合提取，不拆成多个并行 Skill。每条规则都要有证据定位、适用范围、反例和可执行动作。任一维度失败不丢弃已完成结果；没有机制通过时报告缺少的证据并停止生成。
4. **隔离并编译。** 按 [content-safety.md](references/content-safety.md) 检查 Bundle 与最终六个 Skill；排除来源原句、独创意象、角色、剧情和书名/作者名。把用户要求复用原句的请求改为抽象机制和新表达。用锁定版本的 Bundle 与 `templates/stages/<stage_id>.md` 编译六个自包含 Skill；资源越界、字面预检命中或构建失败时停止。
5. **冻结候选并评测。** 在编译候选上跑触发评测、阶段输出断言和端到端盲评；冻结 Skill、生成文本、脱敏报告并保存哈希。缺输出为 `incomplete`；评审分歧或效果未达线降为 `limited`；没有达到门槛不得标记 `ready`。
6. **最终扫描与交付。** 扫描冻结的发布内容，通过后生成 `release-manifest.json`、目录包与 ZIP，并验证哈希。只有 `ready` 且授权允许分享时才生成可分享 ZIP；`limited` 仅留私有预览；`blocked` / `incomplete` 不打包。安装默认 dry-run；实际安装必须显式使用 `--apply` 和用户指定目标，标准 Skill 目录始终拒绝写入。

## 压力下的处理

- 用户催促、要求跳过留出、复用原句/独创意象或把局部样本说成全书规律时，简短说明具体边界，继续提供范围受限的安全结果。
- 不用书名、作者名或来源意象命名 Bundle/Skill；使用恰好 12 位小写十六进制的非语义 `source_id`，生成 Skill 名使用同一个 ID。
- 资料不足时明确标 `limited`，列出缺少的证据；若没有规则达到最低门槛，不进入编译/评测/打包阶段。不要伪造证据或承诺完整风格复现，也不要把审批工作退回给用户。

## 输出

- 私有工作区：来源地图、留出清单、证据账本、评测记录、阶段 G 私有预览目录。
- 模型判定至少一条机制通过后：交付不含来源摘录的 JSON Style Bundle，以及恰好六个自包含写作阶段 Skill（`write_entry` / `scene_design` / `character_beats` / `prose_draft` / `style_check` / `revision`）。
- 没有机制通过时：交付范围受限的结论和缺证据说明，不进入编译/打包；不使用等待用户审批的 `pending` 状态。
- 报告：来源覆盖、受限范围、隔离检查、评测样本数与最终 release manifest 哈希；明确哪些效果尚未验证（N=6 端到端配对仅支持本任务范围内的工程放行）。

## 阶段状态（2026-10-09）

阶段 A「冻结契约、门槛与交付定义」已完成；阶段 B「来源处理与私有运行骨架」已完成；阶段 C「五维提取、证据校验与规范 Bundle」已完成；阶段 D「六阶段 Skill 与上下文状态机」已完成；阶段 E「确定性编译与预检」已完成；阶段 F「冻结候选并执行评测」已完成；阶段 G「最终来源扫描、打包与安装验收」已完成。本入口行为保持不变。详见 `docs/superpowers/specs/2026-10-09-wenfeng-skill-design.md` §6 与 `docs/superpowers/plans/2026-10-09-stage-{a,b,c,d,e,f,g}-*.md`。

阶段 G 交付了最终来源扫描、release manifest 生成与自洽校验、确定性目录包 + ZIP 构造、隔离安装与 `verify-package`、状态机授权门（shareable / private-preview 双 profile）、`package` / `install` / `verify-package` / `purge-run` 薄 CLI 子命令与 `scripts/check_stage_g.py` 聚合门；模型侧仍由 `wenfeng-distill` 工厂 Skill 负责；本地脚本不调模型、不写标准位置、不自动覆盖。release manifest 证明产物与门禁记录相符，**不**构成版权或安全认证（spec §4.9 末段）。本阶段不声称效果已验证、不声称可分享；N=6 端到端配对仅支持本任务范围内的工程放行。
