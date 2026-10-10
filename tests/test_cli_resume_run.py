"""Stage B Task 8c: resume-run CLI."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _run(args: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "scripts/cli.py", *args],
        cwd=str(cwd or PROJECT_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )


def _bootstrap_run(tmp: Path) -> Path:
    auth = Path(tmp) / "auth.json"
    auth.write_text(json.dumps({
        "scope": {"model_processing": "local_only", "derivative_use": "private_only"},
        "evidence_basis": "user_declaration",
    }), encoding="utf-8")
    run_root = Path(tmp) / "run"
    _run([
        "init-run", "--run-root", str(run_root),
        "--run-id", "r1",
        "--authorization", str(auth),
        "--requested-model-id", "local",
        "--requested-purpose", "private_only",
    ])
    return run_root


class ResumeRunTests(unittest.TestCase):
    def test_idempotent_step_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root = _bootstrap_run(Path(tmp))
            for _ in range(2):
                result = _run([
                    "resume-run", "--run-root", str(run_root),
                    "--run-id", "r1", "--step-id", "prepare-source",
                    "--retry-count", "0",
                ])
                self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            manifest = json.loads((run_root / "run-manifest.json").read_text(encoding="utf-8"))
            steps = [s for s in manifest["step_log"] if s["step_id"] == "prepare-source"]
            self.assertEqual(len(steps), 1)

    def test_retry_count_over_three_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root = _bootstrap_run(Path(tmp))
            result = _run([
                "resume-run", "--run-root", str(run_root),
                "--run-id", "r1", "--step-id", "prepare-source",
                "--retry-count", "4",
            ])
            self.assertEqual(result.returncode, 1)

    def test_unknown_step_id_is_recorded(self):
        # resume-run accepts arbitrary step_id by design; what matters is that
        # retry_count > 3 is rejected and idempotency holds.
        with tempfile.TemporaryDirectory() as tmp:
            run_root = _bootstrap_run(Path(tmp))
            result = _run([
                "resume-run", "--run-root", str(run_root),
                "--run-id", "r1", "--step-id", "future-stage-D-step",
                "--retry-count", "0",
            ])
            self.assertEqual(result.returncode, 0)
            manifest = json.loads((run_root / "run-manifest.json").read_text(encoding="utf-8"))
            ids = [s["step_id"] for s in manifest["step_log"]]
            self.assertIn("future-stage-D-step", ids)

    def test_missing_run_root_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "no-such-run"
            result = _run([
                "resume-run", "--run-root", str(run_root),
                "--run-id", "r1", "--step-id", "prepare-source",
                "--retry-count", "0",
            ])
            self.assertEqual(result.returncode, 2, msg=result.stdout + result.stderr)