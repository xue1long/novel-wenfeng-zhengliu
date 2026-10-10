# 文风蒸馏六阶段系统设计说明

> 状态：设计修订稿，已获用户认可进入文档修订；尚未按本稿实现。用户审阅本稿并确认后，再编写实施计划。
>
> 目标变更：从“端到端蒸馏后生成一份写作 Skill”扩展为“抽取、编译、评测并分发六个独立阶段 Skill”的完整系统。本稿取代此前首版仅生成一个写作 Skill 的范围，不代表代码已完成。

## 1. 当前基线

项目空间为 D:/000/wenfeng-skill。它是从旧项目独立出来的文风蒸馏项目；D:/000/cangjie-skill-main 仅作只读参考，不迁入旧通用知识蒸馏流程。

截至 2026-10-09，项目内已有：

- wenfeng-distill 蒸馏入口及五维文风方法说明。
- JSON Style Bundle 模板、结构校验器及合成单元测试。
- 一个项目级草稿修订 Skill 试点。
- 一次真实小说的有限样本运行记录，产出一个 Style Bundle 和一个写作 Skill；抽样覆盖 18/54 章，评估为单次模型方向性评估，不能作为全书风格效果验收。

尚未实现：

- 可复用的来源分块、分层抽样和证据账本生成工具。
- 六个阶段的正式模板与阶段间数据契约。
- 从规范 Bundle 确定性生成六个 Skill 的编译器。
- 来源独立性扫描、盲评流程和端到端评测集。
- 六 Skill 的版本化发布包与干净环境安装验收。

以上试运行产物证明了流程可以探索，不代表本设计的系统级验收已通过。

## 1.1 cangjie 架构借鉴范围

本设计只借鉴 cangjie 的工程组织方式，不继承它面向通用知识蒸馏的产品流程：

- 借鉴 methodology / extractors / schemas / templates / scripts / tests / dist 分层，让方法、提取模块、数据契约、Skill 模板、确定性工具和发布产物各有边界。
- 借鉴 Bundle 作为单一事实源；派生 Skill 由规范 Bundle 和固定模板生成，不手工维护六份规则副本。
- 借鉴“薄 CLI + 确定性编译器”：CLI 只调度本地可重复工具，不调用模型；模型参与的抽取和评测仍由蒸馏流程负责。
- 借鉴编译到暂存目录、完整校验后再原子发布，以及触发测试与输出评测分离的做法。
- 不迁移 RIA-TV++ 通用方法、知识卡片类型、Capability Bundle 字段、promotion/routing、single/pack、通用 update/repair/rollback/benchmark、网站或 Registry。
- 本项目继续采用文风机制 JSON Bundle、五个文风维度、六个固定写作阶段、私有来源隔离和标准库实现；不以复用旧流程为目标。

## 2. 目标

给定一部获准用于本次处理、且授权范围覆盖目标模型处理方式及预期产物用途的 TXT 或 Markdown 小说，系统应能：

1. 在用户指定的私有运行目录建立来源/分块清单、留出记录、私有证据账本和可续跑的步骤日志。
2. 按可复现的五维提取协议生成经证据定位校验的规范 Style Bundle，并区分跨章节规律、局部候选和淘汰项。
3. 通过固定模板把 Bundle 确定性编译成六个可独立调用的写作阶段 Skill。
4. 对输入、机制证据、内容独立性、Skill 触发、输出质量、完整链路和发布包执行有明确门槛的检查。
5. 生成版本化本地目录与可携带发布包，附上脱敏的评测摘要和完整性清单；不把来源正文、留出文本或私有账本带入发布物。

系统交付与某一部作品的蒸馏结果分开验收：系统完整表示流程、契约和工具均可用；某次运行若证据或预算不足，应标记 limited/incomplete，不得因此宣称文风效果已验证。

蒸馏工厂入口 wenfeng-distill 与每部小说生成的六个写作阶段 Skill 是两类不同产物。前者负责从来源到 Bundle；后者负责在新故事写作时消费 Bundle。

## 3. 范围与约束

### 3.1 首个完整版本包含

- 单部来源、UTF-8 TXT/Markdown；不做跨作品作者风格归纳。
- 五个独立的机制提取模块：叙述视角与叙述者口吻、句式与段落节奏、场景构造与转场、对白与潜台词、修辞与意象组织。各模块使用统一候选机制契约，由工厂 Skill 顺序编排。
- 六个写作阶段 Skill：总入口、场景设计、人物节拍、语言落笔、文风校准、成稿修订。
- 一个规范 JSON Bundle、来源/分块/运行清单、阶段上下文契约、确定性编译器、内容独立性门禁、可复现评测材料和版本化发布包。
- 薄本地 CLI 负责初始化、校验、编译、扫描、报告、打包和显式安装；模型抽取与模型评分由工厂 Skill 按协议执行，CLI 不调用模型。
- 使用 Python 标准库、JSON、Markdown 和本地 Codex Skill 约定。无新增运行时依赖。

### 3.2 明确不做

- 不保留 cangjie 的通用知识蒸馏流程，不迁移 RIA-TV++、通用知识抽取器、知识卡片、Capability Bundle 字段、promotion/routing、single/pack、通用 update/repair/rollback/benchmark、网站、Registry 或知识库功能。
- 不建立数据库、云服务、统计平台、通用工作流引擎或多 Agent 提取系统。
- 不支持 EPUB/PDF、多来源合并或自动网络抓取。
- 不把“模型判断通过”描述成统计显著、版权认证或绝对的语义安全保证。
- 不把模型调用塞进 CLI 或编译器。模型参与的抽取和评测由 wenfeng-distill 工厂 Skill 按版本化提示和契约执行；本地脚本负责输入输出、校验、哈希、扫描、报告与发布。
- 不自动安装或覆盖用户级 Skill。安装必须由用户显式运行命令并指定目标；不提供远程 Registry。
- 不要求用户逐条判断风格机制。来源使用授权是启动/共享的前置条件，不属于风格候选裁决。

六个写作阶段由用户显式调用，并通过同一 trace_id 和阶段上下文交接。总入口负责准备计划和上下文，不假装能自动调用其他 Skill。五个提取模块由工厂 Skill 顺序执行，不以并行 Agent 作为首版能力。

## 4. 系统结构

### 4.1 私有运行目录

每次蒸馏在独立私有 run root 中运行，默认位置为 wenfeng-skill 根目录的 `out/<run-id>/`；`/out/` 必须被 Git 忽略。该目录是本地工作区，不提供加密或操作系统访问控制。来源正文不得进入其他项目文件、生成 Skill 或发布目录。run manifest 至少记录：

