"""Stage E Task 5 tests."""

from __future__ import annotations

import json
import sys
import tarfile
import tempfile
import unittest
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from concurrency_lock import LockBusy  # noqa: E402
from deterministic_compiler import (  # noqa: E402
    ExistingStagingRootError,
    PreflightError,
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
            {"mechanism_id": "M02", "stage_bindings": ["scene_design"], "evidence_summary": {"unique_scenes": 3, "unique_chapters": 2}},
        ],
        "stage_bindings": {
            "write_entry": [], "scene_design": ["M02"], "character_beats": [],
            "prose_draft": ["M01"], "style_check": ["M01"], "revision": ["M01"],
        },
        "content_exclusions": ["named_character_profiles"],
        "evaluation_ref": "private-ledger://synthetic",
        "bundle_id": "bundle-0a1b2c3d4e5f-v0_1_0",
    }


def _stage_root_setup(tmp: Path) -> tuple[Path, Path, str]:
    """Return ``(run_root, staging, lock_key)`` with a unique per-call lock_key."""
    run_root = tmp / "run"
    run_root.mkdir()
    staging = run_root / "staging"
    lock_key = f"wenfeng.compile.{uuid.uuid4().hex}"
    return run_root, staging, lock_key


class CompilerNegativeTests(unittest.TestCase):
    def test_existing_non_empty_staging_root_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root, staging, lock_key = _stage_root_setup(Path(tmp))
            staging.mkdir()
            (staging / "leftover.txt").write_text("hi", encoding="utf-8")
            with self.assertRaises(ExistingStagingRootError):
                compile_six_skills(
                    _bundle(),
                    templates_root=PROJECT_ROOT / "templates" / "stages",
                    staging_root=staging,
                    lock_root=run_root, lock_key=lock_key,
                )

    def test_missing_template_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root, staging, lock_key = _stage_root_setup(Path(tmp))
            bad_templates = run_root / "no_templates"
            bad_templates.mkdir()
            from deterministic_compiler import CompilerError
            with self.assertRaises(CompilerError):
                compile_six_skills(
                    _bundle(),
                    templates_root=bad_templates,
                    staging_root=staging,
                    lock_root=run_root, lock_key=lock_key,
                )

    def test_invalid_bundle_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root, staging, lock_key = _stage_root_setup(Path(tmp))
            from deterministic_compiler import CompilerError
            with self.assertRaises(CompilerError):
                compile_six_skills(
                    {},
                    templates_root=PROJECT_ROOT / "templates" / "stages",
                    staging_root=staging,
                    lock_root=run_root, lock_key=lock_key,
                )

    def test_concurrent_compile_returns_busy(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root, staging, lock_key = _stage_root_setup(Path(tmp))
            from concurrency_lock import acquire
            holder = acquire(run_root, lock_key)
            try:
                with self.assertRaises(LockBusy):
                    compile_six_skills(
                        _bundle(),
                        templates_root=PROJECT_ROOT / "templates" / "stages",
                        staging_root=staging,
                        lock_root=run_root, lock_key=lock_key,
                    )
            finally:
                holder.release()


class CompilerHappyPathTests(unittest.TestCase):
    def test_six_skills_emitted_with_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root, staging, lock_key = _stage_root_setup(Path(tmp))
            result = compile_six_skills(
                _bundle(),
                templates_root=PROJECT_ROOT / "templates" / "stages",
                staging_root=staging,
                lock_root=run_root, lock_key=lock_key,
            )
            self.assertTrue((staging / "compile-manifest.json").is_file())
            self.assertEqual(result.manifest["source_id"], _bundle()["source_id"])
            self.assertEqual(result.manifest["schema_version"], "0.2.0")
            for stage_id in ("write_entry", "scene_design", "character_beats",
                              "prose_draft", "style_check", "revision"):
                self.assertTrue((staging / stage_id / "SKILL.md").is_file(),
                                f"{stage_id}/SKILL.md missing")
            self.assertIn(stage_id, result.manifest["skill_hashes"])

    def test_two_runs_byte_identical(self):
        """Same inputs -> byte-identical staging tar (Ruling-E3 verification)."""
        with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
            run_root1, staging1, lock_key1 = _stage_root_setup(Path(tmp1))
            run_root2, staging2, lock_key2 = _stage_root_setup(Path(tmp2))

            m1 = compile_six_skills(
                _bundle(),
                templates_root=PROJECT_ROOT / "templates" / "stages",
                staging_root=staging1,
                lock_root=run_root1,
                lock_key=lock_key1,
            ).manifest
            m2 = compile_six_skills(
                _bundle(),
                templates_root=PROJECT_ROOT / "templates" / "stages",
                staging_root=staging2,
                lock_root=run_root2,
                lock_key=lock_key2,
            ).manifest

            tar1 = Path(tmp1) / "a.tar"
            tar2 = Path(tmp2) / "b.tar"
            with tarfile.open(tar1, "w") as tf:
                tf.add(staging1, arcname="staging")
            with tarfile.open(tar2, "w") as tf:
                tf.add(staging2, arcname="staging")
            # tar metadata (mtime) legitimately differs across runs; compare
            # file bytes instead. Walking the tar in deterministic order and
            # hashing each member body.
            def tar_member_bytes(path: Path) -> bytes:
                buf = bytearray()
                with tarfile.open(path, "r") as tf:
                    for member in sorted(tf.getmembers(), key=lambda m: m.name):
                        if not member.isfile():
                            continue
                        extracted = tf.extractfile(member).read()
                        buf.extend(member.name.encode("utf-8"))
                        buf.append(0)
                        buf.extend(extracted)
                        buf.append(0)
                return bytes(buf)
            self.assertEqual(tar_member_bytes(tar1), tar_member_bytes(tar2),
                             f"manifests:\n{m1}\n{m2}")

    def test_failure_does_not_write_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root, staging, lock_key = _stage_root_setup(Path(tmp))
            bad_templates = run_root / "no_templates"
            bad_templates.mkdir()
            from deterministic_compiler import CompilerError
            try:
                compile_six_skills(
                    _bundle(),
                    templates_root=bad_templates,
                    staging_root=staging,
                    lock_root=run_root, lock_key=lock_key,
                )
            except CompilerError:
                pass
            self.assertFalse((staging / "compile-manifest.json").exists())


class ValidateDistTests(unittest.TestCase):
    def test_validate_clean_staging(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root, staging, lock_key = _stage_root_setup(Path(tmp))
            compile_six_skills(
                _bundle(),
                templates_root=PROJECT_ROOT / "templates" / "stages",
                staging_root=staging,
                lock_root=run_root, lock_key=lock_key,
            )
            errors = validate_dist(staging, run_root=run_root)
            self.assertEqual(errors, [], errors)

    def test_validate_detects_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root, staging, lock_key = _stage_root_setup(Path(tmp))
            compile_six_skills(
                _bundle(),
                templates_root=PROJECT_ROOT / "templates" / "stages",
                staging_root=staging,
                lock_root=run_root, lock_key=lock_key,
            )
            # Tamper with a Skill body.
            tampered = staging / "scene_design" / "SKILL.md"
            tampered.write_text(
                tampered.read_text(encoding="utf-8") + "\n\naddendum",
                encoding="utf-8",
            )
            errors = validate_dist(staging, run_root=run_root)
            self.assertTrue(any("hash mismatch" in e for e in errors), errors)

    def test_validate_missing_manifest_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root, staging, lock_key = _stage_root_setup(Path(tmp))
            errors = validate_dist(staging, run_root=run_root)
            self.assertTrue(any("compile-manifest.json missing" in e for e in errors), errors)


class LiteralScanAtCompileTests(unittest.TestCase):
    def test_literal_scan_blocks_with_exact_copy(self):
        from deterministic_compiler import PreflightError
        with tempfile.TemporaryDirectory() as tmp:
            run_root, staging, lock_key = _stage_root_setup(Path(tmp))
            # Inject a verbatim copy of a chunk of the real reference into the
            # first stage by patching the template.
            templates_dir = run_root / "templates_with_copy"
            templates_dir.mkdir()
            for stage_id in ("write_entry", "scene_design", "character_beats",
                              "prose_draft", "style_check", "revision"):
                src = PROJECT_ROOT / "templates" / "stages" / f"{stage_id}.md"
                dst = templates_dir / f"{stage_id}.md"
                dst.write_text(
                    src.read_text(encoding="utf-8")
                    + "\n\n## 来源副本\n这是一段长达 40 个字符的来源正文用于长段连续匹配测试。\n",
                    encoding="utf-8",
                )
            reference = "这是一段长达 40 个字符的来源正文用于长段连续匹配测试。"
            with self.assertRaises(PreflightError):
                compile_six_skills(
                    _bundle(),
                    templates_root=templates_dir,
                    staging_root=staging,
                    lock_root=run_root, lock_key=lock_key,
                    reference_corpus_for_literal_scan=reference,
                    long_substrings_for_literal_scan=[reference],
                    min_continuous_match=20,
                )


if __name__ == "__main__":
    unittest.main()
