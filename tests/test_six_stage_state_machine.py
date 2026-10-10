"""Stage D Task 3 tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from six_stage_state_machine import (  # noqa: E402
    TERMINAL_STAGE,
    IllegalTransitionError,
    NonMonotonicRetry,
    RetryExhausted,
    partial_replay_targets,
    record_illegal_transition,
    stage_index,
    validate_retry_count,
    validate_transition,
)


class LegalTransitionTests(unittest.TestCase):
    def test_full_chain_passes(self):
        chain = [
            ("write_entry", "scene_design"),
            ("scene_design", "character_beats"),
            ("character_beats", "prose_draft"),
            ("prose_draft", "style_check"),
            ("style_check", "revision"),
            ("revision", TERMINAL_STAGE),
        ]
        for current, nxt in chain:
            validate_transition(current, nxt)

    def test_legal_return_to_passes(self):
        # From prose_draft back to scene_design is legal as a return.
        validate_transition(
            "prose_draft", "style_check", return_to="scene_design"
        )


class IllegalTransitionTests(unittest.TestCase):
    def test_cross_stage_skip_rejected(self):
        with self.assertRaises(IllegalTransitionError):
            validate_transition("write_entry", "prose_draft")

    def test_terminal_continues_forward_rejected(self):
        with self.assertRaises(IllegalTransitionError):
            validate_transition(TERMINAL_STAGE, "revision")

    def test_return_to_points_to_current_stage_rejected(self):
        with self.assertRaises(IllegalTransitionError):
            validate_transition(
                "character_beats", "prose_draft", return_to="character_beats"
            )

    def test_return_to_points_after_current_rejected(self):
        with self.assertRaises(IllegalTransitionError):
            validate_transition(
                "character_beats", "prose_draft", return_to="style_check"
            )

    def test_return_to_terminal_rejected(self):
        with self.assertRaises(IllegalTransitionError):
            validate_transition(
                "prose_draft", "style_check", return_to=TERMINAL_STAGE
            )


class RetryCountTests(unittest.TestCase):
    def test_retry_count_4_raises_retry_exhausted(self):
        with self.assertRaises(RetryExhausted):
            validate_retry_count(4)

    def test_retry_count_3_passes(self):
        validate_retry_count(3)

    def test_retry_count_non_monotonic_rejected(self):
        with self.assertRaises(NonMonotonicRetry):
            validate_retry_count(1, previous=2)


class PartialReplayTargetsTests(unittest.TestCase):
    def test_return_to_character_beats_with_current_prose_draft(self):
        targets = partial_replay_targets("character_beats", "prose_draft")
        self.assertEqual(targets, ["character_beats", "prose_draft"])

    def test_return_to_scene_design_with_current_style_check(self):
        targets = partial_replay_targets("scene_design", "style_check")
        self.assertEqual(targets, ["scene_design", "character_beats", "prose_draft", "style_check"])

    def test_return_to_terminal_rejected(self):
        with self.assertRaises(IllegalTransitionError):
            partial_replay_targets(TERMINAL_STAGE, "revision")


class StageIndexTests(unittest.TestCase):
    def test_terminal_stage_index_is_len(self):
        self.assertEqual(stage_index(TERMINAL_STAGE), 6)

    def test_unknown_stage_raises(self):
        from six_stage_state_machine import UnknownStageError
        with self.assertRaises(UnknownStageError):
            stage_index("epilogue_polish")


class IllegalTransitionReportTests(unittest.TestCase):
    def test_report_matches_stage_context_shape(self):
        report = record_illegal_transition(
            trace_id="t1", from_stage="write_entry", to_stage="prose_draft"
        )
        d = report.as_dict()
        self.assertEqual(d["error_type"], "illegal_transition")
        self.assertEqual(d["conflicting_stage"], "write_entry")
        self.assertIn("illegal handoff", d["note"])


if __name__ == "__main__":
    unittest.main()