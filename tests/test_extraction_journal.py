"""Stage C Task 6 tests."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from extraction_journal import ExtractionJournal  # noqa: E402
from run_journal import HoldoutNotLockedError, StepRetryExhausted  # noqa: E402
from holdout_fixtures import persist_test_holdout  # noqa: E402


class ExtractionJournalBasicTests(unittest.TestCase):
    def test_dimension_start_requires_holdout_locked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "run"
            root.mkdir()
            journal = ExtractionJournal(root, "r1", source_fingerprint="0" * 64)
            with self.assertRaises(HoldoutNotLockedError):
                journal.record_dimension_start("narrative_voice")

    def test_dimension_start_then_checkpoint_then_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "run"
            root.mkdir()
            journal = ExtractionJournal(root, "r1", source_fingerprint="0" * 64)
            persist_test_holdout(root, "0" * 64)
            journal.record_dimension_start("narrative_voice")
            journal.record_dimension_checkpoint(
                "narrative_voice",
                candidates_path="private-ledger://candidates/narrative_voice.json",
                candidates_hash="a" * 64,
                status="succeeded",
                retry_count=0,
            )
            pending = journal.resume_pending_dimensions(
                all_dimensions=["narrative_voice", "sentence_rhythm"]
            )
            self.assertNotIn("narrative_voice", pending)
            self.assertIn("sentence_rhythm", pending)


class ExtractionJournalIdempotencyTests(unittest.TestCase):
    def test_double_checkpoint_does_not_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "run"
            root.mkdir()
            journal = ExtractionJournal(root, "r1", source_fingerprint="0" * 64)
            persist_test_holdout(root, "0" * 64)
            journal.record_dimension_start("narrative_voice")
            for _ in range(2):
                journal.record_dimension_checkpoint(
                    "narrative_voice",
                    candidates_path="private-ledger://candidates/narrative_voice.json",
                    candidates_hash="b" * 64,
                    status="succeeded",
                    retry_count=0,
                )
            manifest = (root / "run-manifest.json").read_text(encoding="utf-8")
            self.assertEqual(manifest.count('"step_id": "extract-narrative_voice"'), 1)


class ExtractionJournalRetryTests(unittest.TestCase):
    def test_retry_count_over_three_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "run"
            root.mkdir()
            journal = ExtractionJournal(root, "r1", source_fingerprint="0" * 64)
            persist_test_holdout(root, "0" * 64)
            with self.assertRaises(StepRetryExhausted):
                journal.record_dimension_checkpoint(
                    "narrative_voice",
                    candidates_path="x",
                    candidates_hash="a" * 64,
                    status="failed",
                    retry_count=4,
                )


class FailurePreservesSuccessTests(unittest.TestCase):
    def test_failure_does_not_drop_successful_dimension(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "run"
            root.mkdir()
            journal = ExtractionJournal(root, "r1", source_fingerprint="0" * 64)
            persist_test_holdout(root, "0" * 64)
            journal.record_dimension_start("narrative_voice")
            journal.record_dimension_checkpoint(
                "narrative_voice",
                candidates_path="p1",
                candidates_hash="a" * 64,
                status="succeeded",
                retry_count=0,
            )
            journal.record_dimension_failure(
                "sentence_rhythm",
                error_type="model_timeout",
                error_detail="simulated",
            )
            pending = journal.resume_pending_dimensions(
                all_dimensions=["narrative_voice", "sentence_rhythm", "scene_transition"]
            )
            self.assertNotIn("narrative_voice", pending)
            self.assertIn("sentence_rhythm", pending)
            self.assertIn("scene_transition", pending)


class ResumePendingDimensionsTests(unittest.TestCase):
    def test_returns_all_dimensions_when_no_checkpoints(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "run"
            root.mkdir()
            journal = ExtractionJournal(root, "r1", source_fingerprint="0" * 64)
            pending = journal.resume_pending_dimensions(
                all_dimensions=["narrative_voice", "sentence_rhythm"]
            )
            self.assertEqual(set(pending), {"narrative_voice", "sentence_rhythm"})


if __name__ == "__main__":
    unittest.main()