- run_id、无语义随机 source_id、来源文件指纹、文件格式、编码、规范化/解析器版本。
- 处理记录：用户同意的模型处理范围；派生产物用途默认 `private_only`。只有请求分享时才需显式提供 `shareable_*` 用途授权。系统不要求用户声明来源处理权，记录也不构成系统对合法性的验证或认证。
- 处理状态、model-budget-policy 版本、扫描预算数值（最大请求数、累计输入 token、单批 token 上限及超限策略）、创建与保留期限；每个受支持模型必须有固定默认预算 profile，缺少数值 profile 时不得标记 ready。run 到期后不自动删除；支持显式安全清理，并记录清理结果。
- 步骤日志：step_id、输入哈希、提示/模板版本、模型标识、输出路径与哈希、状态、重试次数和错误类型，支持幂等续跑。

chunk manifest 保存稳定 chunk_id、章节/场景定位、源文件字符偏移、边界置信度、窗口哈希和分块版本，不保存正文。source map 保存章节、场景、抽样位置及覆盖矩阵；holdout manifest 在提取前封存场景 ID 与来源定位；evidence ledger 保存私有短摘录、位置、适用范围、反例和判定状态。source exclusions 只供构建期扫描。

证据摘录单条最多 200 个 Unicode 码点。模型处理同意记录缺失或不覆盖当前模型处理方式时，不启动模型提取；不允许分享派生产物时，最多生成私有本地预览。完整原文及留出文本只允许保存在 `out/<run-id>/`，不得进入其他项目文件、生成 Skill 或发布包。source-manifest.schema.json、chunk-manifest.schema.json 和 run-manifest.schema.json 分别定义这些契约。

### 4.2 抽样与留出

在阅读用于提取的正文前先锁定留出集。抽样需覆盖开篇、人物出场、日常、对话、冲突/高潮、揭秘和章末等场景类型，并记录前、中、后段覆盖情况。超长章节在自然叙事边界切块，单个提取窗口默认不超过 5,000 个 Unicode 码点；不得在句中截断。

分块器对同一来源指纹和版本必须生成稳定 chunk_id 与定位；边界置信度低、未识别或未覆盖的部分显式记录。source map 保存未覆盖场景类型和低置信边界。抽样不足时 Bundle 降为 limited，不用均匀章节采样冒充全书代表性。来源指纹或规范化/分块器版本变化后，chunk manifest、抽样图和留出集必须重建。

### 4.3 五维机制提取

五个提取器是独立的方法模块，不是并行 Agent。wenfeng-distill 工厂 Skill 按固定顺序对每个维度执行“提取 → 结构/证据校验 → 结构化复核 → 写入检查点”，再合并候选、跨维度去重并计算状态。模型交互由工厂 Skill 根据版本化提示完成；脚本不调用模型。任一维度失败不丢弃已完成结果。

candidate-mechanism.schema.json 固定每条候选的 mechanism_id、dimension、通用规则、适用条件、动作步骤、禁用条件、stage_bindings、证据引用、反例引用、提取提示版本和复核状态。候选只存 chunk_id、场景/章节 ID、字符偏移及摘录哈希；完整摘录保存在私有 evidence ledger。字符偏移统一采用规范化文本上的 Unicode 码点闭开区间 [start,end)，并记录规范化版本。校验器依据来源指纹、规范化版本和偏移重新计算摘录哈希，拒绝越界、错位或对不上来源的证据引用。

每个维度运行以下步骤：

1. 提取器根据抽样窗口输出候选机制和可定位正反证据，写入私有候选文件。
2. 确定性校验 schema、证据引用、独立场景/章节计数、重复 ID 和必需字段。
3. 复核提示只针对候选与其正反证据，按版本化量表检查规则是否被证据支持、反例/替代解释是否处理、规则是否可执行且不含来源专属表达；输出 supported、limited 或 unsupported 及结构化理由，不让用户逐条裁决。
4. 规则引擎合并模型复核结果与机械证据门槛，决定 Bundle 状态：
   - approved：至少 3 个独立场景、覆盖至少 2 章，证据引用有效且复核为 supported。
   - limited：至少 2 个独立场景、证据引用有效且复核为 limited；只允许按候选声明的局部范围使用。
   - excluded：引用无效、证据不足、复核 unsupported、重复或冲突无法消解。
5. 每个维度完成即写步骤日志与哈希检查点。失败最多自动重试 3 次；仍失败则记为 incomplete，可从未完成步骤续跑，不改写已通过哈希校验的结果。

五个声明维度都需有 approved 机制时 Bundle 才能标记 ready；否则为 limited。没有任何机制通过门槛时，不编译可分发 Skill。模型复核属于自动化判定证据，不得描述成独立人类验证。

### 4.4 Bundle 与来源隔离

Style Bundle 是六个 Skill 的唯一事实源，使用 JSON。至少包含 schema_version、bundle_version、source_id、evidence_status、claimed_dimensions、mechanisms、stage_bindings、content_exclusions 和 evaluation_ref。stage_bindings 固定映射六个 stage_id 到 mechanism_id 列表；允许阶段列表为空，但不得引用缺失或 excluded 的机制。schema 校验类型、必需项、枚举和内部引用；跨文件定位由独立校验器验证。

source-manifest、chunk-manifest、run-manifest、candidate-mechanism、evidence-ledger、style-bundle、stage-context、eval-suite、eval-report、content-scan-report、compile-manifest 和 release-manifest 各有独立 schema。运行期私有证据、写作上下文、评测私钥和发布元数据不得混入 Bundle。

source_id 是随机生成的无语义 12 位小写十六进制 ID，不从书名、作者名或其哈希派生。Bundle 和 Skill 不含来源原句、摘录、书名、作者名、人物名、剧情事件链或独创意象描述。来源专名和表达只留在私有 exclusions 中；发布物的 content_exclusions 只列通用类别。

内容独立性检查分预检与最终门：

1. 编译预检：本地确定性扫描完整来源与冻结的 Bundle/六个 Skill，精确私有标记或达到策略阈值的连续匹配直接阻断，避免把明显复用文本送入评测或暂存为可发布包。
2. 最终门：所有 Skill、评测输出和聚合报告冻结后，再对完整来源分块清单和全部候选发布内容做语义风险检查；逐窗口记录 checked、risk、inconclusive 或 failed。模型语义判断只作风险筛查，不构成版权或安全保证。

字面相似策略同时记录候选唯一 12 码点 shingle 命中率和最长连续匹配长度，避免只用可被通用文本稀释的单一比例。精确私有标记/达到 content-scan-policy 中锁定的连续匹配长度是硬阻断。阶段 A 的固定控制集至少包含 20 个来源复制正例和 20 个非来源原创/通用语言负例。来源正例在抽样/留出锁定时单独分区，只用于扫描器校准，不送入机制提取或写作评测，并只保存在私有 run；任何依据留出或扫描结果修改机制的版本都必须重新锁定留出集。精确复制正例必须 100% 阻断，负例误阻断不超过 1/20，未达标则策略校准失败且不能标记 ready/shareable。相似度阈值在阶段 A 校准并锁定版本；阈值变更必须升策略版本、重扫全部冻结产物。该控制集只验证扫描器回归，不证明对任意改写或语义复用的检出率。

