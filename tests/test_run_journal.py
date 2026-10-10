"""Stage B Task 6: run journal + idempotent step records.

Spec anchor: §4.1 '步骤日志'.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from run_journal import (  # noqa: E402
    HoldoutNotLockedError,
    RunJournal,
    StepRetryExhausted,
    _read_manifest,
)
from holdout_fixtures import persist_test_holdout  # noqa: E402


class RunJournalBasicTests(unittest.TestCase):
    def test_first_step_record_appears_in_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "run"
            root.mkdir()
            journal = RunJournal(root, "run-001", source_fingerprint="fp")
            persist_test_holdout(root, "fp")
            journal.lock_holdout()
            journal.record_step(
                "extract-narrative-voice",
                input_hash="a" * 64,
                prompt_template_version="v1",
                model_id="local",
                output_path="private-ledger://out",
                output_hash="b" * 64,
                status="succeeded",
            )
            manifest = _read_manifest(root / "run-manifest.json")
            self.assertEqual(len(manifest["step_log"]), 1)
            self.assertEqual(manifest["step_log"][0]["step_id"], "extract-narrative-voice")

    def test_repeated_step_record_does_not_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "run"
            root.mkdir()
            journal = RunJournal(root, "run-001", source_fingerprint="fp")
            persist_test_holdout(root, "fp")
            journal.lock_holdout()
            for _ in range(3):
                journal.record_step(
                    "extract-narrative-voice",
                    input_hash="a" * 64,
                    prompt_template_version="v1",
                    model_id="local",
                    output_path="private-ledger://out",
                    output_hash="b" * 64,
                    status="succeeded",
                )
            manifest = _read_manifest(root / "run-manifest.json")
            self.assertEqual(len(manifest["step_log"]), 1)

    def test_retry_count_exhaustion_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "run"
            root.mkdir()
            journal = RunJournal(root, "run-001", source_fingerprint="fp")
            persist_test_holdout(root, "fp")
            journal.lock_holdout()
            with self.assertRaises(StepRetryExhausted):
                journal.record_step(
                    "extract-narrative-voice",
                    input_hash="a" * 64,
                    prompt_template_version="v1",
                    model_id="local",
                    output_path="private-ledger://out",
                    output_hash="b" * 64,
                    status="failed",
                    retry_count=4,
                )

    def test_set_status_rejects_unknown_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "run"
            root.mkdir()
            journal = RunJournal(root, "run-001", source_fingerprint="fp")
            with self.assertRaises(ValueError):
                journal.set_status("pending")


class RunJournalHoldoutGateTests(unittest.TestCase):
    def test_extract_step_before_lock_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "run"
            root.mkdir()
            journal = RunJournal(root, "run-001", source_fingerprint="fp")
            with self.assertRaises(HoldoutNotLockedError):
                journal.record_step(
                    "extract-narrative-voice",
                    input_hash="a" * 64,
                    prompt_template_version="v1",
                    model_id="local",
                    output_path="private-ledger://out",
                    output_hash="b" * 64,
                    status="succeeded",
                )

    def test_non_extract_step_can_record_without_holdout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "run"
            root.mkdir()
            journal = RunJournal(root, "run-001", source_fingerprint="fp")
            journal.record_step(
                "prepare-source",
                input_hash="a" * 64,
                prompt_template_version="v1",
                model_id="local",
                output_path="private-ledger://out",
                output_hash="b" * 64,
                status="succeeded",
            )
            manifest = _read_manifest(root / "run-manifest.json")
            self.assertEqual(len(manifest["step_log"]), 1)


class RunJournalPersistTests(unittest.TestCase):
    def test_step_survives_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "run"
            root.mkdir()
            journal = RunJournal(root, "run-001", source_fingerprint="fp")
            persist_test_holdout(root, "fp")
            journal.lock_holdout()
            journal.record_step(
                "extract-narrative-voice",
                input_hash="a" * 64,
                prompt_template_version="v1",
                model_id="local",
                output_path="private-ledger://out",
                output_hash="b" * 64,
                status="succeeded",
            )
            # Simulate process restart: re-instantiate.
            journal2 = RunJournal(root, "run-001", source_fingerprint="fp")
            journal2.record_step(
                "extract-narrative-voice",
                input_hash="a" * 64,
                prompt_template_version="v1",
                model_id="local",
                output_path="private-ledger://out2",
                output_hash="c" * 64,
                status="succeeded",
            )
            manifest = _read_manifest(root / "run-manifest.json")
            self.assertEqual(len(manifest["step_log"]), 1)
            self.assertEqual(manifest["step_log"][0]["output_hash"], "c" * 64)


if __name__ == "__main__":
    unittest.main()
