# 阶段 G 实施计划：最终来源扫描、打包与安装验收

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不调用任何模型、不动阶段 A–F 任何资产的前提下，把**最终来源扫描、release-manifest、确定性目录包 + ZIP、隔离安装验收、用户级 dry-run**完整落地。`dist/<source_id>/<bundle_version>/` 只能由 `final_state="ready"` + 授权允许分享时生成；limited 仅生成 run-private 预览；blocked/incomplete 不进入 dist。所有产物可在隔离位置被 `verify-package` 复检。

**Architecture:** 薄本地 CLI（纯 Python 标准库）。输入来自阶段 F 冻结的 staging（含 `compile-manifest.json` + `eval-report.json` + 六个 Skill body + `eval-report.frozen-hashes.json`）。阶段 G 只读不写 staging；写所有产物到 `run_root/dist/` 或 `dist/<source_id>/<bundle_version>/`。模型侧仍由 `wenfeng-distill` 工厂 Skill 完成；本地脚本只验证：来源扫描覆盖、报告哈希、release manifest 自洽、ZIP 字节一致、安装拒绝覆盖与标准位置、`verify-package` 通过。

**Tech Stack:** Python 3 标准库（hashlib / pathlib / json / re / zipfile / tempfile / shutil / secrets）。阶段 A `vendor/json_schema_validate.py` + 13 schema、阶段 B `path_safety.py` / `run_journal.py`、阶段 C `evidence_validator.py` / `bundle_compiler.py`、阶段 D `six_stage_contract.py` / `stage_context_validator.py`、阶段 E `preflight.py` / `literal_scan.py` / `deterministic_compiler.py` / `cli_compile.py` / `check_stage_e.py`、阶段 F `evaluation_freezer.py` / `cli_evaluate.py` / `check_stage_f.py`、`scripts/state_machine.py` / `effect_gate.py` / `invalidation_rules.py` / `check_bundle_cross_refs.py`。

**Spec anchors:** §4.7（CLI）、§4.9（分发）、§6 阶段 G 验收原文。

## Global Constraints

- **绝不**调用任何模型；本地脚本只做来源扫描、release manifest、确定性 ZIP、隔离安装、复检。
- **绝不**复制、提交、输出**任何**真实来源正文、留出集、证据摘录、书名、作者名、人物名。所有测试夹具使用公开虚构文本。
- **绝不**新增运行时依赖；只能使用 Python 3 标准库 + 已落地的 `vendor/`、`scripts/`。
- **绝不**写 `%APPDATA%/wenfeng-skill` / `~/.wenfeng-skill` 等标准位置；只接受 `--scope user --target <path>` 显式 opt-in。
- **绝不**自动卸载旧版本；拒绝同名覆盖（除非 `--force`）。
- **绝不**把 `source_body` / `book_name` / `author_name` / `unblinding_map` / `pair_results` / `rating_secrets` / `per_pair_text` 写进 release-manifest 或 ZIP 内容。
- 阶段 G **不**修改阶段 A 的 13 个 schema；`release-manifest.schema.json` 是阶段 G **新增**的 schema（Ruling-G1）。
- 阶段 G **不**修改 `wenfeng-distill` 工厂 Skill；只读 `staging_root` 字节。
- 阶段 G **不**直接修改 staging 字节；只读 `validate-dist` + `validate-evaluation` 已通过的结果。
- `package --profile shareable` 仅当 `final_state == "ready"` 且 `authorization_purpose` ∈ `{shareable_anonymous, shareable_with_attribution}` 时允许；否则报错退出 2。
- `package --profile private-preview` 仅当 `final_state == "limited"` 时允许（`incomplete` / `blocked` 不进入 dist；spec §4.9 末段）；写到 `run_root/dist/private/`。
- `verify-package` 在 tmpdir 解包 → 跑 `validate-dist` + `validate-evaluation` + release manifest 哈希校验；不修改任何文件。
- `purge-run` 只删 `run_root/dist/` 私有预览目录；不动 `dist/<source_id>/<bundle_version>/`。

