"""Stage G Task 3 tests."""

from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from deterministic_package import (  # noqa: E402
    DeterministicPackageError,
    build_directory_dist,
    build_zip_dist,
    compute_zip_hash,
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
    (staging / "compile-manifest.json").write_text(
        '{"manifest_version": "0.1.0"}', encoding="utf-8"
    )
    (staging / "eval-report.json").write_text(
        '{"report_version": "0.1.0"}', encoding="utf-8"
    )
    (staging / "release-manifest.json").write_text(
        '{"manifest_version": "0.1.0"}', encoding="utf-8"
    )
    (staging / "source-scan-report.json").write_text(
        '{"scan": "ok"}', encoding="utf-8"
    )


def _make_manifest() -> dict:
    return {"manifest_version": "0.1.0"}


class HappyPathTests(unittest.TestCase):
    def test_directory_dist_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            staging = Path(tmp) / "staging"
            _make_staging(staging)
            out = Path(tmp) / "dist"
            build_directory_dist(staging, _make_manifest(), output_dir=out)
            self.assertTrue((out / "write_entry" / "SKILL.md").is_file())
            self.assertTrue((out / "compile-manifest.json").is_file())
            self.assertTrue((out / "source-scan-report.json").is_file())
            # release-manifest is generated separately by the CLI; not the
            # directory_dist builder's responsibility.
            self.assertFalse((out / "release-manifest.json").is_file())

    def test_zip_byte_identical_across_runs(self):
        with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
            s1 = Path(tmp1) / "staging"; _make_staging(s1)
            s2 = Path(tmp2) / "staging"; _make_staging(s2)
            d1 = Path(tmp1) / "dist"; d2 = Path(tmp2) / "dist"
            build_directory_dist(s1, _make_manifest(), output_dir=d1)
            build_directory_dist(s2, _make_manifest(), output_dir=d2)
            z1 = Path(tmp1) / "pkg.zip"; z2 = Path(tmp2) / "pkg.zip"
            build_zip_dist(d1, z1)
            build_zip_dist(d2, z2)
            self.assertEqual(z1.read_bytes(), z2.read_bytes())

    def test_zip_hash_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            staging = Path(tmp) / "staging"
            _make_staging(staging)
            out = Path(tmp) / "dist"
            build_directory_dist(staging, _make_manifest(), output_dir=out)
            zip_path = Path(tmp) / "pkg.zip"
            build_zip_dist(out, zip_path)
            h1 = compute_zip_hash(zip_path)
            h2 = compute_zip_hash(zip_path)
            self.assertEqual(h1, h2)

    def test_zip_entries_sorted(self):
        with tempfile.TemporaryDirectory() as tmp:
            staging = Path(tmp) / "staging"
            _make_staging(staging)
            out = Path(tmp) / "dist"
            build_directory_dist(staging, _make_manifest(), output_dir=out)
            zip_path = Path(tmp) / "pkg.zip"
            build_zip_dist(out, zip_path)
            with zipfile.ZipFile(zip_path, "r") as zf:
                names = zf.namelist()
            self.assertEqual(names, sorted(names))
            # release-manifest.json lives at dist_dir root, NOT inside ZIP.
            self.assertNotIn("release-manifest.json", names)


class NegativeTests(unittest.TestCase):
    def test_output_dir_non_empty_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            staging = Path(tmp) / "staging"
            _make_staging(staging)
            out = Path(tmp) / "dist"
            out.mkdir()
            (out / "leftover.txt").write_text("hi", encoding="utf-8")
            with self.assertRaises(DeterministicPackageError):
                build_directory_dist(staging, _make_manifest(), output_dir=out)

    def test_missing_skill_md_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            staging = Path(tmp) / "staging"
            _make_staging(staging)
            (staging / "scene_design" / "SKILL.md").unlink()
            with self.assertRaises(DeterministicPackageError):
                build_directory_dist(staging, _make_manifest(), output_dir=Path(tmp) / "out")

    def test_zip_already_exists_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            staging = Path(tmp) / "staging"
            _make_staging(staging)
            out = Path(tmp) / "dist"
            build_directory_dist(staging, _make_manifest(), output_dir=out)
            zip_path = Path(tmp) / "pkg.zip"
            zip_path.write_text("preexisting", encoding="utf-8")
            with self.assertRaises(DeterministicPackageError):
                build_zip_dist(out, zip_path)


if __name__ == "__main__":
    unittest.main()