语义扫描按模型上下文上限切批，预估请求数和输入 token 后与 run manifest 中的数值预算比较。窗口结果逐批落盘并按 ID 幂等；中断可续跑，缺窗、失败批次或预算耗尽均不得静默跳过。所有窗口 clear 才标记 semantic_clear；任一窗口 risk 视为硬风险并 blocked，inconclusive 或预算耗尽降为 limited，失败批次记 incomplete 并允许续跑。即使全覆盖也不得声称语义审查绝对安全。

发布最终门检查冻结 Bundle、六个 Skill、评测生成文本、脱敏评测报告和包内说明。任何硬阻断、未授权处理、来源正文/私有账本/解盲映射泄漏都会阻断发布。

### 4.5 六阶段 Skill 契约

每个模板有独立 SKILL.md、明确触发条件、正向和负向示例、必需输入、唯一主要输出、缺失输入行为和停止条件。stage_id 固定为 write_entry、scene_design、character_beats、prose_draft、style_check、revision；这些 ID 同时用于模板目录、Bundle 绑定、stage-context 和评测用例。

| 阶段 | 输入 | 输出 | 约束 |
|---|---|---|---|
| 总入口 | 用户写作简报、格式/事实约束 | trace_id、阶段顺序、约束清单、首阶段上下文 | 不改写用户简报，不调用其他 Skill |
| 场景设计 | 简报、约束清单 | 场景目标、冲突、行动、转折与收束计划 | 不引入来源剧情或来源人物 |
| 人物节拍 | 场景计划、用户提供的人物信息 | POV、动机、互动、对白功能和人物节拍 | 不把来源人物关系映射到新人物 |
| 语言落笔 | 已确认的场景计划和人物节拍 | 新故事初稿 | 只应用适用的 approved/limited 机制，limited 机制需保持局部 |
| 文风校准 | 初稿、机制 Bundle、用户硬约束 | 按机制 ID 定位的诊断报告 | 只诊断，不擅自改正文或添加情节 |
| 成稿修订 | 初稿、校准报告、原始硬约束 | 最终正文和简短变更记录 | 保持事实、事件顺序、视角与用户指定结尾 |

不同阶段不得随机重解释上游数据。冲突应指出发生冲突的字段、阶段和机制，并定向返回相关上游阶段。

### 4.6 stage-context 与状态/失效规则

每次写作链共用 trace_id。stage-context 至少包含 contract_version、trace_id、bundle_id、stage_id、retry_count、stage_snapshot、error_report、next_stage 和 return_to。stage_snapshot 只记录只读输入/输出引用、哈希和 changed_fields，不复制来源正文；error_report 包含 error_type、conflicting_stage、mechanism_id 和说明。

六阶段允许的正常边为 write_entry → scene_design → character_beats → prose_draft → style_check → revision → completed。return_to 必须指向当前阶段之前的合法阶段；回退后只重跑受影响阶段及下游，不自动重跑整链。初次调用 retry_count 为 0，每次回退递增，最多 3 次；耗尽后记为 incomplete，输出失败报告。schema 校验非法跳转、非递增计数或越界引用。

run 状态固定为 incomplete、blocked、limited、ready：
- incomplete：可恢复的运行错误或未完成检查；禁止发布，允许按日志续跑。
- blocked：授权缺失/超范围、证据引用造假、精确/长段来源复用、语义扫描判为 risk 或结构校验失败；禁止编译或分享。
- limited：运行完成但证据、语义扫描覆盖/结论不确定或效果评测未达到 ready 门槛；只允许私有预览，不允许 shareable 发布。
- ready：所有来源、抽取、编译、评测、内容安全和授权门均通过。可分享资格还要求授权记录明确允许派生产物分享。

失效规则按输入哈希传播：来源/规范化/分块版本变化使抽样、留出和所有下游失效；提取提示/复核模型/候选 schema 变化使提取结果及其下游失效；Bundle/模板/编译器变化使编译、评测、扫描与发布失效；评分模型/量表变化使评测与发布失效；语义扫描模型或策略变化使受影响窗口的扫描和发布失效。单纯增加扫描预算不使已完成且输入/提示/模型哈希一致的窗口失效，只续跑未完成窗口。manifest 保存每项依赖哈希和失效原因。

### 4.7 薄 CLI 与确定性编译器

wenfeng-distill 工厂 Skill 执行模型提取/复核/评分；CLI 不调用模型。CLI 命令限定为：

- doctor、init-run、prepare-source：环境诊断、授权前置条件检查、来源指纹/规范化/稳定分块与清单生成。
- validate-extraction、validate-bundle、check-content [--resume]：schema、证据偏移/摘录哈希、机制计数、引用、确定性字面扫描与扫描覆盖状态校验；语义扫描按窗口检查点续跑。
- compile、validate-dist：将通过门槛的 Bundle 和六份模板编译到私有 staging，静态验证阶段包。
- eval-report：读取模型评分记录，运行机械断言、分数聚合和状态计算；不生成模型评分。
- purge-run --dry-run、purge-run --confirm：只清理指定 run root 内、经路径 containment 校验的私有运行目录；展示预览后必须显式确认，不自动清理其他路径。
- package --scope private-preview|shareable、verify-package：生成或校验目录包与确定性 ZIP；shareable 仅在 ready 且授权允许分享时可用，limited 只能生成私有预览。
- install --dry-run、install --scope user --target <path>：显式预览或安装；不自动写用户级目录，不覆盖已有 Skill。

编译流程为：校验 Bundle、模板、stage_bindings 和授权状态；在私有 staging 生成恰好六个自包含 Skill；执行 frontmatter/UTF-8/链接/资源 containment/未声明文件/二进制文件/符号链接逃逸/名称与 stage_id 对应检查；对冻结输出执行字面预检。每阶段规则副本哈希不一致、资源越界或任何硬门失败都拒绝生成候选包。

相同规范 Bundle、模板、工具和 schema 版本必须生成相同 Skill 字节及相同的确定性 manifest 字段；排序固定、UTF-8、LF、无生成时间字段。ZIP 内文件按路径排序并规范时间戳。模型评分和评测摘要单独记录，不混入编译器的可复现输入。

打包与安装使用同卷 staging、预检和发布锁；目标存在即失败，不静默覆盖。安装先检查六个目标名和全部资源，再暂存六个目录；提交中断时清理本次新建目录并保留已有内容。--dry-run 报告目标路径、冲突和将写入文件。任何安装动作都要求明确的命令调用，不由 compile/package 隐式触发。