## Review Focus

- **最终来源扫描**对 6 个 Skill body 与 eval-report 的字面扫描；预算不足时 `coverage < 1.0` → 不能标 ready。
- **release-manifest.json** 包含 build-hash、bundle/模板/工具/schema 版本、6 个 Skill 哈希、ZIP 哈希、授权用途、触发/输出/端到端门状态、eval 报告哈希、最终扫描策略版本/覆盖率/报告哈希、兼容目标、发布状态。
- **确定性 ZIP**：`zipfile.ZIP_DEFLATED` + 排序条目 + 固定 mtime（1980-01-01 00:00:00） → 相同输入 → 相同字节。
- **隔离安装验收**：`install --dry-run` 解到 tmpdir 并跑 `verify-package`；`install --scope user --target <path>` 显式 opt-in；拒绝标准位置 + 拒绝同名覆盖。
- **只有 ready + 授权**生成 shareable ZIP；limited 仅私有预览；blocked/incomplete 报错。
- **verify-package** 跨阶段：stage A 13 个 schema、stage E `validate-dist`、stage F `validate-evaluation`、stage G `release-manifest` 哈希。
- **不**进入 dist 的字段：`source_body` / `book_name` / `author_name` / `unblinding_map` / `pair_results` / `rating_secrets` / `per_pair_text` / 私有 source exclusions。
- **N=6 端到端** 仍只支持本任务范围内工程放行（spec §4.8 末段）。
- 状态机：阶段 A `state_machine.compute_final_state` 同源。
- 阶段 G 不实现 `package` 之外的 spec §4.7 子命令（如有 `list-runs` / `inspect-run` 等 → 留 spec 后续扩展）。

### Task 1: 最终来源扫描（仅本地合成 fixture）

**Files:**
- Create: `scripts/final_source_scan.py`
- Create: `tests/test_final_source_scan.py`

**接口契约：**
- `class SourceScanPolicy`：字段 `policy_version: str`、`shingle_size: int`、`min_continuous_match: int`、`total_budget_codepoints: int`、`coverage_target: float`。
- `final_source_scan(staging_root: Path, policy: SourceScanPolicy) -> dict`：对 staging 内 6 个 Skill body + `eval-report.json` 跑字面扫描；返回 `{"policy_version", "coverage_codepoints", "coverage_target", "coverage_ratio", "skill_scan_results", "report_scan_result", "hashes", "scanned_at_marker"}`。`scanned_at_marker=""`（Ruling-E2）。
- `final_source_scan_with_run_journal(...)`：额外把扫描摘要写到 `run_journal`（spec §4.7 要求 run manifest 记录每步）。
- `evaluate_scan_coverage(scan: dict) -> list[str]`：返回错误消息。`coverage_ratio < policy.coverage_target` → "coverage below target"。
- 预算不足（`coverage_ratio < 1.0`）→ 不能标 ready；接受 partial coverage 但报 warning。

- [x] 写 5 个非法 / 边界单测：coverage < target → 失败；shingle_size=0 → ValueError；未知 policy_version 字段 → 接受（schema 之外字段被忽略）；扫描 Skill body 含精确 shingle → 报错；staging 缺 SKILL.md → 报错。
- [x] 写 3 个合法单测：干净 staging 通过扫描、coverage=1.0；预算用尽但 coverage=0.95 → 通过（>= target）；同输入两次扫描哈希一致（determinism）。
- [x] 跑通。

### Task 2: release manifest 生成与自洽校验

**Files:**
- Create: `scripts/release_manifest.py`
- Create: `schemas/release-manifest.schema.json`
- Create: `tests/test_release_manifest.py`

