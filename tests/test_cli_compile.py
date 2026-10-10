"""Stage E Task 6 tests."""

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
        [sys.executable, "scripts/cli_compile.py", *args],
        cwd=str(cwd or PROJECT_ROOT),
        capture_output=True,
        timeout=30,
    )
    return subprocess.CompletedProcess(
        proc.args,
        proc.returncode,
        proc.stdout.decode("utf-8", errors="replace") if proc.stdout else "",
        proc.stderr.decode("utf-8", errors="replace") if proc.stderr else "",
    )


def _write_bundle(tmp: Path) -> Path:
    bundle = {
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
    bundle_path = tmp / "bundle.json"
    bundle_path.write_text(json.dumps(bundle), encoding="utf-8")
    return bundle_path


class CompileTests(unittest.TestCase):
    def test_compile_emits_staging(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            run_root = tmp_path / "run"
            run_root.mkdir()
            staging = run_root / "staging"
            bundle = _write_bundle(tmp_path)
            result = _run([
                "compile",
                "--staging-root", str(staging),
                "--run-root", str(run_root),
                "--bundle", str(bundle),
                "--lock-key", f"wenfeng.compile.{uuid.uuid4().hex}",
            ])
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            self.assertTrue((staging / "compile-manifest.json").is_file())

    def test_compile_refuses_existing_non_empty_staging(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            run_root = tmp_path / "run"
            run_root.mkdir()
            staging = run_root / "staging"
            staging.mkdir()
            (staging / "leftover.txt").write_text("hi", encoding="utf-8")
            bundle = _write_bundle(tmp_path)
            result = _run([
                "compile",
                "--staging-root", str(staging),
                "--run-root", str(run_root),
                "--bundle", str(bundle),
                "--lock-key", f"wenfeng.compile.{uuid.uuid4().hex}",
            ])
            self.assertEqual(result.returncode, 2)
            self.assertIn("refused", result.stdout + result.stderr)

    def test_compile_refuses_missing_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            run_root = tmp_path / "run"
            run_root.mkdir()
            staging = run_root / "staging"
            result = _run([
                "compile",
                "--staging-root", str(staging),
                "--run-root", str(run_root),
                "--bundle", str(tmp_path / "no-such.json"),
                "--lock-key", f"wenfeng.compile.{uuid.uuid4().hex}",
            ])
            self.assertEqual(result.returncode, 2)


class ValidateDistTests(unittest.TestCase):
    def test_validate_clean_staging_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            run_root = tmp_path / "run"
            run_root.mkdir()
            staging = run_root / "staging"
            bundle = _write_bundle(tmp_path)
            r = _run([
                "compile",
                "--staging-root", str(staging),
                "--run-root", str(run_root),
                "--bundle", str(bundle),
                "--lock-key", f"wenfeng.compile.{uuid.uuid4().hex}",
            ])
            self.assertEqual(r.returncode, 0, msg=r.stderr)
            result = _run(["validate-dist", "--staging-root", str(staging)])
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)

    def test_validate_detects_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            run_root = tmp_path / "run"
            run_root.mkdir()
            staging = run_root / "staging"
            bundle = _write_bundle(tmp_path)
            r = _run([
                "compile",
                "--staging-root", str(staging),
                "--run-root", str(run_root),
                "--bundle", str(bundle),
                "--lock-key", f"wenfeng.compile.{uuid.uuid4().hex}",
            ])
            self.assertEqual(r.returncode, 0, msg=r.stderr)
            tampered = staging / "scene_design" / "SKILL.md"
            tampered.write_text(
                tampered.read_text(encoding="utf-8") + "\n\naddendum",
                encoding="utf-8",
            )
            result = _run(["validate-dist", "--staging-root", str(staging)])
            self.assertNotEqual(result.returncode, 0)
            combined = (result.stdout or "") + (result.stderr or "")
            self.assertIn("hash mismatch", combined)

    def test_validate_missing_manifest_returns_exit_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            run_root = tmp_path / "run"
            run_root.mkdir()
            staging = run_root / "staging"
            result = _run(["validate-dist", "--staging-root", str(staging)])
            self.assertEqual(result.returncode, 1)
            combined = (result.stdout or "") + (result.stderr or "")
            self.assertIn("compile-manifest.json missing", combined)


if __name__ == "__main__":
    unittest.main()