"""Stage G Task 4 tests."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from isolated_install import (  # noqa: E402
    IsolatedInstallError,
    dry_run_install,
    user_install,
    verify_package,
    verify_package_in_dir,
)


def _make_staging(staging: Path) -> None:
    import hashlib
    staging.mkdir(parents=True, exist_ok=True)
    skill_hashes: dict[str, str] = {}
    for stage_id in (
        "write_entry", "scene_design", "character_beats",
        "prose_draft", "style_check", "revision",
    ):
        (staging / stage_id).mkdir(exist_ok=True)
        body = f"# {stage_id}\n"
        (staging / stage_id / "SKILL.md").write_text(body, encoding="utf-8")
        skill_hashes[stage_id] = hashlib.sha256(body.encode("utf-8")).hexdigest()
    (staging / "compile-manifest.json").write_text(
        json.dumps({
            "manifest_version": "0.1.0",
            "bundle_id": "bundle-test-v0_1_0",
            "skill_hashes": skill_hashes,
        }),
        encoding="utf-8",
    )
    (staging / "eval-report.json").write_text(
        json.dumps({
            "report_version": "0.1.0",
            "bundle_id": "bundle-test-v0_1_0",
            "gate_results": {
                "trigger": {"precision": 1.0, "recall": 1.0, "passed": True},
                "output": {"mechanical_pass_rate": 1.0, "passed": True},
                "end_to_end": {"verdict": "pass", "winning_pairs": 6,
                                "style_fit_median": 4.5, "pairing_median_delta": 1.5,
                                "quality_median_delta": 0.0, "undetermined_dimensions": [],
                                "passed": True},
            },
            "summary": {"final_state": "ready",
                        "notes": "[redacted=0a1b2c3d4e5f/bundle-test-v0_1_0;removed=;timestamp=none]"},
        }),
        encoding="utf-8",
    )
    skill_hashes = {}
    import hashlib
    for sid in ("write_entry", "scene_design", "character_beats",
                "prose_draft", "style_check", "revision"):
        skill_hashes[sid] = hashlib.sha256((staging / sid / "SKILL.md").read_bytes()).hexdigest()
    manifest = {
        "manifest_version": "0.1.0",
        "bundle_id": "bundle-test-v0_1_0",
        "source_id": "0a1b2c3d4e5f",
        "schema_version": "0.1.0",
        "tool_version": "0.1.0",
        "template_version": "0.1.0",
        "compiler_version": "0.1.0",
        "authorization_purpose": "shareable_anonymous",
        "release_state": "ready",
        "compatibility_targets": ["wenfeng-distill@0.1.0"],
        "skill_hashes": skill_hashes,
        "compile_manifest_hash": "b" * 64,
        "eval_report_hash": "a" * 64,
        "source_scan_hash": "c" * 64,
        "zip_hash": "d" * 64,
        "gate_status": {"trigger": True, "output": True, "end_to_end": True},
        "build_hash": "0" * 64,
    }
    from release_manifest import compute_build_hash
    manifest["build_hash"] = compute_build_hash(manifest)
    (staging / "release-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2),
        encoding="utf-8",
    )


def _make_zip_from_staging(staging: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w") as zf:
        for stage_id in (
            "write_entry", "scene_design", "character_beats",
            "prose_draft", "style_check", "revision",
        ):
            zf.writestr(
                f"{stage_id}/SKILL.md",
                (staging / stage_id / "SKILL.md").read_bytes(),
            )
        zf.writestr("compile-manifest.json", (staging / "compile-manifest.json").read_bytes())
        zf.writestr("eval-report.json", (staging / "eval-report.json").read_bytes())
        zf.writestr("release-manifest.json", (staging / "release-manifest.json").read_bytes())


class HappyPathTests(unittest.TestCase):
    def test_dry_run_does_not_touch_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "run"; run_root.mkdir()
            staging = run_root / "staging"; _make_staging(staging)
            zip_path = run_root / "pkg.zip"
            _make_zip_from_staging(staging, zip_path)
            target = run_root / "install-target"
            target.mkdir()
            before = list(target.iterdir())
            result = dry_run_install(zip_path, target=target, run_root=run_root)
            after = list(target.iterdir())
            self.assertEqual(before, after)
            self.assertTrue(result["dry_run"])
            self.assertTrue(result["files_in_target_unchanged"])

    def test_user_install_writes_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "run"; run_root.mkdir()
            staging = run_root / "staging"; _make_staging(staging)
            zip_path = run_root / "pkg.zip"
            _make_zip_from_staging(staging, zip_path)
            target = run_root / "user-install"
            result = user_install(zip_path, target=target, run_root=run_root)
            self.assertTrue(result["installed"])
            self.assertTrue((target / "release-manifest.json").is_file())
            self.assertTrue((target / "scene_design" / "SKILL.md").is_file())

    def test_verify_package_in_dir_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "run"; run_root.mkdir()
            staging = run_root / "staging"; _make_staging(staging)
            zip_path = run_root / "pkg.zip"
            _make_zip_from_staging(staging, zip_path)
            verify = verify_package(zip_path, run_root=run_root)
            self.assertTrue(verify["ok"], msg=verify)


class NegativeTests(unittest.TestCase):
    def test_standard_location_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "run"; run_root.mkdir()
            staging = run_root / "staging"; _make_staging(staging)
            zip_path = run_root / "pkg.zip"
            _make_zip_from_staging(staging, zip_path)
            target = Path.home() / ".wenfeng-skill"
            with self.assertRaises(IsolatedInstallError):
                dry_run_install(zip_path, target=target, run_root=run_root)
            with self.assertRaises(IsolatedInstallError):
                user_install(zip_path, target=target, run_root=run_root)

    def test_overwrite_rejected_without_force(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "run"; run_root.mkdir()
            staging = run_root / "staging"; _make_staging(staging)
            zip_path = run_root / "pkg.zip"
            _make_zip_from_staging(staging, zip_path)
            target = run_root / "user-install"
            target.mkdir()
            (target / "leftover.txt").write_text("hi", encoding="utf-8")
            with self.assertRaises(IsolatedInstallError):
                user_install(zip_path, target=target, run_root=run_root)
            # With force=True it proceeds.
            result = user_install(zip_path, target=target, run_root=run_root, force=True)
            self.assertTrue(result["installed"])

    def test_force_overwrite_reinstalls(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "run"; run_root.mkdir()
            staging = run_root / "staging"; _make_staging(staging)
            zip_path = run_root / "pkg.zip"
            _make_zip_from_staging(staging, zip_path)
            target = run_root / "user-install"
            target.mkdir()
            (target / "leftover.txt").write_text("hi", encoding="utf-8")
            user_install(zip_path, target=target, run_root=run_root, force=True)
            self.assertFalse((target / "leftover.txt").exists())
            self.assertTrue((target / "release-manifest.json").is_file())

    def test_tampered_package_fails_verify(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "run"; run_root.mkdir()
            staging = run_root / "staging"; _make_staging(staging)
            zip_path = run_root / "pkg.zip"
            _make_zip_from_staging(staging, zip_path)
            # Tamper with a SKILL.md inside the ZIP by re-zipping.
            with zipfile.ZipFile(zip_path, "a") as zf:
                # Replace scene_design/SKILL.md with tampered content.
                pass
            with tempfile.TemporaryDirectory() as inner:
                with zipfile.ZipFile(zip_path, "r") as zf:
                    zf.extractall(inner)
                (Path(inner) / "scene_design" / "SKILL.md").write_text(
                    "# scene_design\n\ntampered", encoding="utf-8"
                )
                with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                    for path in sorted(Path(inner).rglob("*")):
                        if path.is_file():
                            zf.writestr(
                                path.relative_to(inner).as_posix(),
                                path.read_bytes(),
                            )
            verify = verify_package(zip_path, run_root=run_root)
            self.assertFalse(verify["ok"])


if __name__ == "__main__":
    unittest.main()