### 4.8 评测系统

eval-suite schema 把触发、输出、完整链路和评审量表分开。每次结果固定模型标识/版本、提示版本、生成参数、预算、工具版本、用例版本、输入/输出哈希、完成状态和未完成原因。

1. **Bundle 与契约门**：Bundle 字段、证据定位、状态门槛、阶段绑定和六个 Skill 自包含/静态检查必须 100% 通过。
2. **触发评测**：每个阶段至少 10 个应触发、10 个不应触发、5 个相邻能力/边界用例；各阶段 precision 与 recall 均不低于 0.90。缺少必需输入、负向示例和误触发必须纳入用例。
3. **阶段输出评测**：六个阶段各覆盖正常输入、缺失输入、负向规则和停止条件。schema、必需输出、用户硬约束等机械断言必须 100% 通过；缺输出、格式错误或运行中断一律为 incomplete，不计通过。
4. **端到端盲评**：至少 6 组相同简报的基线/六阶段配对，覆盖至少 3 类场景。两组候选使用同一模型版本和生成参数、同一简报/硬约束/输出长度与总 token 预算；基线不获得来源或 Bundle。候选随机匿名、随机顺序并冻结后，两个独立评分上下文看到相同的脱敏机制量表和写作约束（不看来源原文/书名/作者名），按 1–5 分评风格贴合、文本质量和约束遵循。

端到端“效果达标”须同时满足：六组中至少四组风格贴合优于基线，配对差值中位数至少 +0.5 分，Skill 输出风格贴合中位数至少 4 分；文本质量相对基线的配对差值中位数不得低于 -0.5 分；硬约束和内容独立性无失败。两组评分在任一维度相差超过 1 分时，该维度记为不确定，运行降为 limited。若硬性契约/约束失败则阻断；结果未达到效果门但无硬失败时仅能私有 limited 预览，不得宣传已验证有效。

N=6 只支持本评测任务范围内的工程放行，不支持统计显著性或普遍有效声明。调参后使用过的留出集不能作为独立验收集；新版本必须重新锁定留出集。盲评解盲映射、逐案例评测文本和评分密钥留在私有目录；发布时只带脱敏聚合摘要及其哈希。

### 4.9 分发

首版分发定义为可携带的本地发布包，不建设网站或远程 Registry。ready 且授权允许分享的版本生成 dist/<source_id>/<bundle_version>/ 目录和确定性 ZIP。包内固定包含六个自包含 Skill 目录、README、release-manifest.json、compile-manifest.json、脱敏的聚合评测摘要和安装说明。

release manifest 记录 Bundle/模板/工具/schema 版本、六个 Skill 哈希、ZIP 哈希、授权用途标记、触发/输出/端到端评测状态及评测摘要哈希、最终内容扫描策略版本/覆盖率/报告哈希、兼容目标和发布状态。它证明产物与门禁记录相符，不构成版权或安全认证。

不含来源正文、证据短摘录、留出文本、私有 source exclusions、逐案例评测文本、评分密钥或解盲映射。limited 仅生成 run 私有预览，不生成可分享 ZIP；blocked/incomplete 不进入 dist。

install --dry-run 和显式 install --scope user --target <path> 支持隔离验证和用户级安装。安装拒绝同名覆盖，用户可先通过 dry-run 复核目标；更新发布为新版本，不自动卸载旧版。ZIP 可手动传递给其他使用者，首版不提供托管分发服务。

## 5. 建议项目结构

    wenfeng-skill/
    ├── SKILL.md
    ├── methodology/
    │   ├── source-intake.md
    │   ├── sampling-and-holdout.md
    │   ├── evidence-and-decisions.md
    │   ├── content-independence.md
    │   └── evaluation-and-release.md
    ├── extractors/
    │   ├── narrative-voice.md
    │   ├── sentence-rhythm.md
    │   ├── scene-transition.md
    │   ├── dialogue-subtext.md
    │   └── imagery-rhetoric.md
    ├── schemas/
    │   ├── source-manifest.schema.json
    │   ├── chunk-manifest.schema.json
    │   ├── run-manifest.schema.json
    │   ├── candidate-mechanism.schema.json
    │   ├── evidence-ledger.schema.json
    │   ├── style-bundle.schema.json
    │   ├── stage-context.schema.json
    │   ├── eval-suite.schema.json
    │   ├── eval-report.schema.json
    │   ├── content-scan-report.schema.json
    │   ├── compile-manifest.schema.json
    │   └── release-manifest.schema.json
    ├── policies/
    │   ├── evaluation-policy.json
    │   ├── content-scan-policy.json
    │   └── model-budget-policy.json
    ├── templates/
    │   └── stages/
    │       ├── write-entry.md
    │       ├── scene-design.md
    │       ├── character-beats.md
    │       ├── prose-draft.md
    │       ├── style-check.md
    │       └── revision.md
    ├── scripts/
    │   ├── cli.py
    │   ├── prepare_source.py
    │   ├── validate_extraction.py
    │   ├── validate_bundle.py
    │   ├── check_content_independence.py
    │   ├── compile_skills.py
    │   ├── validate_dist.py
    │   ├── report_evals.py
    │   ├── package_release.py
    │   └── install_skills.py
    ├── evals/
    │   ├── trigger-cases.json
    │   ├── output-cases.json
    │   ├── end-to-end-tasks.json
    │   └── content-scan-controls.json
    ├── tests/
    │   ├── test_source_contracts.py
    │   ├── test_evidence_references.py
    │   ├── test_run_resume.py
    │   ├── test_run_purge_safety.py
    │   ├── test_stage_transitions.py
    │   ├── test_bundle_validation.py
    │   ├── test_content_scan_controls.py
    │   ├── test_compile_resources.py
    │   ├── test_compile_reproducibility.py
    │   ├── test_eval_gates.py
    │   ├── test_package_integrity.py
    │   └── test_install_transaction.py
    ├── references/
    └── dist/

五维提取与模型评分通过工厂 Skill 的版本化提示执行；脚本不存模型密钥、不发起模型请求。每部作品的正文、账本、留出、逐案例评分和解盲映射留在项目外的私有 run。项目中的 evals 只放原创测试、断言和合成扫描控制；每个 run 的 20 个来源复制正例从该 run 来源生成并只存私有目录，绝不写回项目。

## 6. 分阶段实施与验收门

### 阶段 A：冻结契约、门槛与交付定义

