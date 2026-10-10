# 文风蒸馏 Skill

`wenfeng-distill` 从一部用户提供的 TXT/Markdown 小说中提取有证据、有限定的表达机制，并生成一个 Style Bundle 和六个写作阶段 Skill。它不保留 cangjie 的通用知识蒸馏流程。

## 使用

将此目录作为 `wenfeng-distill` 放入 Codex 本地 Skills 目录，或在开发时从当前项目直接读取 `SKILL.md`。默认私有 run root 为本目录的 `out/<run-id>/`；根目录 `.gitignore` 忽略整个 `/out/`。源正文、留出样本、摘录、来源地图和评分记录只写入该私有运行区，不放入生成 Skill 或发布包。

运行前确认用户接受选定摘录进入当前会话所用模型的上下文；不要求用户声明来源处理权。本地 Skill 不代表模型处理必然只发生在本机。`out/` 是 Git 忽略的本地工作区，不提供加密或操作系统访问控制。

## Style Bundle 结构校验

```powershell
python scripts/validate_bundle.py path\to\style-bundle.json
python -m unittest discover -s tests -v
```

校验器检查 JSON 结构、必填字段、状态与 ID、证据定位格式、机制证据数量，以及 `ready` Bundle 的声明维度覆盖。返回码 `0` 表示结构与声明门槛通过，`1` 表示 Bundle 不符合结构/门槛，`2` 表示文件不可读或 JSON 无法解析。自检数据均为合成内容。

结构通过不代表来源隔离、版权或语义安全已经得到证明；来源内容仍须只留在 `out/<run-id>/`，并按 Skill 内的内容隔离流程处理。

## Policy 门禁

```powershell
python scripts/check_policy_gate.py policies/evaluation-policy.json policies/content-scan-policy.json policies/model-budget-policy.json
```

只读检查器。返回 `0` 表示三份 policy 均通过结构与数值门槛，`1` 表示存在违规项，`2` 表示文件不可读或 JSON 无法解析。**任何被支持模型若缺 `max_requests` / `max_input_tokens_total` / `max_tokens_per_batch` / `overlimit_policy` 任一项，对该模型的 `compute_readiness` 必须返回 `False`**，并被 `compute_readiness` 报告为 `model_budget_profile_incomplete`。

## 阶段 A 验收（契约冻结）

```powershell
python scripts/check_stage_a.py
python -m unittest discover -s tests -v
```

阶段 A 仅冻结**契约、数值门槛与交付定义**，未启动来源抽取、Skill 编译、内容扫描或评测。运行入口 `wenfeng-distill` 行为保持原样。本阶段不声称效果已验证、不声称可分享；阶段 B–G 须依次启动并逐门验收。

## 阶段 B 验收（来源处理与私有运行骨架）

```powershell
python scripts/check_stage_b.py
```

阶段 B 落地了 `source_id` 随机生成、原始文件哈希与规范化文本指纹、稳定分块、`init-run` 授权校验、模型标注 scene map、按真实标签生成的抽样覆盖矩阵、可验证的留出锁、`run-manifest.json` 步进日志，以及 `prepare-source` / `init-run` / `apply-scene-map` / `build-sampling` / `lock-holdout` / `resume-run` CLI 子命令。提取前必须通过 `lock-holdout` 校验；单独修改配置中的布尔值不会解锁提取。所有写操作只发生在用户显式传入的 `--run-root` 之下；模型调用仍由 `wenfeng-distill` 工厂 Skill 负责。

聚合门退出码：`0` 通过；`1` 阶段 B 不变量破坏；`2` 端到端链失败。

## 阶段 C 验收（五维提取、证据校验与规范 Bundle）

```powershell
python scripts/check_stage_c.py
```

阶段 C 落地了证据偏移/哈希重算校验器（按 Ruling-C4 与 `chunker._hash_window` 同源）、五个顺序提取模块（独立方法模块，非并行 Agent）、结构化复核提示解析、机制去重与状态合并、Style Bundle 编译器，以及 `extract-dimensions` / `review-dimensions` / `compile-bundle` 三个薄 CLI 子命令。模型侧调用仍由 `wenfeng-distill` 工厂 Skill 负责；本地脚本不调模型，`--stub` 模式仅用于本地回归测试。聚合门默认 stub profile = `mixed`，端到端链路默认产出 `limited` 而非 `ready`，避免 CI 默认宣称系统已 ready。

聚合门退出码：`0` 通过；`1` 阶段 C 不变量破坏；`2` 端到端链失败。