**接口契约：**
- `class ReleaseManifest`：必填字段见 `release-manifest.schema.json`。
- `build_release_manifest(staging_root: Path, *, bundle_id: str, source_id: str, authorization_purpose: str, eval_report_hash: str, final_scan_result: dict, zip_path: Path | None = None) -> dict`：构造 manifest dict；`build_hash` = `hashlib.sha256(sorted_json_bytes(manifest_without_build_hash))`。
- `write_release_manifest(manifest: dict, target_dir: Path) -> Path`：写到 `target_dir/release-manifest.json`；schema 校验。
- `verify_release_manifest(manifest: dict) -> list[str]`：返回错误消息列表；`build_hash` 必须与重算一致；所有哈希字段必须存在。
- **不**写 source_body / book_name / author_name / unblinding_map / pair_results / rating_secrets；如提供则抛 `ReleaseManifestError`。

- [x] 写 5 个非法单测：build_hash 失配 → 拒；含 source_body → 拒；含 unblinding_map → 拒；缺 zip_hash → 拒；schema 校验失败 → 拒。
- [x] 写 3 个合法单测：完整 manifest 写入 / 校验通过；同输入两次写 build_hash 一致（determinism）；`verify-package` 跨字段：6 个 Skill 哈希与 staging 字节一致。
- [x] 跑通。

### Task 3: 确定性目录包 + ZIP 构造

**Files:**
- Create: `scripts/deterministic_package.py`
- Create: `tests/test_deterministic_package.py`

**接口契约：**
- `build_directory_dist(staging_root: Path, manifest: dict, *, output_dir: Path) -> Path`：把 staging 内容 + release-manifest 拷到 `output_dir`（按 `source_id/bundle_version/` 子目录）；**不**拷贝 eval-suite/eval-cases/frozen-hashes；只拷 6 个 Skill body + `compile-manifest.json` + `eval-report.json` + `release-manifest.json`。
- `build_zip_dist(directory_dist: Path, output_path: Path) -> Path`：构造确定性 ZIP；`zipfile.ZIP_DEFLATED` + `sort_entries=True` + 固定 mtime（1980-01-01 00:00:00）；同输入 → 同字节。
- `compute_zip_hash(zip_path: Path) -> str`：`hashlib.sha256(zip_path.read_bytes())`。
- 拒绝任何路径逃逸；拒绝 symlink 逃逸；拒绝写入标准位置。

- [x] 写 5 个非法单测：含 symlink 逃逸 → 拒；含 source_body 字段 → 拒；含 unblinding_map → 拒；output_dir 在 run_root 外 → 拒；ZIP mtime 漂移 → 字节不同。
- [x] 写 3 个合法单测：同输入两次 ZIP 字节相同（determinism）；目录包字节序与 ZIP entry 顺序一致；`compute_zip_hash` 跨次幂等。
- [x] 跑通。

### Task 4: 隔离安装与 `verify-package`

**Files:**
- Create: `scripts/isolated_install.py`
- Create: `tests/test_isolated_install.py`

**接口契约：**
- `class InstallScope`：只接受 `user`（不暴露 `system`）。
- `dry_run_install(package_path: Path, *, target: Path) -> dict`：解到 tmpdir（不写 target）；调 `verify-package`；返回 `{"dry_run", "target", "tmpdir", "verify_result", "files_in_target_unchanged"}`。
- `user_install(package_path: Path, *, target: Path, force: bool = False) -> dict`：显式 opt-in；解到 target；**拒绝** `Path.home() / ".wenfeng-skill"` / `%APPDATA%/wenfeng-skill` 之类；**拒绝**同名覆盖（除非 `force=True`）；返回 `{"installed", "target", "files"}`。
- `verify_package(package_path: Path, *, tmp_root: Path | None = None) -> dict`：解到 tmpdir（默认自动管理）→ 跑 stage E `validate_dist`（直接对 staging subdir）+ stage F `validate_evaluation` + release manifest 校验 + 6 个 Skill 哈希复检。
- 拒绝写 `Path.home() / ".wenfeng-skill"` / `Path(os.environ.get("APPDATA", "")) / "wenfeng-skill"` / 任何 `dist/<source_id>/<bundle_version>/` 路径。