冻结来源授权字段、run journal、candidate/evidence/Bundle/stage-context/eval/report/scan/compile/release schemas；固定有限状态、内容扫描控制集、评测阈值、每个支持模型的数值预算 profile、ZIP 内容和安装行为；没有数值预算 profile 的模型不能标记 ready。验收：状态转移表、哈希失效规则、各门的输入/输出和阻断条件无矛盾；测试夹具覆盖正常、失败、超预算、断点续跑和授权不足。

### 阶段 B：来源处理与私有运行骨架

实现模型处理同意前置校验、来源指纹/规范化、稳定分块、抽样覆盖、预锁留出、run journal 和语义扫描预算预估。验收：相同来源及版本生成稳定 ID/定位；来源或处理器变化使下游失效；模型处理同意缺失不调用模型；私有用途默认 `private_only`，分享用途仍需显式授权；预算估算可解释，窗口清单完整且可续跑。

### 阶段 C：五维提取、证据校验与规范 Bundle

实现五个顺序提取模块、结构化复核提示、候选和账本 schema、证据偏移/哈希校验、机制计数/去重和自动状态合并。验收：模型误报的偏移不能通过；复制、错位、重复、反例不足、部分维度失败、模型超时和续跑均有合成用例；任何用户都无需逐条裁决候选机制。

### 阶段 D：六阶段 Skill 与上下文状态机

实现六个自包含模板、明确触发正负例、输入输出 schema、合法 handoff 图、回退规则和三次熔断。验收：六阶段逐一通过正向/负向触发、缺输入、输出结构、合法跳转和非法跳转用例；下游引用失效时不能继续写作。

### 阶段 E：确定性编译与预检

实现薄 CLI、Bundle 验证、机制投影、自包含构建、路径 containment、字节/section 哈希、并发锁和私有 staging。先执行静态包校验及确定性字面预检，不发布 dist。验收：重复构建完全一致；副本被改、路径逃逸、硬性来源命中或目标冲突均阻断；失败 staging 不被识别成版本。

### 阶段 F：冻结候选并执行评测

在阶段 E 候选上执行分阶段触发测试、输出机械断言和盲评端到端对照；冻结全部 Skill、评测生成文本和脱敏报告并保存哈希。验收：触发 precision/recall 和端到端效果门逐项有报告；缺输出为 incomplete；评审不一致或效果未达线自动降为 limited；没有达到门槛不得标记 ready。

### 阶段 G：最终来源扫描、打包与安装验收

对阶段 F 冻结的全部发布内容执行最终字面和语义扫描；预算不足时可续跑，未覆盖不能标 ready。通过后生成 release manifest、脱敏评测摘要、确定性目录包和 ZIP，验证哈希，再做隔离安装及用户级 dry-run。验收：来源窗口覆盖率、扫描决定和 eval 报告哈希可追溯；只有 ready 且授权允许分享时生成 shareable ZIP；limited 仅留私有预览；正式用户级安装必须单独显式执行。

依赖顺序为 A → B → C → D → E → F → G。各阶段门未通过时保留私有检查点并阻止下游，不将“可编译”误报成“效果达标”或“可分享”。

## 7. 风险与边界

- 来源授权采用用户声明而非系统法律判断：授权范围不含模型处理或分享时自动限制/阻断；系统不提供版权认证。
- 模型可能编造机制或引用：偏移、摘录哈希、来源指纹、计数和 schema 由本地确定性工具验证；模型复核不冒充人类验证。
- 全书语义扫描受模型上下文、费用和失败影响：预估预算、窗口级检查点、幂等续跑；缺窗、预算耗尽或不确定自动降级，不能标 ready/shareable。
- 文本相似度可能误报通用表达，也可能漏掉改写：阈值由固定控制集校准并版本化，精确命中和明确长段复用作为硬阻断，语义检查只作风险门，不保证安全。
- 触发和质量评测仍是小样本、模型评分：固定基线和设置、双盲独立评分、硬约束断言，并将结论限制在本评测范围，不声称统计显著或普遍有效。
- 六 Skill 规则漂移由 Bundle 单一事实源、哈希和最终包校验控制；流程回退由 stage-context 的合法跳转、输入哈希失效和三次熔断控制。
- 本地 Skill 不保证推理只在本地发生；模型上下文范围在授权声明中明确，默认不把来源正文写入项目或发布包。
- 首版只做可携带 ZIP 和本地显式安装，不做网站、Registry、CI、数据库或通用工作流引擎。

## 8. 最终系统验收

只有同时满足以下条件，才称为“六阶段文风蒸馏系统已交付”：

- 来源授权范围已记录并覆盖模型处理；证据引用通过偏移与摘录哈希校验，提取结果可续跑且可追溯。
- 六个写作阶段 Skill 均可独立发现和调用，触发、负例、输入输出、停止条件和合法 handoff 均通过契约测试。
- 同一 Bundle、模板、schema 和工具版本能确定性编译成恰好六个自包含 Skill；资源越界、内容硬命中或包校验失败阻断发布。
- 各阶段触发 precision/recall 达到门槛；输出机械断言全通过；端到端盲评达到预注册效果门，或明确将该次运行标为 limited 且不生成可分享包。
- 全来源语义扫描每个窗口有状态；ready/shareable 要求完整覆盖且无风险/不确定项。覆盖不足、预算耗尽或模型错误可续跑，未完成时不能标 ready。
- 可分享版本授权范围允许分享，并带有 ZIP/目录哈希、脱敏评测报告哈希、内容扫描策略和覆盖率；私有正文、证据、逐案例输出和解盲材料不进入包。
- 隔离安装和用户级 dry-run 验收通过；实际用户级安装只有显式命令触发，不由编译/打包自动完成。

## 阶段 A 完成报告（2026-10-09）

阶段 A「冻结契约、门槛与交付定义」已完成验收。本阶段仅交付契约与只读门禁，不启动来源抽取、Skill 编译、内容扫描或评测；`wenfeng-distill` 入口行为保持原样。本阶段不声称效果已验证、不声称可分享。

### 交付清单

- 13 个 JSON Schema（`schemas/*.schema.json`，Draft 2020-12；自写 vendored 校验器在 `vendor/json_schema_validate.py`，扩展 `x-wenfengRange` / `x-wenfengCodepointMax`，详见 `schemas/_meta.json`）。
- 13 个 example（`schemas/examples/*.example.json`），均通过各自 schema。
- 跨文件引用检查器 `scripts/check_bundle_cross_refs.py` 补足 vendored 校验器不实现的跨文件解析。
- 3 份 policy 文件（`policies/evaluation-policy.json`、`content-scan-policy.json`、`model-budget-policy.json`），对应只读门禁 `scripts/check_policy_gate.py`。
- 状态机 `scripts/state_machine.py` 与哈希失效规则 `scripts/invalidation_rules.py`，人读表在 `docs/contracts/{state-machine.md,invalidation-rules.md}`。
- 端到端盲评效果门计算 `scripts/effect_gate.py`（spec §4.8 数值规则）。
- 阶段 A 聚合验收 `scripts/check_stage_a.py` 与 128 个 unittest 用例（`tests/test_*.py`）；聚合报告 `docs/superpowers/reports/stage-a-2026-10-09.txt`。

