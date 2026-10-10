"""Stage G Task 2 tests."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from release_manifest import (  # noqa: E402
    ReleaseManifestError,
    build_release_manifest,
    compute_build_hash,
    verify_release_manifest,
    write_release_manifest,
)


def _make_staging(staging: Path) -> None:
    staging.mkdir(parents=True, exist_ok=True)
    for stage_id in (
        "write_entry", "scene_design", "character_beats",
        "prose_draft", "style_check", "revision",
    ):
        (staging / stage_id).mkdir(exist_ok=True)
        (staging / stage_id / "SKILL.md").write_text(
            f"# {stage_id}\n", encoding="utf-8"
        )


def _make_zip(path: Path, staging: Path) -> None:
    with zipfile.ZipFile(path, "w") as zf:
        for stage_id in (
            "write_entry", "scene_design", "character_beats",
            "prose_draft", "style_check", "revision",
        ):
            zf.writestr(f"{stage_id}/SKILL.md", f"# {stage_id}\n")


def _good_kwargs(staging: Path) -> dict:
    zip_path = staging.parent / "pkg.zip"
    _make_zip(zip_path, staging)
    return {
        "staging_root": staging,
        "bundle_id": "bundle-test-v0_1_0",
        "source_id": "0a1b2c3d4e5f",
        "authorization_purpose": "shareable_anonymous",
        "release_state": "ready",
        "eval_report_hash": "a" * 64,
        "final_scan_result": {"coverage_ratio": 1.0, "policy": {"policy_version": "0.1.0"}},
        "zip_path": zip_path,
        "compile_manifest_hash": "b" * 64,
        "compatibility_targets": ["wenfeng-distill@0.1.0"],
        "gate_status": {"trigger": True, "output": True, "end_to_end": True},
    }


class HappyPathTests(unittest.TestCase):
    def test_build_manifest_succeeds(self):
        with tempfile.TemporaryDirectory() as tmp:
            staging = Path(tmp) / "staging"
            _make_staging(staging)
            manifest = build_release_manifest(**_good_kwargs(staging))
            self.assertEqual(len(manifest["skill_hashes"]), 6)
            self.assertEqual(len(manifest["build_hash"]), 64)
            for stage_id in (
                "write_entry", "scene_design", "character_beats",
                "prose_draft", "style_check", "revision",
            ):
                self.assertIn(stage_id, manifest["skill_hashes"])

    def test_write_manifest_passes_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            staging = Path(tmp) / "staging"
            _make_staging(staging)
            manifest = build_release_manifest(**_good_kwargs(staging))
            out = Path(tmp) / "dist"
            path = write_release_manifest(manifest, out)
            self.assertTrue(path.is_file())

    def test_determinism_same_input_same_build_hash(self):
        with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
            s1 = Path(tmp1) / "staging"; _make_staging(s1)
            s2 = Path(tmp2) / "staging"; _make_staging(s2)
            m1 = build_release_manifest(**_good_kwargs(s1))
            m2 = build_release_manifest(**_good_kwargs(s2))
            self.assertEqual(m1["build_hash"], m2["build_hash"])

    def test_verify_release_manifest_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            staging = Path(tmp) / "staging"
            _make_staging(staging)
            manifest = build_release_manifest(**_good_kwargs(staging))
            errors = verify_release_manifest(manifest, staging_root=staging)
            self.assertEqual(errors, [], errors)


class NegativeTests(unittest.TestCase):
    def test_forbidden_field_rejected_on_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            staging = Path(tmp) / "staging"
            _make_staging(staging)
            manifest = build_release_manifest(**_good_kwargs(staging))
            manifest["source_body"] = "do not leak me"
            with self.assertRaises(ReleaseManifestError):
                write_release_manifest(manifest, Path(tmp) / "dist")

    def test_unblinding_map_rejected_on_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            staging = Path(tmp) / "staging"
            _make_staging(staging)
            manifest = build_release_manifest(**_good_kwargs(staging))
            manifest["unblinding_map"] = {"EP-00": "secret"}
            with self.assertRaises(ReleaseManifestError):
                write_release_manifest(manifest, Path(tmp) / "dist")

    def test_build_hash_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            staging = Path(tmp) / "staging"
            _make_staging(staging)
            manifest = build_release_manifest(**_good_kwargs(staging))
            manifest["build_hash"] = "f" * 64
            errors = verify_release_manifest(manifest)
            self.assertTrue(any("build_hash" in e for e in errors), errors)

    def test_missing_zip_path_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            staging = Path(tmp) / "staging"
            _make_staging(staging)
            kwargs = _good_kwargs(staging)
            kwargs["zip_path"] = Path(tmp) / "no-such.zip"
            with self.assertRaises(ReleaseManifestError):
                build_release_manifest(**kwargs)

    def test_missing_skill_md_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            staging = Path(tmp) / "staging"
            _make_staging(staging)
            (staging / "scene_design" / "SKILL.md").unlink()
            with self.assertRaises(ReleaseManifestError):
                build_release_manifest(**_good_kwargs(staging))

    def test_compute_build_hash_stable(self):
        a = compute_build_hash({"k": "v", "build_hash": "0" * 64})
        b = compute_build_hash({"k": "v", "build_hash": "0" * 64})
        self.assertEqual(a, b)


class CrossFieldConsistencyTests(unittest.TestCase):
    def test_live_skill_hash_mismatch_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            staging = Path(tmp) / "staging"
            _make_staging(staging)
            manifest = build_release_manifest(**_good_kwargs(staging))
            # Tamper with a Skill body in staging.
            (staging / "scene_design" / "SKILL.md").write_text(
                "# scene_design\n\naddendum", encoding="utf-8"
            )
            errors = verify_release_manifest(manifest, staging_root=staging)
            self.assertTrue(any("scene_design" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()