"""Stage B Task 8b: init-run CLI."""

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


def _write_auth(tmp: Path, *, model_processing: str, derivative_use: str | None = None) -> Path:
    scope = {"model_processing": model_processing}
    if derivative_use is not None:
        scope["derivative_use"] = derivative_use
    auth = Path(tmp) / "auth.json"
    auth.write_text(json.dumps({
        "scope": scope,
        "evidence_basis": "user_declaration",
    }), encoding="utf-8")
    return auth


class InitRunTests(unittest.TestCase):
    def test_missing_model_processing_consent_blocks_run_root_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            auth = Path(tmp) / "auth.json"
            auth.write_text(json.dumps({"scope": {}}), encoding="utf-8")
            run_root = Path(tmp) / "run"
            result = _run([
                "init-run", "--run-root", str(run_root),
                "--run-id", "r1",
                "--authorization", str(auth),
                "--requested-model-id", "local",
                "--requested-purpose", "private_only",
            ])
            self.assertEqual(result.returncode, 1, msg=result.stdout + result.stderr)
            self.assertFalse(run_root.exists(), "run root must NOT be created on auth failure")

    def test_private_only_defaults_without_derivative_use(self):
        with tempfile.TemporaryDirectory() as tmp:
            auth = _write_auth(tmp, model_processing="local_only")
            source = Path(tmp) / "book.txt"
            source.write_text("synthetic source", encoding="utf-8")
            run_root = Path(tmp) / "run"
            prepared = _run(["prepare-source", "--source", str(source), "--run-root", str(run_root)])
            self.assertEqual(prepared.returncode, 0, msg=prepared.stdout + prepared.stderr)
            result = _run([
                "init-run", "--run-root", str(run_root),
                "--run-id", "r1",
                "--authorization", str(auth),
                "--requested-model-id", "local",
            ])
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            self.assertTrue(run_root.is_dir())
            manifest = json.loads((run_root / "run-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "incomplete")
            self.assertEqual(len(manifest["step_log"]), 1)
            source_manifest = json.loads((run_root / "source-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(source_manifest["authorization"]["scope"]["derivative_use"], "private_only")
            self.assertEqual(source_manifest["declared_derivative_use"], "private_only")

    def test_shareable_run_requires_explicit_derivative_use(self):
        with tempfile.TemporaryDirectory() as tmp:
            auth = _write_auth(tmp, model_processing="local_only")
            run_root = Path(tmp) / "run"
            result = _run([
                "init-run", "--run-root", str(run_root),
                "--run-id", "r1",
                "--authorization", str(auth),
                "--requested-model-id", "local",
                "--requested-purpose", "shareable_anonymous",
            ])
            self.assertEqual(result.returncode, 1, msg=result.stdout + result.stderr)
            self.assertIn("derivative_use", result.stdout + result.stderr)
            self.assertFalse(run_root.exists())

    def test_hosted_model_with_local_only_scope_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            auth = _write_auth(tmp, model_processing="local_only", derivative_use="private_only")
            run_root = Path(tmp) / "run"
            result = _run([
                "init-run", "--run-root", str(run_root),
                "--run-id", "r1",
                "--authorization", str(auth),
                "--requested-model-id", "gpt-4",
                "--requested-purpose", "private_only",
            ])
            self.assertEqual(result.returncode, 1)
            self.assertFalse(run_root.exists())

    def test_dry_run_does_not_create_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            auth = _write_auth(tmp, model_processing="local_only", derivative_use="private_only")
            run_root = Path(tmp) / "run"
            result = _run([
                "init-run", "--run-root", str(run_root),
                "--run-id", "r1",
                "--authorization", str(auth),
                "--requested-model-id", "local",
                "--requested-purpose", "private_only",
                "--dry-run",
            ])
            self.assertEqual(result.returncode, 0)
            self.assertFalse(run_root.exists())

    def test_existing_run_root_rejected(self):
        """init-run refuses to clobber an existing run root (Stage C will add
        --resume to opt into clobbering)."""
        with tempfile.TemporaryDirectory() as tmp:
            auth = _write_auth(tmp, model_processing="local_only", derivative_use="private_only")
            run_root = Path(tmp) / "run"
            run_root.mkdir()
            result = _run([
                "init-run", "--run-root", str(run_root),
                "--run-id", "r1",
                "--authorization", str(auth),
                "--requested-model-id", "local",
                "--requested-purpose", "private_only",
            ])
            self.assertEqual(result.returncode, 2, msg=result.stdout + result.stderr)
            # Existing run root must be untouched.
            self.assertTrue(run_root.is_dir())
            self.assertFalse((run_root / "run-manifest.json").exists())