### 显式不做（留给后续阶段）

- 不实现来源授权前置、来源指纹与规范化、稳定分块、抽样覆盖、预锁留出、run journal、语义扫描预算预估（**阶段 B**）。
- 不实现五维顺序提取、结构化复核提示、机制合并（**阶段 C**）。
- 不实现六个写作阶段 Skill 模板与 stage-context 状态机（**阶段 D**）。
- 不实现薄 CLI、Bundle 编译、staging、自包含构建、字面预检（**阶段 E**）。
- 不实现分阶段触发评测、输出机械断言、端到端盲评（**阶段 F**）。
- 不实现最终来源扫描、release-manifest、确定性 ZIP、隔离安装（**阶段 G**）。

### 后续准入

阶段 B 启动前必须满足：`python scripts/check_stage_a.py` 退出码 0 且 `python -m unittest discover -s tests -v` 全过。当前已满足。

阶段 B 起每完成一阶段验收门才能进入下一阶段；任何阶段门失败必须保留私有检查点并阻止下游，不将"可编译"误报成"效果达标"或"可分享"。

## 阶段 B 完成报告（2026-10-09）

阶段 B「来源处理与私有运行骨架」已通过验收。本阶段交付模型处理同意前置、来源指纹与规范化、稳定分块、抽样覆盖矩阵、预锁留出、run journal + 幂等续跑、扫描预算预估与 `prepare-source` / `init-run` / `resume-run` 三个薄 CLI 子命令；**不**调用任何模型、不写入用户级 Skills。所有产物落在调用方传入的 `--run-root` 之下，且经 `scripts/path_safety.py` 的 containment + symlink 逃逸阻断；当前入口默认将它设为 `out/<run-id>/`。本阶段不声称效果已验证、不声称可分享。

### 交付清单

- 路径安全 `scripts/path_safety.py`（containment + symlink 逃逸阻断 + NUL 字节拒绝）。
- 来源指纹与规范化 `scripts/source_fingerprint.py`（BOM / CRLF / 零宽空格剥离；normalizer_version 入哈希）。
- 稳定分块器 `scripts/chunker.py`（Markdown 标题 + 中英文章节标题 + 虚拟 C000；≤ 5000 码点不切句；chunker_version 入哈希；场景 cue 词表 8 中 8 英锁定在脚本顶部）。
- 抽样覆盖矩阵 `scripts/sampling.py`（7 类场景 × 3 段位置 = 21 cell）+ 预锁留出 `scripts/holdout.py`（中段 20% 封存，hash 校验）。
- 模型处理同意前置校验 `scripts/authorization_gate.py`（模型处理范围必须覆盖所选模型；私有运行的派生用途默认 `private_only`，分享用途要求显式 shareable scope）。
- run journal `scripts/run_journal.py`（幂等续跑 + retry ≤ 3 + holdout 未锁禁止 `extract-*` 步骤；`run-config.json` sidecar 携带 parser_version 以兼容 stage A schema 的 `additionalProperties:false`）。
- 语义扫描预算 `scripts/scan_budget.py`（Ruling-4：估算口径 `1 token ≈ 4 字符`；`BATCH_WINDOW_CODEPOINTS = 32000 = 8000 * 4`；缺字段报错；窗口清单 + 续跑）。
- 薄 CLI `scripts/cli.py`（`prepare-source` / `init-run` / `resume-run` 三个子命令；不调模型）。
- 阶段 B 聚合验收 `scripts/check_stage_b.py` 与 216 个 unittest 用例全过；聚合报告 `docs/superpowers/reports/stage-b-2026-10-09.txt`。

### 显式不做（留给后续阶段）

- 不实现五维顺序提取、结构化复核提示、机制合并（**阶段 C**）。
- 不实现六个写作阶段 Skill 模板与 stage-context 状态机（**阶段 D**）。
- 不实现薄 CLI 的 `compile` / `validate-dist` / `package` / `install` 子命令与 deterministic 编译（**阶段 E**）。
- 不实现分阶段触发评测、输出机械断言、端到端盲评（**阶段 F**）。
- 不实现最终来源扫描、release-manifest、确定性 ZIP、隔离安装（**阶段 G**）。

### 后续准入

阶段 C 启动前必须满足：`python scripts/check_stage_b.py` 退出码 0 且 `python scripts/check_stage_a.py` 仍退出码 0。当前已满足。

阶段 C 起每完成一阶段验收门才能进入下一阶段；任何阶段门失败必须保留私有检查点并阻止下游，不将"可编译"误报成"效果达标"或"可分享"。

## 阶段 C 完成报告（2026-10-09）

阶段 C「五维提取、证据校验与规范 Bundle」已通过验收。本阶段交付证据偏移/哈希重算校验、五个顺序提取模块（独立方法模块，非并行 Agent）、结构化复核提示解析、候选去重 + 跨维度冲突消解 + 状态合并、Style Bundle 编译器与 `extract-dimensions` / `review-dimensions` / `compile-bundle` 三个薄 CLI 子命令；**不**调用任何模型，所有模型侧调用由 `wenfeng-distill` 工厂 Skill 按版本化提示完成；本地脚本仅验证提示版本、契约、对齐。聚合门默认 stub profile = `mixed`，端到端链路默认产出 `limited` 而非 `ready`，避免 CI 默认宣称系统已 ready。本阶段不声称效果已验证、不声称可分享。

### 交付清单

- 证据偏移/哈希重算校验 `scripts/evidence_validator.py`（与 `chunker._hash_window` 同源；Ruling-C4 兑现）。
- 五个顺序提取模块 `scripts/extractors/{narrative_voice,sentence_rhythm,scene_transition,dialogue_subtext,imagery_rhetoric}.py` + 调度基类 `scripts/extractors/base.py`（`DIMENSION_ORDER` 与 `EXTRACTION_PROMPT_VERSIONS` 锁定）。
- 占位模型函数 `scripts/extractors/base.py:_stub_model_call`（Ruling-C5；socket trap 单测保证无网络 IO）。
- 复核提示契约 `scripts/review_prompts.py`（`REVIEW_PROMPT_VERSION`、`REVIEW_RUBRIC`、`build_review_prompt`）。
- 复核解析 `scripts/review_parser.py`（`parse_review_output` 强制结构化 JSON；Ruling-C6）。
- 候选去重与状态合并 `scripts/mechanism_merger.py`（approved ≥3 scenes + ≥2 chapters + supported；limited ≥2 scenes；excluded ≥3 reasons 之一）。
- Style Bundle 编译器 `scripts/bundle_compiler.py`（仅 schema-allowed 字段；含 `book_name` / `author_name` 等来源专属字段即拒；Ruling-C7）。
- 阶段 C 日志 `scripts/extraction_journal.py`（holdout 未锁禁止 extract-*；retry ≤ 3；Ruling-C8）。
- 薄 CLI `scripts/cli_extract.py`（`extract-dimensions` / `review-dimensions` / `compile-bundle`）。
- 阶段 C 聚合验收 `scripts/check_stage_c.py` 与 287 个 unittest 用例全过；聚合报告 `docs/superpowers/reports/stage-c-2026-10-09.txt`。