## 阶段 D 验收（六阶段 Skill 与上下文状态机）

```powershell
python scripts/check_stage_d.py
```

阶段 D 落地了六个独立 Skill 模板（`write_entry` / `scene_design` / `character_beats` / `prose_draft` / `style_check` / `revision`），阶段间数据契约表（spec §4.5 表 1:1），stage-context 状态机（合法 handoff + return_to 合法 + 三次熔断），模板-契约一致性检查器。聚合门强调"模板就绪 + 契约就绪"，**不**测触发 precision/recall、不跑端到端盲评——那些留给阶段 F。本阶段不声称效果已验证、不声称可分享。

聚合门退出码：`0` 通过；`1` 阶段 D 不变量破坏；`2` 端到端链失败。

## 阶段 E 验收（确定性编译与预检）

```powershell
python scripts/check_stage_e.py
```

阶段 E 落地了并发锁（Windows `msvcrt.locking` / POSIX `fcntl.flock`，Ruling-E7）、确定性 Skill 投影器（`{generated_at}` 永远渲染为空，Ruling-E2）、静态预检、字面预检、确定性编译器（相同输入 → 相同字节；`compile-manifest` schema 0.2.0 携带 `source_id`）与 `compile` / `validate-dist` CLI 子命令。模型侧仍由 `wenfeng-distill` 工厂 Skill 负责；本地脚本不调模型，只验证模板、契约和确定性。本阶段不声称效果已验证、不声称可分享。

聚合门退出码：`0` 通过；`1` 阶段 E 不变量破坏；`2` IO / 子进程失败。

## 阶段 F 验收（冻结候选并执行评测）

```powershell
python scripts/check_stage_f.py
```

阶段 F 落地了触发评测指标计算器（precision/recall ≥ 0.90 / ≥ 10+10+5 用例）、阶段输出机械断言（contract 100% 匹配；缺输出 → `incomplete`）、端到端盲评框架（≥6 组配对 × ≥3 类场景；winning ≥ 4 / median Δ ≥ +0.5 / quality Δ ≥ -0.5；分歧 > 1 → `limited`；N=6 仅支持本任务范围内工程放行）、评测冻结与脱敏报告写入（解盲映射 / 逐案例文本 / 评分密钥不留入 staging；脱敏标记写在 `summary.notes`）、状态机聚合（复用 stage A `state_machine.compute_final_state`）、`run-evaluation` / `validate-evaluation` 薄 CLI 子命令与 `scripts/check_stage_f.py` 聚合门。模型侧仍由 `wenfeng-distill` 工厂 Skill 负责；本地脚本不调模型（聚合门有反向断言 grep `import socket` / `urllib` / `requests` 等）。聚合门**不**调模型、不写用户级 Skills；阶段 G 用 eval-report 打包。

聚合门退出码：`0` 通过；`1` 阶段 F 不变量破坏；`2` IO / 子进程失败。

## 阶段 G 验收（最终来源扫描、打包与安装验收）

```powershell
python scripts/check_stage_g.py
```

阶段 G 落地了最终来源扫描、release manifest、自洽校验、确定性目录包与 ZIP、隔离安装和 `verify-package`。`install` 默认只做 dry-run；实际写入需要显式 `--apply --scope user --target <path>`。`~/.wenfeng-skill`、`%APPDATA%/wenfeng-skill` 等标准位置始终拒绝写入，现有目标也不会自动覆盖。`shareable` 要求 `ready` 与分享授权；`private-preview` 仅接受 `limited`；`blocked` / `incomplete` 不进入 dist。模型侧仍由工厂 Skill 负责，本地脚本不调模型。release manifest 证明产物与门禁记录相符，**不**构成版权或安全认证。

聚合门退出码：`0` 通过；`1` 阶段 G 不变量破坏；`2` IO / 子进程 / 状态门失败。

`package --profile shareable` 输出位置：`<output-dir>/<source_id>/<bundle_id>/v0.1.0/`，内含 `package.zip`（6 个 SKILL.md + compile-manifest.json + eval-report.json；release-manifest.json 在 dist_dir 根避免自指 hash 循环）+ `release-manifest.json` + `source-scan-report.json`。

## 草稿修订试点

项目中另有一个单独调用的草稿修订 Skill：[skills/wenfeng-style-revision/SKILL.md](skills/wenfeng-style-revision/SKILL.md)。它需要用户提供草稿和现成的证据型写作指南；缺少指南时会先询问是否补充指南或改为中性润色。该模块目前是项目级试点，尚未安装到用户级 Skills 目录。