- [x] 写 5 个非法单测：拒绝标准位置（`--target ~/.wenfeng-skill`） → 拒；拒绝覆盖（target 已存在 + 无 `--force`） → 拒；`--scope system` 不被识别 → 拒；`verify-package` 缺 release-manifest → 拒；`verify-package` 哈希失配 → 拒。
- [x] 写 3 个合法单测：`dry-run` 不写 target；`user install` 写 target；`verify-package` 在篡改 SKILL.md 后报错。
- [x] 跑通。

### Task 5: 状态机与授权门（package 入口）

**Files:**
- Create: `scripts/package_state_gate.py`
- Create: `tests/test_package_state_gate.py`

**接口契约：**
- `class PackageProfile`：枚举 `shareable` / `private-preview`。
- `evaluate_package_state(final_state: str, authorization_purpose: str, profile: PackageProfile) -> str`：返回 `allowed` / `denied` / `private-allowed`。
  - `shareable + final_state=="ready" + purpose in {shareable_*, shareable_anonymous}` → `allowed`
  - `private-preview + final_state=="limited"` → `private-allowed`
  - 其它 → `denied`
- `deny_reason(...)` 给出可读原因。
- 复用 stage A `state_machine.compute_final_state` 检查授权标志。

- [x] 写 5 个非法单测：shareable + final_state="limited" → denied；shareable + final_state="blocked" → denied；shareable + final_state="incomplete" → denied；private-preview + final_state="blocked" → denied；private-preview + final_state="incomplete" → denied。
- [x] 写 3 个合法单测：shareable + ready + shareable_anonymous → allowed；shareable + ready + shareable_with_attribution → allowed；private-preview + limited → private-allowed。
- [x] 跑通。

### Task 6: 薄 CLI `package` / `install` / `verify-package` / `purge-run`

**Files:**
- Create: `scripts/cli_package.py`
- Create: `tests/test_cli_package.py`

**接口契约：**
- `python scripts/cli_package.py package --staging-root <path> --profile shareable|private-preview --output-dir <path>`：跑最终来源扫描 → 写 release-manifest → 构造目录包 + ZIP；exit `0`/`1`/`2`。
- `python scripts/cli_package.py install --dry-run --target <path> --package <path>` / `install --scope user --target <path> --package <path> [--force]`：dry-run 不写 target；user 写 target；拒绝标准位置。
- `python scripts/cli_package.py verify-package --package <path>`：解到 tmpdir + 跑 stage E + stage F + stage G 校验。
- `python scripts/cli_package.py purge-run --run-root <path>`：删 `run_root/dist/` 私有预览目录。
- 拒绝 system scope / 拒绝覆盖 / 拒绝标准位置。
- 退出码 `0` / `1` / `2`。

- [x] 写 5 个 `package` 单测：ready + shareable → 成功；limited + shareable → denied exit 2；limited + private-preview → 成功；blocked + private-preview → denied exit 2；incomplete + private-preview → denied exit 2。
- [x] 写 4 个 `install` 单测：dry-run 不写 target；user 写 target；标准位置被拒；已有同名 target 被拒（除非 `--force`）。
- [x] 写 3 个 `verify-package` 单测：合法 ZIP 通过；篡改 SKILL.md 后失败；缺 release-manifest 失败。
- [x] 写 1 个 `purge-run` 单测：成功删除 `run_root/dist/`。
- [x] 跑通。

### Task 7: 阶段 G 聚合验收门 + 报告

**Files:**
- Create: `scripts/check_stage_g.py`
- Create: `tests/test_stage_g_gates.py`