### 显式不做（留给后续阶段）

- 不实现六个写作阶段 Skill 模板与 stage-context 状态机（**阶段 D**）。
- 不实现薄 CLI 的 `compile` / `validate-dist` / `package` / `install` 子命令与 deterministic 编译（**阶段 E**）。
- 不实现分阶段触发评测、输出机械断言、端到端盲评（**阶段 F**）。
- 不实现最终来源扫描、release-manifest、确定性 ZIP、隔离安装（**阶段 G**）。

### 后续准入

阶段 D 启动前必须满足：`python scripts/check_stage_c.py` 退出码 0 且 `python scripts/check_stage_b.py` 与 `python scripts/check_stage_a.py` 仍退出码 0。当前已满足。

阶段 D 起每完成一阶段验收门才能进入下一阶段；任何阶段门失败必须保留私有检查点并阻止下游，不将"可编译"误报成"效果达标"或"可分享"。

## 阶段 D 完成报告（2026-10-09）

阶段 D「六阶段 Skill 与上下文状态机」已通过验收。本阶段交付六个独立 Skill 模板（`write_entry` / `scene_design` / `character_beats` / `prose_draft` / `style_check` / `revision`）、阶段间数据契约表（spec §4.5 表 1:1）、stage-context 状态机（合法 handoff + return_to + 三次熔断 + partial replay targets）、模板-契约一致性检查器。模型侧执行仍由 `wenfeng-distill` 工厂 Skill 完成；本地脚本只验证模板形式、契约对齐、跳转合法性。聚合门强调"模板就绪 + 契约就绪"，**不**测触发 precision/recall、不跑端到端盲评——那些留给阶段 F。本阶段不声称效果已验证、不声称可分享。

### 交付清单

- 六个 Skill 模板 `templates/stages/{write_entry,scene_design,character_beats,prose_draft,style_check,revision}.md`（frontmatter + 6 段正文；自包含）。
- frontmatter 解析器 `scripts/skill_template.py`（纯 stdlib YAML 子集；不引入 PyYAML；Ruling-D7）。
- 阶段间数据契约 `scripts/six_stage_contract.py` + 人读文档 `docs/contracts/six-stage-data-contract.md`。
- stage-context 状态机 `scripts/six_stage_state_machine.py`（6 条合法 handoff；`return_to` 必须指向前一阶段；retry ≤ 3；partial_replay_targets 列出 `[return_to, ...下游阶段]`）。
- 下游引用失效校验 `scripts/stage_context_validator.py`（基于 stage A schema + 业务校验；`bundle://mechanism/M99` stale 引用 → `StaleMechanismReference`）。
- 模板-契约一致性检查 `scripts/template_contract_checker.py`（中文关键词映射；Ruling-D5 不验证运行时行为）。
- 阶段 D 聚合验收 `scripts/check_stage_d.py` 与 348 个 unittest 用例全过；聚合报告 `docs/superpowers/reports/stage-d-2026-10-09.txt`。

### 显式不做（留给后续阶段）

- 不实现薄 CLI 的 `compile` / `validate-dist` / `package` / `install` 子命令与 deterministic 编译（**阶段 E**）。
- 不实现分阶段触发评测、输出机械断言、端到端盲评（**阶段 F**）。
- 不实现最终来源扫描、release-manifest、确定性 ZIP、隔离安装（**阶段 G**）。

### 后续准入

阶段 E 启动前必须满足：`python scripts/check_stage_d.py` 退出码 0 且 `python scripts/check_stage_{c,b,a}.py` 仍退出码 0。当前已满足。

阶段 E 起每完成一阶段验收门才能进入下一阶段；任何阶段门失败必须保留私有检查点并阻止下游，不将"可编译"误报成"效果达标"或"可分享"。

## 阶段 E 完成报告（2026-10-09）

阶段 E「确定性编译与预检」已通过验收。本阶段交付并发锁、确定性 Skill 投影器、静态预检、字面预检、确定性编译器与 `compile` / `validate-dist` 薄 CLI 子命令。模型侧仍由 `wenfeng-distill` 工厂 Skill 完成；本地脚本不调模型，只验证模板 + 契约 + 确定性。聚合门**不**测运行时行为；阶段 F 用 staging 跑评测，阶段 G 用 staging 打包。本阶段不声称效果已验证、不声称可分享。

### 交付清单

- 并发锁 `scripts/concurrency_lock.py`（Windows `msvcrt.locking` / POSIX `fcntl.flock`；Ruling-E7）。
- 确定性 Skill 投影器 `scripts/skill_projector.py`（6 个 stage × bundle mechanism 投影；`{generated_at}` 永远渲染为空，Ruling-E2）。
- 静态预检 `scripts/preflight.py`（frontmatter / UTF-8 / 链接 / 资源 containment / 未声明文件；复用 stage B `path_safety`）。
- 字面预检 `scripts/literal_scan.py`（精确 shingle + 长段连续匹配；不引入相似度比例，Ruling-E4）。
- 确定性编译器 `scripts/deterministic_compiler.py`（临时目录 → atomic rename；失败 staging 不写 `compile-manifest.json`，Ruling-E3）。
- 薄 CLI `scripts/cli_compile.py`（`compile` / `validate-dist` 2 个子命令）。
- 阶段 E 聚合验收 `scripts/check_stage_e.py` 与 399 个 unittest 用例全过；聚合报告 `docs/superpowers/reports/stage-e-2026-10-09.txt`。

### 显式不做（留给后续阶段）

- 不实现分阶段触发评测、输出机械断言、端到端盲评（**阶段 F**）。
- 不实现最终来源扫描、release-manifest、确定性 ZIP、隔离安装（**阶段 G**）。

### 后续准入

阶段 F 启动前必须满足：`python scripts/check_stage_e.py` 退出码 0 且 `python scripts/check_stage_{d,c,b,a}.py` 仍退出码 0。当前已满足。

阶段 F 起每完成一阶段验收门才能进入下一阶段；任何阶段门失败必须保留私有检查点并阻止下游，不将"可编译"误报成"效果达标"或"可分享"。