每个 `check_stage_*.py` 只检查对应阶段；完整检查按 A→G 依次运行各门，全量单测运行 `python -m unittest discover -s tests -v`。

## 边界

- 首版只面向单部小说、五维整合提取和一个 Style Bundle；编译产物为六个写作阶段 Skill。
- 低证据覆盖结果标为 `limited`；小样本盲评不能证明普遍效果。
- 候选机制和内容隔离由固定门槛自动判定；低证据规则会降级或剔除，不要求用户逐条审批。首版不提供相似度或语义安全保证。
- 不要提交小说正文、留出集、证据摘录、运行材料或源名映射。

用户明确启动了阶段二、三的有界试点：现已加入 Bundle 结构校验器和一个草稿修订模块。该启动指令不算真实使用故障或重复单独调用的证据；后续自动化和其他模块拆分仍须满足设计说明中的分阶段门槛。

## 阶段 A 已交付

2026-10-09 阶段 A「冻结契约、门槛与交付定义」已通过验收：

- 13 个 JSON Schema（Draft 2020-12，单文件 vendored 自写校验器，扩展 `x-wenfengRange` / `x-wenfengCodepointMax`）锁定在 `schemas/`；详见 `schemas/_meta.json`。
- 3 份 policy 文件（`policies/evaluation-policy.json`、`content-scan-policy.json`、`model-budget-policy.json`）冻结数值门槛；`scripts/check_policy_gate.py` 提供只读 CLI 入口。
- 状态机 `scripts/state_machine.py` + 哈希失效规则 `scripts/invalidation_rules.py` 与两份人读文档 `docs/contracts/{state-machine.md,invalidation-rules.md}` 同源。
- 跨文件引用检查 `scripts/check_bundle_cross_refs.py` 补足 vendored 校验器不实现的 `$id` 跨文件解析。
- 阶段 A 聚合验收 `scripts/check_stage_a.py` 与 128 个 unittest 用例全过；报告见 `docs/superpowers/reports/stage-a-2026-10-09.txt`。

**本阶段不声称效果已验证、不声称可分享**；`wenfeng-distill` 入口行为保持原样。阶段 B–G 须按 spec §6 顺序启动并逐门验收。

## 阶段 B 已交付

2026-10-09 阶段 B「来源处理与私有运行骨架」已通过验收：

- 路径安全 `scripts/path_safety.py`（containment + symlink 逃逸阻断）。
- 来源指纹与规范化 `scripts/source_fingerprint.py`（BOM / CRLF / 零宽空格剥离；normalizer_version 入哈希）。
- 稳定分块器 `scripts/chunker.py`（Markdown 标题 + 中英文章节标题 + 虚拟 C000；≤ 5000 码点不切句；chunker_version 入哈希）。
- 抽样覆盖矩阵 `scripts/sampling.py`（7 类场景 × 3 段位置 = 21 cell；只统计有 scene class 标签的 chunk）+ 预锁留出 `scripts/holdout.py`（封存中段场景，整场景锁定并校验 hash）。
- 模型处理同意前置校验 `scripts/authorization_gate.py`（模型处理范围必须覆盖所选模型；私有运行的 derivative_use 默认为 `private_only`，分享用途需显式 shareable scope）。
- run journal `scripts/run_journal.py`（幂等续跑 + retry ≤ 3 + holdout 未锁禁止 extract-*）。
- 语义扫描预算 `scripts/scan_budget.py`（Ruling-4：估算口径 `1 token ≈ 4 字符`；缺字段报错；窗口清单 + 续跑）。
- 薄 CLI `scripts/cli.py`（来源准备、初始化、scene map、抽样、留出锁定和续跑；不调模型）。
- 阶段 B 聚合验收 `scripts/check_stage_b.py` 与 216 个 unittest 用例全过；报告见 `docs/superpowers/reports/stage-b-2026-10-09.txt`。

**本阶段不声称效果已验证、不声称可分享**；所有写操作只发生在 `--run-root` 之下，模型抽取仍由 `wenfeng-distill` 工厂 Skill 负责。阶段 C–G 须按 spec §6 顺序启动并逐门验收。

## 阶段 C 已交付

2026-10-09 阶段 C「五维提取、证据校验与规范 Bundle」已通过验收：

