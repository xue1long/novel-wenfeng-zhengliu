"""Stage F Task 4 tests."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from final_state_evaluator import (  # noqa: E402
    evaluate_evaluation_state,
    record_state_transition,
)


def _good_trigger() -> dict:
    return {
        "all_stages_meet_precision_and_recall_threshold": True,
        "stages_with_full_coverage": 6,
    }


def _good_output_eval() -> dict:
    return {"mechanical_pass_rate": 1.0, "passed": 6, "failed": 0}


def _good_end_to_end() -> dict:
    return {"verdict": "pass"}


class NegativeTests(unittest.TestCase):
    def test_missing_outputs_demote_to_incomplete(self):
        state = evaluate_evaluation_state(
            _good_trigger(), _good_output_eval(), _good_end_to_end(),
            has_unredacted_artifacts=False,
            missing_outputs=["style_check"],
        )
        self.assertEqual(state, "incomplete")

    def test_unredacted_artifacts_force_blocked(self):
        state = evaluate_evaluation_state(
            _good_trigger(), _good_output_eval(), _good_end_to_end(),
            has_unredacted_artifacts=True,
            missing_outputs=[],
        )
        self.assertEqual(state, "blocked")


class HappyPathTests(unittest.TestCase):
    def test_all_gates_pass_with_authorization_returns_ready(self):
        # Output_eval=1.0 + e2e='pass' + trigger full coverage + shareable
        # authorization -> spec §4.6 says ready is reachable.
        state = evaluate_evaluation_state(
            _good_trigger(), _good_output_eval(), _good_end_to_end(),
            has_unredacted_artifacts=False,
            missing_outputs=[],
        )
        self.assertEqual(state, "ready")

    def test_end_to_end_limited_yields_limited(self):
        # output eval failing OR end-to-end not 'pass' -> not "ready",
        # state machine reports ``limited`` per spec §4.8 (4).
        state = evaluate_evaluation_state(
            _good_trigger(), {"mechanical_pass_rate": 0.5}, {"verdict": "limited"},
            has_unredacted_artifacts=False,
            missing_outputs=[],
        )
        self.assertEqual(state, "limited")


class StateTransitionJournalTests(unittest.TestCase):
    def test_transition_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "run"
            run_root.mkdir()
            journal_path = run_root / "run-manifest.json"
            journal_path.write_text(json.dumps({
                "run_id": "r1",
                "step_log": [],
            }), encoding="utf-8")
            evidence = {"trigger_precision": 0.95}
            record_state_transition(journal_path, from_state="incomplete",
                                    to_state="limited", evidence=evidence)
            record_state_transition(journal_path, from_state="incomplete",
                                    to_state="limited", evidence=evidence)
            data = json.loads(journal_path.read_text(encoding="utf-8"))
            self.assertEqual(len(data["step_log"]), 1)

    def test_source_specific_evidence_keys_stripped(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "run"
            run_root.mkdir()
            journal_path = run_root / "run-manifest.json"
            journal_path.write_text(json.dumps({"run_id": "r1", "step_log": []}), encoding="utf-8")
            record_state_transition(
                journal_path,
                from_state="incomplete", to_state="limited",
                evidence={"book_name": "do-not-echo", "note": "audit"},
            )
            data = json.loads(journal_path.read_text(encoding="utf-8"))
            entry = data["step_log"][0]
            self.assertIn("audit", entry["error_type"])
            self.assertNotIn("do-not-echo", entry["error_type"])


if __name__ == "__main__":
    unittest.main()