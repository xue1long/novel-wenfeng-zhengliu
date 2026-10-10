"""Stage F Task 6 tests."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _run(args: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        [sys.executable, "scripts/cli_evaluate.py", *args],
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


def _make_compile_manifest(staging: Path) -> None:
    staging.mkdir(parents=True, exist_ok=True)
    for stage_id in (
        "write_entry", "scene_design", "character_beats",
        "prose_draft", "style_check", "revision",
    ):
        (staging / stage_id).mkdir()
        (staging / stage_id / "SKILL.md").write_text(f"# {stage_id}\n", encoding="utf-8")
    (staging / "compile-manifest.json").write_text(json.dumps({
        "manifest_version": "0.1.0",
        "source_id": "0a1b2c3d4e5f",
        "bundle_id": "bundle-0a1b2c3d4e5f-v0_1_0",
        "skill_hashes": {},
    }), encoding="utf-8")


class RunEvaluationTests(unittest.TestCase):
    def test_happy_profile_writes_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "run"
            run_root.mkdir()
            staging = run_root / "staging"
            _make_compile_manifest(staging)
            r = _run([
                "run-evaluation",
                "--staging-root", str(staging),
                "--profile", "happy",
            ])
            self.assertIn(r.returncode, (0, 1), msg=r.stdout + r.stderr)
            self.assertTrue((staging / "eval-report.json").is_file())
            report = json.loads((staging / "eval-report.json").read_text(encoding="utf-8"))
            # Redaction marker is in notes.
            self.assertIn("redacted", report["summary"]["notes"])
            # No private fields leak.
            for leaked in ("unblinding_map", "pair_results", "rating_secrets"):
                self.assertNotIn(leaked, report)

    def test_mixed_profile_returns_limited_or_equivalent(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "run"
            run_root.mkdir()
            staging = run_root / "staging"
            _make_compile_manifest(staging)
            r = _run([
                "run-evaluation",
                "--staging-root", str(staging),
                "--profile", "mixed",
            ])
            self.assertIn(r.returncode, (0, 1), msg=r.stdout + r.stderr)
            report = json.loads((staging / "eval-report.json").read_text(encoding="utf-8"))
            self.assertIn(report["summary"]["final_state"], {"limited", "incomplete", "blocked", "ready"})

    def test_contains_private_profile_returns_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "run"
            run_root.mkdir()
            staging = run_root / "staging"
            _make_compile_manifest(staging)
            r = _run([
                "run-evaluation",
                "--staging-root", str(staging),
                "--profile", "contains_private",
            ])
            # The CLI marks has_unredacted_artifacts=True and the state
            # machine produces "blocked" -> exit 1.
            self.assertEqual(r.returncode, 1, msg=r.stdout + r.stderr)
            report = json.loads((staging / "eval-report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["summary"]["final_state"], "blocked")

    def test_missing_manifest_returns_exit_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "run"
            run_root.mkdir()
            staging = run_root / "staging"  # empty; no compile-manifest
            r = _run([
                "run-evaluation",
                "--staging-root", str(staging),
                "--profile", "happy",
            ])
            self.assertEqual(r.returncode, 1, msg=r.stdout + r.stderr)
            self.assertIn("compile-manifest.json missing", r.stdout + r.stderr)


class ValidateEvaluationTests(unittest.TestCase):
    def test_validate_clean_report_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "run"
            run_root.mkdir()
            staging = run_root / "staging"
            _make_compile_manifest(staging)
            r1 = _run([
                "run-evaluation",
                "--staging-root", str(staging),
                "--profile", "happy",
            ])
            self.assertIn(r1.returncode, (0, 1), msg=r1.stdout + r1.stderr)
            r2 = _run(["validate-evaluation", "--staging-root", str(staging)])
            self.assertEqual(r2.returncode, 0, msg=r2.stdout + r2.stderr)

    def test_validate_flags_private_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "run"
            run_root.mkdir()
            staging = run_root / "staging"
            _make_compile_manifest(staging)
            # First build a clean report.
            r1 = _run([
                "run-evaluation",
                "--staging-root", str(staging),
                "--profile", "happy",
            ])
            self.assertIn(r1.returncode, (0, 1), msg=r1.stdout + r1.stderr)
            # Tamper: inject a private field.
            report_path = staging / "eval-report.json"
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["unblinding_map"] = {"EP-00": "private"}
            report_path.write_text(json.dumps(report), encoding="utf-8")
            r2 = _run(["validate-evaluation", "--staging-root", str(staging)])
            self.assertEqual(r2.returncode, 1, msg=r2.stdout + r2.stderr)
            self.assertIn("private fields", r2.stdout + r2.stderr)

    def test_validate_missing_report_returns_exit_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "run"
            run_root.mkdir()
            staging = run_root / "staging"
            r = _run(["validate-evaluation", "--staging-root", str(staging)])
            self.assertEqual(r.returncode, 1, msg=r.stdout + r.stderr)
            self.assertIn("eval-report.json missing", r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
