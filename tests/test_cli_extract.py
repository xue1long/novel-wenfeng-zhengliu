"""Stage C Task 7a: extract-dimensions CLI."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "tests"))
from holdout_fixtures import prepare_locked_run  # noqa: E402


def _run(args: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "scripts/cli_extract.py", *args],
        cwd=str(cwd or PROJECT_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )


def _bootstrap(tmp: Path) -> tuple[Path, Path]:
    text = "# 第一章\n句子一。句子二。\n\n# 第二章\n句子三。句子四。\n\n# 第三章\n句子五。句子六。\n"
    run_root = prepare_locked_run(tmp, text)
    return run_root, run_root


class ExtractDimensionsTests(unittest.TestCase):
    def test_holdout_unlocked_blocks_extraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            # Bootstrap but DON'T lock holdout.
            src = tmp_path / "novel.txt"
            src.write_text("# 第一章\n句子。\n", encoding="utf-8")
            auth = tmp_path / "auth.json"
            auth.write_text(json.dumps({
                "scope": {"model_processing": "local_only", "derivative_use": "private_only"},
                "evidence_basis": "user_declaration",
            }), encoding="utf-8")
            run_root = tmp_path / "run"
            subprocess.run(
                [sys.executable, "scripts/cli.py", "prepare-source",
                 "--source", str(src), "--run-root", str(run_root)],
                cwd=str(PROJECT_ROOT), capture_output=True, text=True, timeout=30,
            )
            subprocess.run(
                [sys.executable, "scripts/cli.py", "init-run",
                 "--run-root", str(run_root), "--run-id", "r1",
                 "--authorization", str(auth),
                 "--requested-model-id", "local",
                 "--requested-purpose", "private_only"],
                cwd=str(PROJECT_ROOT), capture_output=True, text=True, timeout=30,
            )
            result = _run([
                "extract-dimensions",
                "--run-root", str(run_root),
                "--run-id", "r1",
                "--stub",
            ])
            # The CLI exits 1 with a clear holdout message.
            self.assertEqual(result.returncode, 1, msg=result.stdout + result.stderr)
            self.assertIn("holdout", (result.stdout + result.stderr).lower())

    def test_default_stub_profile_is_mixed(self):
        with tempfile.TemporaryDirectory() as tmp:
            init_root, _ = _bootstrap(Path(tmp))
            result = _run([
                "extract-dimensions",
                "--run-root", str(init_root),
                "--run-id", "r1",
                "--stub",
            ])
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            summary = json.loads((init_root / "extract-summary.json").read_text(encoding="utf-8"))
            self.assertEqual(len(summary), 5)
            for entry in summary:
                self.assertEqual(entry["status"], "succeeded")
                self.assertGreater(entry["candidates"], 0)

    def test_all_supported_profile_with_enough_chapters(self):
        with tempfile.TemporaryDirectory() as tmp:
            init_root, _ = _bootstrap(Path(tmp))
            result = _run([
                "extract-dimensions",
                "--run-root", str(init_root),
                "--run-id", "r1",
                "--stub", "--stub-profile", "all_supported",
            ])
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            # All five dimensions produced candidates with supported status.
            for path in (init_root / "candidates").glob("*.json"):
                payload = json.loads(path.read_text(encoding="utf-8"))
                for cand in payload["candidates"]:
                    self.assertEqual(cand["review_status"], "supported")

    def test_retry_over_three_marks_dimension_failed(self):
        # The CLI surfaces retry exhaustion via the journal's exception handler.
        # We force exhaustion by writing 4 retries directly into the journal.
        with tempfile.TemporaryDirectory() as tmp:
            init_root, _ = _bootstrap(Path(tmp))
            from extraction_journal import ExtractionJournal, StepRetryExhausted
            ej = ExtractionJournal(init_root, "r1", source_fingerprint="0" * 64)
            with self.assertRaises(StepRetryExhausted):
                ej.record_dimension_checkpoint(
                    "narrative_voice",
                    candidates_path="x",
                    candidates_hash="a" * 64,
                    status="failed",
                    retry_count=4,
                )


if __name__ == "__main__":
    unittest.main()