**接口契约：**
- `check_stage_g.py`：
  - 调 `check_stage_a..f.py` 不退化。
  - 跑 shareable happy path：stage F eval 产出 `ready` → `package --profile shareable` → 成功 → `verify-package` 通过。
  - 跑 private-preview path：stage F `mixed` profile → `final_state=limited` → `package --profile private-preview` → 成功 → `verify-package` 通过。
  - 跑 blocked path：`--profile contains_private` → `final_state=blocked` → 两条 package 都被拒。
  - 跑 install dry-run：解到 tmpdir 不写 target。
  - 跑 install user：写 target；拒绝覆盖；拒绝标准位置。
  - 跑"0 模型调用"反向断言：grep `stage_g` 全部脚本无 socket / urllib / requests import。
  - 跑"无来源正文 / 解盲映射进 release-manifest"反向断言。
  - 退出码 `0` / `1` invariant / `2` 端到端。
- 在 `docs/superpowers/reports/stage-g-YYYYMMDD.txt` 留报告。

- [x] 写 5 个聚合单测：阶段 A–F 不退化；shareable happy path；private-preview path；blocked 被拒；install dry-run 不写 target。
- [x] 写"0 模型调用"反向断言：grep `stage_g` 全部脚本无 socket / urllib / requests import。
- [x] 写"无隐私字段进 release-manifest"反向断言：构造含 source_body 的 manifest → 拒。
- [x] 跑通。

### Task 8: 阶段 G 状态与交付说明

**Files:**
- Modify: `docs/superpowers/specs/2026-10-09-wenfeng-skill-design.md`（追加"阶段 G 完成报告"段）
- Modify: `README.md`（追加"阶段 G 已交付"段）
- Modify: `SKILL.md`（末尾追加阶段状态注释）

- [x] 列出本阶段交付的脚本、产物路径、CLI 子命令与各自边界；明确**本阶段不声称效果已验证、不声称可分享**；release manifest 只证明产物与门禁记录相符，不构成版权或安全认证（spec §4.9）。
- [x] README 同上。
- [x] SKILL.md 末尾追加阶段状态注释。
- [x] 跑一次 `python scripts/check_stage_g.py` 把输出保存为 `docs/superpowers/reports/stage-g-YYYYMMDD.txt`。

## Rulings

- **Ruling-G1:** 阶段 G **复用**阶段 A 已有的 `release-manifest.schema.json`（已包含 spec §4.9 字段集：source_id / build_hash / gate_status / compatibility_targets / 6 个 hash 等）；不修改阶段 A 任何 schema；G 阶段重写 `schemas/examples/release-manifest.example.json` 让 example 与 schema 一致（example 是 schema 的示例，跟随 schema 不变）。
- **Ruling-G2:** 阶段 G **不**调模型；最终来源扫描、release manifest、确定性 ZIP、隔离安装、复检全在本地。
- **Ruling-G3:** `install --scope user --target <path>` 显式 opt-in；`--scope system` 永不被识别；`Path.home() / ".wenfeng-skill"` / `%APPDATA%/wenfeng-skill` 等标准位置**永不被写入**。
- **Ruling-G4:** ZIP mtime 固定为 1980-01-01 00:00:00；条目按相对路径字典序排序；相同输入 → 相同字节。
- **Ruling-G5:** `package --profile shareable` 仅当 `final_state="ready"` 且 `authorization_purpose` ∈ `{shareable_anonymous, shareable_with_attribution}` 时允许；`--profile private-preview` 仅当 `final_state="limited"` 时允许；`blocked` / `incomplete` 不进入 dist。
- **Ruling-G6:** `verify-package` 跨阶段：stage E `validate-dist`（直接对 staging subdir） + stage F `validate-evaluation`（对 staging subdir） + stage G `verify_release_manifest`（build_hash 复算）。
- **Ruling-G7:** `purge-run` 只删 `run_root/dist/` 私有预览；不动 `dist/<source_id>/<bundle_version>/`。
- **Ruling-G8:** 阶段 G **不**实现 `package` / `install` / `verify-package` / `purge-run` 之外的 spec §4.7 子命令；`list-runs` / `inspect-run` 等留待 spec 后续扩展。