## 阶段 F 完成报告（2026-10-09）

阶段 F「冻结候选并执行评测」已通过验收。本阶段交付触发评测指标计算器、阶段输出机械断言、端到端盲评框架、状态机聚合、评测冻结与脱敏报告写入与 `run-evaluation` / `validate-evaluation` 薄 CLI 子命令。模型侧仍由 `wenfeng-distill` 工厂 Skill 完成；本地脚本不调模型（聚合门有反向断言 grep `import socket` / `urllib` / `requests` 等）。聚合门**不**调模型、不写用户级 Skills；阶段 G 用 eval-report 打包。

**N=6 端到端配对仅支持本评测任务范围内的工程放行，不支持统计显著性或普遍有效声明**（spec §4.8 末段）。本阶段不声称效果已验证、不声称可分享。

### 交付清单

- 触发评测指标计算器 `scripts/trigger_metrics.py`（6 阶段 × (10+10+5)，precision/recall ≥ 0.90）。
- 阶段输出机械断言 `scripts/output_assertions.py`（复用 stage D `six_stage_contract`；缺输出 → `incomplete`；schema / 必需输出 / 硬约束机械断言 100%）。
- 端到端盲评框架 `scripts/end_to_end_eval.py`（≥6 组配对；winning ≥ 4 / median Δ ≥ +0.5 / quality Δ ≥ -0.5；分歧 > 1 → `undetermined_dimensions` → `limited`）。
- 状态机聚合 `scripts/final_state_evaluator.py`（复用 stage A `state_machine.compute_final_state`；缺输出 → `incomplete`；未脱敏 → `blocked`）。
- 评测冻结与脱敏报告写入 `scripts/evaluation_freezer.py`（不修改 stage A schema；`frozen_hashes` 写到 sidecar；脱敏报告剥除 `unblinding_map` / `pair_results` / `rating_secrets`，脱敏标记写进 `summary.notes`）。
- 薄 CLI `scripts/cli_evaluate.py` + 合成 fixture `scripts/cli_evaluate_synth.py`（`run-evaluation --profile {happy|mixed|contains_private}`；不调模型）。
- 阶段 F 聚合验收 `scripts/check_stage_f.py` + 反向断言；451 个 unittest 用例全过；聚合报告 `docs/superpowers/reports/stage-f-2026-10-09.txt`。

### 显式不做（留给后续阶段）

- 不实现最终来源扫描、release-manifest、确定性 ZIP、隔离安装（**阶段 G**）。
- 不实际运行真实模型生成 trigger / output / end-to-end 结果；本阶段仅验证评测管线（合成 fixture 来自 spec 锁定的 10+10+5 / 6+ 类场景）。真实模型侧由 `wenfeng-distill` 工厂 Skill 跑，输出接入阶段 G 之前必须由调用方替换合成 fixture。

### 后续准入

阶段 G 启动前必须满足：`python scripts/check_stage_f.py` 退出码 0 且 `python scripts/check_stage_{e,d,c,b,a}.py` 仍退出码 0。当前已满足。

阶段 G 起每完成一阶段验收门才能进入下一阶段；任何阶段门失败必须保留私有检查点并阻止下游，不将"可编译"误报成"效果达标"或"可分享"。

## 阶段 G 完成报告（2026-10-09）

阶段 G「最终来源扫描、打包与安装验收」已通过验收。本阶段交付最终来源扫描、release manifest 生成与自洽校验、确定性目录包 + ZIP 构造、隔离安装与 `verify-package`、状态机授权门与 `package` / `install` / `verify-package` / `purge-run` 薄 CLI 子命令。模型侧仍由 `wenfeng-distill` 工厂 Skill 完成；本地脚本不调模型（聚合门有反向断言 grep `import socket` / `urllib` / `requests` 等）、不写标准位置（`~/.wenfeng-skill` / `%APPDATA%/wenfeng-skill` 永不被写入）、不自动覆盖（拒绝同名覆盖除非 `--force`）。聚合门**不**调模型、不写用户级 Skills；阶段 G 是项目最终阶段。

**release manifest 证明产物与门禁记录相符，不构成版权或安全认证**（spec §4.9 末段）。本阶段不声称效果已验证、不声称可分享。

### 交付清单

- 最终来源扫描 `scripts/final_source_scan.py`（复用 stage E 字面预检；coverage < target → 拒绝；budget 不够时续跑）。
- release manifest 生成与自洽校验 `scripts/release_manifest.py`（拒 `source_body` / `book_name` / `author_name` / `unblinding_map` / `pair_results` / `rating_secrets` / `per_pair_text` / 私有 source exclusions；`build_hash` SHA-256 of canonical JSON）。
- 确定性目录包 + ZIP 构造 `scripts/deterministic_package.py`（mtime 固定 1980-01-01；字典序条目；`release-manifest.json` 在 dist_dir 根避免自指 hash 循环）。
- 隔离安装与 `verify-package` `scripts/isolated_install.py`（`--dry-run` 不动 target；`--scope user --target <path>` 显式 opt-in；拒绝标准位置；拒绝同名覆盖）。
- 状态机授权门 `scripts/package_state_gate.py`（`shareable` 仅 `ready` + `shareable_*`；`private-preview` 仅 `limited`；`blocked` / `incomplete` 不进 dist）。
- 薄 CLI `scripts/cli_package.py`（`package --profile {shareable,private-preview}` / `install --scope user --target` / `verify-package` / `purge-run`）。
- 阶段 G 聚合验收 `scripts/check_stage_g.py` + 反向断言；518 个 unittest 用例全过；聚合报告 `docs/superpowers/reports/stage-g-2026-10-09.txt`。

### 显式不做

- 不实现 spec §4.7 其他子命令（如 `list-runs` / `inspect-run` 等）；阶段 G 只实现 4 个子命令（`package` / `install` / `verify-package` / `purge-run`）。
- 不托管分发服务；spec §4.9 末段明文"首版不提供托管分发服务"。
- 不自动卸载旧版本；拒绝同名覆盖（除非 `--force`）。
- 不写 `source_body` / `book_name` / `author_name` / `unblinding_map` / `pair_results` / `rating_secrets` / `per_pair_text` / 私有 source exclusions 到 release-manifest 或 ZIP（spec §4.9 末段明文"不含来源正文、证据短摘录、留出文本、私有 source exclusions、逐案例评测文本、评分密钥或解盲映射"）。

### 后续准入

阶段 G 是项目最终阶段；依赖顺序为 A → B → C → D → E → F → G。当前已全部通过验收。本项目的门禁链到此闭合：**所有阶段门未通过时保留私有检查点并阻止下游，不将"可编译"误报成"效果达标"或"可分享"**（spec §6 末段）。
