"""Stage G Task 6 tests."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _run(args: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        [sys.executable, "-u", "scripts/cli_package.py", *args],
        cwd=str(cwd or PROJECT_ROOT),
        capture_output=True,
        timeout=60,
    )
    return subprocess.CompletedProcess(
        proc.args,
        proc.returncode,
        proc.stdout.decode("utf-8", errors="replace") if proc.stdout else "",
        proc.stderr.decode("utf-8", errors="replace") if proc.stderr else "",
    )


def _make_staging(staging: Path, *, final_state: str = "ready") -> None:
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
            "bundle_id": "bundletestv0010",
            "source_id": "0a1b2c3d4e5f",
            "evidence_status": "approved" if final_state == "ready" else "limited",
            "skill_hashes": skill_hashes,
        }),
        encoding="utf-8",
    )
    (staging / "eval-report.json").write_text(
        json.dumps({
            "report_version": "0.1.0",
            "bundle_id": "bundletestv0010",
            "gate_results": {
                "trigger": {"precision": 1.0, "recall": 1.0, "passed": True},
                "output": {"mechanical_pass_rate": 1.0, "passed": True},
                "end_to_end": {"verdict": "pass", "winning_pairs": 6,
                                "style_fit_median": 4.5, "pairing_median_delta": 1.5,
                                "quality_median_delta": 0.0, "undetermined_dimensions": [],
                                "passed": True},
            },
            "summary": {"final_state": final_state,
                        "notes": "[redacted=0a1b2c3d4e5f/bundletestv0010;removed=;timestamp=none]"},
        }),
        encoding="utf-8",
    )


def _make_run_manifest(run_root: Path, *, auth: str) -> None:
    (run_root / "run-manifest.json").write_text(
        json.dumps({"authorization_purpose": auth, "run_id": "r-test"}),
        encoding="utf-8",
    )


class PackageTests(unittest.TestCase):
    def test_help_builds_parser(self):
        r = _run(["--help"])
        self.assertEqual(r.returncode, 0, msg=r.stdout + r.stderr)

    def test_shareable_happy_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "run"; run_root.mkdir()
            staging = run_root / "staging"; _make_staging(staging, final_state="ready")
            _make_run_manifest(run_root, auth="shareable_anonymous")
            output_dir = Path(tmp) / "shareable"
            r = _run([
                "package",
                "--staging-root", str(staging),
                "--run-root", str(run_root),
                "--output-dir", str(output_dir),
                "--run-manifest", str(run_root / "run-manifest.json"),
                "--profile", "shareable",
            ])
            self.assertEqual(r.returncode, 0, msg=r.stdout + r.stderr)
            # The dist directory contains a release-manifest.json + ZIP.
            dist = output_dir / "0a1b2c3d4e5f" / "bundletestv0010" / "v0.1.0"
            self.assertTrue((dist / "release-manifest.json").is_file())
            self.assertTrue((dist / "package.zip").is_file())

    def test_shareable_denied_for_limited(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "run"; run_root.mkdir()
            staging = run_root / "staging"; _make_staging(staging, final_state="limited")
            _make_run_manifest(run_root, auth="shareable_anonymous")
            output_dir = Path(tmp) / "shareable"
            r = _run([
                "package",
                "--staging-root", str(staging),
                "--run-root", str(run_root),
                "--output-dir", str(output_dir),
                "--run-manifest", str(run_root / "run-manifest.json"),
                "--profile", "shareable",
            ])
            self.assertEqual(r.returncode, 2, msg=r.stdout + r.stderr)
            self.assertIn("refused", r.stdout + r.stderr)

    def test_private_preview_happy_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "run"; run_root.mkdir()
            staging = run_root / "staging"; _make_staging(staging, final_state="limited")
            _make_run_manifest(run_root, auth="private_only")
            output_dir = Path(tmp) / "shareable"
            r = _run([
                "package",
                "--staging-root", str(staging),
                "--run-root", str(run_root),
                "--output-dir", str(output_dir),
                "--run-manifest", str(run_root / "run-manifest.json"),
                "--profile", "private-preview",
            ])
            self.assertEqual(r.returncode, 0, msg=r.stdout + r.stderr)
            self.assertTrue((run_root / "dist" / "private" / "bundletestv0010" / "release-manifest.json").is_file())

    def test_blocked_private_preview_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "run"; run_root.mkdir()
            staging = run_root / "staging"; _make_staging(staging, final_state="blocked")
            _make_run_manifest(run_root, auth="private_only")
            output_dir = Path(tmp) / "shareable"
            r = _run([
                "package",
                "--staging-root", str(staging),
                "--run-root", str(run_root),
                "--output-dir", str(output_dir),
                "--run-manifest", str(run_root / "run-manifest.json"),
                "--profile", "private-preview",
            ])
            self.assertEqual(r.returncode, 2, msg=r.stdout + r.stderr)
            self.assertIn("refused", r.stdout + r.stderr)

    def test_incomplete_private_preview_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "run"; run_root.mkdir()
            staging = run_root / "staging"; _make_staging(staging, final_state="incomplete")
            _make_run_manifest(run_root, auth="private_only")
            output_dir = Path(tmp) / "shareable"
            r = _run([
                "package",
                "--staging-root", str(staging),
                "--run-root", str(run_root),
                "--output-dir", str(output_dir),
                "--run-manifest", str(run_root / "run-manifest.json"),
                "--profile", "private-preview",
            ])
            self.assertEqual(r.returncode, 2)


class InstallTests(unittest.TestCase):
    def _make_package(self, run_root: Path) -> Path:
        staging = run_root / "staging"; _make_staging(staging, final_state="ready")
        _make_run_manifest(run_root, auth="shareable_anonymous")
        output_dir = run_root / "shareable"
        r = _run([
            "package",
            "--staging-root", str(staging),
            "--run-root", str(run_root),
            "--output-dir", str(output_dir),
            "--run-manifest", str(run_root / "run-manifest.json"),
            "--profile", "shareable",
        ])
        self.assertEqual(r.returncode, 0, msg=r.stdout + r.stderr)
        # The ZIP lives at dist_dir/package.zip.
        return list((output_dir / "0a1b2c3d4e5f" / "bundletestv0010" / "v0.1.0").glob("package.zip"))[0]

    def test_install_dry_run_does_not_touch_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "run"; run_root.mkdir()
            pkg = self._make_package(run_root)
            target = run_root / "user-install"
            target.mkdir()
            (target / "existing.txt").write_text("hi", encoding="utf-8")
            before = list(target.iterdir())
            r = _run([
                "install",
                "--package", str(pkg),
                "--run-root", str(run_root),
                "--target", str(target),
            ])
            self.assertEqual(r.returncode, 0, msg=r.stdout + r.stderr)
            after = list(target.iterdir())
            self.assertEqual(before, after)

    def test_install_user_scope_writes_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "run"; run_root.mkdir()
            pkg = self._make_package(run_root)
            target = run_root / "user-install"
            r = _run([
                "install",
                "--package", str(pkg),
                "--run-root", str(run_root),
                "--target", str(target),
                "--scope", "user",
                "--apply",
            ])
            self.assertEqual(r.returncode, 0, msg=r.stdout + r.stderr)
            self.assertTrue((target / "release-manifest.json").is_file())

    def test_install_user_scope_refuses_standard_location(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "run"; run_root.mkdir()
            pkg = self._make_package(run_root)
            target = Path.home() / ".wenfeng-skill"
            r = _run([
                "install",
                "--package", str(pkg),
                "--run-root", str(run_root),
                "--target", str(target),
                "--scope", "user",
                "--apply",
            ])
            self.assertEqual(r.returncode, 2, msg=r.stdout + r.stderr)
            self.assertIn("standard location", r.stdout + r.stderr)

    def test_install_user_scope_refuses_existing_without_force(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "run"; run_root.mkdir()
            pkg = self._make_package(run_root)
            target = run_root / "user-install"
            target.mkdir()
            (target / "leftover.txt").write_text("hi", encoding="utf-8")
            r = _run([
                "install",
                "--package", str(pkg),
                "--run-root", str(run_root),
                "--target", str(target),
                "--scope", "user",
                "--apply",
            ])
            self.assertEqual(r.returncode, 2, msg=r.stdout + r.stderr)
            self.assertIn("non-empty", r.stdout + r.stderr)


class VerifyPackageTests(unittest.TestCase):
    def test_verify_clean_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "run"; run_root.mkdir()
            staging = run_root / "staging"; _make_staging(staging, final_state="ready")
            _make_run_manifest(run_root, auth="shareable_anonymous")
            output_dir = run_root / "shareable"
            r = _run([
                "package",
                "--staging-root", str(staging),
                "--run-root", str(run_root),
                "--output-dir", str(output_dir),
                "--run-manifest", str(run_root / "run-manifest.json"),
                "--profile", "shareable",
            ])
            self.assertEqual(r.returncode, 0, msg=r.stdout + r.stderr)
            pkg = list((output_dir / "0a1b2c3d4e5f" / "bundletestv0010" / "v0.1.0").glob("package.zip"))[0]
            r = _run(["verify-package", "--package", str(pkg), "--run-root", str(run_root)])
            self.assertEqual(r.returncode, 0, msg=r.stdout + r.stderr)

    def test_verify_tampered_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "run"; run_root.mkdir()
            staging = run_root / "staging"; _make_staging(staging, final_state="ready")
            _make_run_manifest(run_root, auth="shareable_anonymous")
            output_dir = run_root / "shareable"
            r = _run([
                "package",
                "--staging-root", str(staging),
                "--run-root", str(run_root),
                "--output-dir", str(output_dir),
                "--run-manifest", str(run_root / "run-manifest.json"),
                "--profile", "shareable",
            ])
            self.assertEqual(r.returncode, 0, msg=r.stdout + r.stderr)
            pkg = list((output_dir / "0a1b2c3d4e5f" / "bundletestv0010" / "v0.1.0").glob("package.zip"))[0]
            # Re-zip with a tampered SKILL.md.
            with zipfile.ZipFile(pkg, "r") as zf:
                inner = zf.namelist()
                contents = {n: zf.read(n) for n in inner}
            contents["scene_design/SKILL.md"] = b"# scene_design\n\ntampered"
            with zipfile.ZipFile(pkg, "w", zipfile.ZIP_DEFLATED) as zf:
                for n in sorted(contents):
                    zf.writestr(n, contents[n])
            r = _run(["verify-package", "--package", str(pkg), "--run-root", str(run_root)])
            self.assertNotEqual(r.returncode, 0, msg=r.stdout + r.stderr)


class PurgeRunTests(unittest.TestCase):
    def test_purge_run_removes_private_dist(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "run"; run_root.mkdir()
            staging = run_root / "staging"; _make_staging(staging, final_state="limited")
            _make_run_manifest(run_root, auth="private_only")
            output_dir = run_root / "shareable"
            r = _run([
                "package",
                "--staging-root", str(staging),
                "--run-root", str(run_root),
                "--output-dir", str(output_dir),
                "--run-manifest", str(run_root / "run-manifest.json"),
                "--profile", "private-preview",
            ])
            self.assertEqual(r.returncode, 0, msg=r.stdout + r.stderr)
            self.assertTrue((run_root / "dist").exists())
            r = _run(["purge-run", "--run-root", str(run_root)])
            self.assertEqual(r.returncode, 0, msg=r.stdout + r.stderr)
            self.assertFalse((run_root / "dist").exists())


if __name__ == "__main__":
    unittest.main()
