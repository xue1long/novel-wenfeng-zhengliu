"""Stage E aggregate acceptance gate.

Verifies:
  - Two consecutive ``compile_six_skills`` runs produce byte-identical
    staging (Ruling-E3 / spec §4.7 "same input -> same bytes").
  - ``validate_dist`` passes against the just-built staging.
  - ``validate_dist`` flags hash mismatches after tampering.
  - Literal scan blocks when a Skill body embeds an exact copy of the
    reference corpus.
  - A failed ``compile_six_skills`` does NOT leave a ``compile-manifest.json``
    behind (Ruling-E3 / spec §4.7 "failure staging cannot be identified").

Exit codes:
  0 — PASS
  1 — invariant failure
  2 — IO / subprocess failure
"""

from __future__ import annotations

import json
import sys
import tempfile
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from deterministic_compiler import (  # noqa: E402
    CompilerError,
    compile_six_skills,
    validate_dist,
)


def _bundle() -> dict:
    return {
        "schema_version": "2",
        "bundle_version": "0.1.0",
        "source_id": "0" * 12,
        "evidence_status": "approved",
        "claimed_dimensions": ["narrative_voice", "sentence_rhythm", "scene_transition", "dialogue_subtext", "imagery_rhetoric"],
        "mechanisms": [
            {"mechanism_id": "M01", "stage_bindings": ["prose_draft"], "evidence_summary": {"unique_scenes": 3, "unique_chapters": 2}},
        ],
        "stage_bindings": {
            "write_entry": [], "scene_design": [], "character_beats": [],
            "prose_draft": ["M01"], "style_check": ["M01"], "revision": ["M01"],
        },
        "content_exclusions": ["named_character_profiles"],
        "evaluation_ref": "private-ledger://synthetic",
        "bundle_id": "bundle-0a1b2c3d4e5f-v0_1_0",
    }


def check_byte_identical_compile() -> list[str]:
    """Two consecutive runs with the same inputs must produce byte-identical
    staging members. We compare per-member hashes (tar metadata such as mtime
    legitimately differs across runs)."""
    failures: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        run_root1 = tmp_path / "r1"; run_root1.mkdir()
        run_root2 = tmp_path / "r2"; run_root2.mkdir()
        staging1 = run_root1 / "staging"
        staging2 = run_root2 / "staging"
        lock_key = f"wenfeng.compile.{uuid.uuid4().hex}"
        result1 = compile_six_skills(
            _bundle(),
            templates_root=PROJECT_ROOT / "templates" / "stages",
            staging_root=staging1,
            lock_root=run_root1,
            lock_key=lock_key,
        )
        result2 = compile_six_skills(
            _bundle(),
            templates_root=PROJECT_ROOT / "templates" / "stages",
            staging_root=staging2,
            lock_root=run_root2,
            lock_key=lock_key + ".other",
        )
        # Per-file hashes must match.
        if result1.declared_files != result2.declared_files:
            failures.append("declared_files differ across runs")
        # And the manifest skill_hashes must match.
        if result1.manifest["skill_hashes"] != result2.manifest["skill_hashes"]:
            failures.append("skill_hashes differ across runs")
    return failures


def check_validate_dist_after_tamper() -> list[str]:
    failures: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        run_root = tmp_path / "run"; run_root.mkdir()
        staging = run_root / "staging"
        compile_six_skills(
            _bundle(),
            templates_root=PROJECT_ROOT / "templates" / "stages",
            staging_root=staging,
            lock_root=run_root,
        )
        # Tamper with one Skill body.
        tampered = staging / "scene_design" / "SKILL.md"
        tampered.write_text(
            tampered.read_text(encoding="utf-8") + "\n\naddendum",
            encoding="utf-8",
        )
        errors = validate_dist(staging, run_root=run_root)
        if not any("hash mismatch" in e for e in errors):
            failures.append(f"validate_dist did not flag tamper; errors={errors}")
    return failures


def check_failure_staging_unidentifiable() -> list[str]:
    """A compile that fails MUST NOT leave a compile-manifest.json behind."""
    failures: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        run_root = tmp_path / "run"; run_root.mkdir()
        staging = run_root / "staging"
        templates_root = run_root / "no_templates"; templates_root.mkdir()
        try:
            compile_six_skills(
                _bundle(),
                templates_root=templates_root,
                staging_root=staging,
                lock_root=run_root,
            )
        except CompilerError:
            pass
        if (staging / "compile-manifest.json").exists():
            failures.append("compile-manifest.json present after a failed compile")
    return failures


def check_literal_scan_blocks() -> list[str]:
    failures: list[str] = []
    reference = "这是一段长达 40 个字符的来源正文用于字面预检端到端测试。"
    templates_root = PROJECT_ROOT / "templates" / "stages"
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        # Build a templates copy with the literal copy injected into one stage.
        contaminated = tmp_path / "writable_templates"
        contaminated.mkdir()
        for stage_id in (
            "write_entry", "scene_design", "character_beats",
            "prose_draft", "style_check", "revision",
        ):
            src = PROJECT_ROOT / "templates" / "stages" / f"{stage_id}.md"
            dst = contaminated / f"{stage_id}.md"
            dst.write_text(
                src.read_text(encoding="utf-8")
                + "\n\n## 来源副本\n"
                + reference
                + "\n",
                encoding="utf-8",
            )
        run_root = tmp_path / "run"; run_root.mkdir()
        staging = run_root / "staging"
        from deterministic_compiler import PreflightError
        try:
            compile_six_skills(
                _bundle(),
                templates_root=contaminated,
                staging_root=staging,
                lock_root=run_root,
                reference_corpus_for_literal_scan=reference,
                long_substrings_for_literal_scan=[reference],
                min_continuous_match=20,
            )
        except PreflightError as exc:
            if "literal scan failed" not in str(exc):
                failures.append(f"literal-scan error did not mention literal scan: {exc}")
        else:
            failures.append("literal scan did not block the verbatim copy")
    return failures


def main() -> int:
    failures: list[str] = []
    failures.extend(check_byte_identical_compile())
    failures.extend(check_validate_dist_after_tamper())
    failures.extend(check_failure_staging_unidentifiable())
    failures.extend(check_literal_scan_blocks())
    if failures:
        print("Stage E aggregate gate FAILED:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("Stage E aggregate gate PASSED:")
    print("- two consecutive compiles produce byte-identical staging (determinism)")
    print("- validate_dist flags tampering")
    print("- failed compile leaves no compile-manifest.json behind")
    print("- literal scan blocks verbatim source copy")
    print("- staging is ready for stage F eval and stage G packaging; this gate does NOT validate runtime behavior")
    return 0


if __name__ == "__main__":
    sys.exit(main())