- 证据偏移/哈希重算校验 `scripts/evidence_validator.py`（与 `chunker._hash_window` 同源；越界 / 错位 / hash 不匹配 → 拒绝）。
- 五个顺序提取模块 `scripts/extractors/{narrative_voice,sentence_rhythm,scene_transition,dialogue_subtext,imagery_rhetoric}.py`（独立方法模块，非并行 Agent；每个维度固定 `extraction_prompt_version`，变更触发下游失效）。
- 占位模型函数 `scripts/extractors/base.py:_stub_model_call`（仅 `--stub` 与测试使用，socket trap 保证无网络 IO）。
- 复核提示契约 `scripts/review_prompts.py` + 自动判定 `scripts/review_parser.py`（强制结构化 JSON；自由文本拒绝）。
- 候选去重 + 机制合并 `scripts/mechanism_merger.py`（approved ≥3 scenes + ≥2 chapters + supported；limited ≥2 scenes；跨 chunk 冲突自动 excluded）。
- Style Bundle 编译器 `scripts/bundle_compiler.py`（仅写 schema-allowed 字段；含源专属字段即拒）。
- 阶段 C 日志 `scripts/extraction_journal.py`（基于 stage B `run_journal`，holdout 未锁禁止 extract-*）。
- 薄 CLI `scripts/cli_extract.py`（`extract-dimensions` / `review-dimensions` / `compile-bundle`；不调模型；`--stub` 默认 `mixed` profile，端到端默认产出 `limited`）。
- 阶段 C 聚合验收 `scripts/check_stage_c.py` 与 287 个 unittest 用例全过；报告见 `docs/superpowers/reports/stage-c-2026-10-09.txt`。

**本阶段不声称效果已验证、不声称可分享**；模型调用仍由 `wenfeng-distill` 工厂 Skill 负责；占位函数严禁生产路径使用。阶段 D–G 须按 spec §6 顺序启动并逐门验收。

## 阶段 D 已交付

2026-10-09 阶段 D「六阶段 Skill 与上下文状态机」已通过验收：

- 六个独立 Skill 模板 `templates/stages/{write_entry,scene_design,character_beats,prose_draft,style_check,revision}.md`（frontmatter + 6 个必填正文段；自包含，不互相引用）。
- 模板解析器 `scripts/skill_template.py`（纯 stdlib YAML 子集；不引入 PyYAML）。
- 阶段间数据契约 `scripts/six_stage_contract.py`（spec §4.5 表 1:1）+ 人读文档 `docs/contracts/six-stage-data-contract.md`。
- stage-context 状态机 `scripts/six_stage_state_machine.py`（合法 handoff 6 条边、`return_to` 只能向前回退、`retry_count ≤ 3`、`partial_replay_targets` 只重跑 `return_to` 及下游）。
- 下游引用失效校验 `scripts/stage_context_validator.py`（基于 stage A `stage-context.schema.json`；`bundle://mechanism/M99` 之类的 stale 引用 → `StaleMechanismReference`）。
- 模板-契约一致性检查 `scripts/template_contract_checker.py`（中文关键词映射；写"模板就绪 + 契约就绪"，不验证运行时行为）。
- 阶段 D 聚合验收 `scripts/check_stage_d.py` 与 348 个 unittest 用例全过；报告见 `docs/superpowers/reports/stage-d-2026-10-09.txt`。

**本阶段不声称效果已验证、不声称可分享**；六个模板是契约，模型侧执行仍由 `wenfeng-distill` 工厂 Skill 完成；触发 precision/recall / 端到端盲评留给阶段 F。

## 阶段 E 已交付

2026-10-09 阶段 E「确定性编译与预检」已通过验收：

- 并发锁 `scripts/concurrency_lock.py`（Windows `msvcrt.locking` / POSIX `fcntl.flock`；同进程重入报 `LockBusy`，Ruling-E7）。
- 确定性 Skill 投影器 `scripts/skill_projector.py`（6 个 stage × bundle mechanism 投影；`{generated_at}` 永远渲染为空，Ruling-E2）。
- 静态预检 `scripts/preflight.py`（frontmatter / UTF-8 / 链接 / 资源 containment / 未声明文件；复用 stage B `path_safety`）。
- 字面预检 `scripts/literal_scan.py`（精确 shingle + 长段连续匹配；不引入相似度比例，Ruling-E4）。
- 确定性编译器 `scripts/deterministic_compiler.py`（临时目录 → atomic rename；失败 staging 不写 `compile-manifest.json`，Ruling-E3）。
- 薄 CLI `scripts/cli_compile.py`（`compile` / `validate-dist` 2 个子命令；不调模型）。
- 阶段 E 聚合验收 `scripts/check_stage_e.py` 与 399 个 unittest 用例全过；报告见 `docs/superpowers/reports/stage-e-2026-10-09.txt`。

**本阶段不声称效果已验证、不声称可分享**；模型侧仍由 `wenfeng-distill` 工厂 Skill 完成；评测/打包/安装留给阶段 F / G。

## 阶段 F 已交付

2026-10-09 阶段 F「冻结候选并执行评测」已通过验收：

- 触发评测指标计算器 `scripts/trigger_metrics.py`（6 阶段 × (10 must_trigger + 10 must_not_trigger + 5 boundary)，precision/recall ≥ 0.90）。
- 阶段输出机械断言 `scripts/output_assertions.py`（复用 stage D `six_stage_contract`；缺输出 → `incomplete`；schema / 必需输出 / 硬约束机械断言 100%）。
- 端到端盲评框架 `scripts/end_to_end_eval.py`（≥6 组配对 × ≥3 类场景；复用 stage A `effect_gate`；winning ≥ 4 / median Δ ≥ +0.5 / quality Δ ≥ -0.5；评审分歧 > 1 → 该维度 `undetermined_dimensions` → 整体降 `limited`）。
- 状态机聚合 `scripts/final_state_evaluator.py`（复用 stage A `state_machine.compute_final_state`；缺输出 → `incomplete`；未脱敏 → `blocked`）。
- 评测冻结与脱敏报告写入 `scripts/evaluation_freezer.py`（不修改 stage A schema；`frozen_hashes` 写到 sidecar `eval-report.frozen-hashes.json`；脱敏报告剥除 `unblinding_map` / `pair_results` / `rating_secrets`，脱敏标记写进 `summary.notes`）。
- 薄 CLI `scripts/cli_evaluate.py` + 合成 fixture `scripts/cli_evaluate_synth.py`（`run-evaluation --profile {happy|mixed|contains_private}`；不调模型）。
- 阶段 F 聚合验收 `scripts/check_stage_f.py` + 反向断言（grep `import socket / urllib / requests`）；451 个 unittest 用例全过；报告见 `docs/superpowers/reports/stage-f-2026-10-09.txt`。

**本阶段不声称效果已验证、不声称可分享**；模型侧仍由 `wenfeng-distill` 工厂 Skill 完成；**N=6 端到端配对仅支持本评测任务范围内的工程放行，不支持统计显著性或普遍有效声明**（spec §4.8 末段）；打包/安装留给阶段 G。

## 阶段 G 已交付

2026-10-09 阶段 G「最终来源扫描、打包与安装验收」已通过验收：

- 最终来源扫描 `scripts/final_source_scan.py`（复用 stage E 字面预检；coverage < target → 拒绝；budget 不够时续跑，未覆盖不能标 ready）。
- release manifest 生成与自洽校验 `scripts/release_manifest.py`（拒 `source_body` / `book_name` / `author_name` / `unblinding_map` / `pair_results` / `rating_secrets` / `per_pair_text` / 私有 source exclusions；`build_hash` 由 SHA-256 of canonical JSON 重算）。
- 确定性目录包 + ZIP 构造 `scripts/deterministic_package.py`（mtime 固定 1980-01-01 00:00:00；字典序条目；`release-manifest.json` 在 dist_dir 根避免自指 hash 循环；同输入 → 同字节）。
- 隔离安装与 `verify-package` `scripts/isolated_install.py`（默认 dry-run；显式 `--apply --scope user --target <path>` 才写入；拒绝标准位置；拒绝同名覆盖除非 `--force`；`verify-package` 跨阶段校验 release-manifest + 6 Skill 哈希 + stage F eval-report）。
- 状态机授权门 `scripts/package_state_gate.py`（`shareable` 仅 `ready` + `shareable_*`；`private-preview` 仅 `limited`；`blocked` / `incomplete` 不进 dist）。
- 薄 CLI `scripts/cli_package.py`（`package --profile {shareable,private-preview}` / `install --scope user --target` / `verify-package` / `purge-run`）。
- 阶段 G 聚合验收 `scripts/check_stage_g.py` + 反向断言（grep `import socket / urllib / requests`；release manifest 拒私有字段）；518 个 unittest 用例全过；报告见 `docs/superpowers/reports/stage-g-2026-10-09.txt`。

**release manifest 证明产物与门禁记录相符，不构成版权或安全认证**（spec §4.9 末段）。**本阶段不声称效果已验证、不声称可分享**；模型侧仍由 `wenfeng-distill` 工厂 Skill 完成。阶段 G 是项目最终阶段（依赖顺序 A → B → C → D → E → F → G 全部通过）。
