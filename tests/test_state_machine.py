"""Stage A Task 7: run state machine + invalidation rules tests.

Spec anchor: §4.6.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from state_machine import (  # noqa: E402
    STATES,
    BLOCKED_TRANSITIONS,
    compute_final_state,
    requires_authorization_for_share,
    transition,
)


class StateMachineTests(unittest.TestCase):
    def test_known_states(self):
        self.assertEqual(set(STATES), {"incomplete", "blocked", "limited", "ready"})

    def test_continue_incomplete(self):
        self.assertEqual(transition("incomplete", "step_resumed"), "incomplete")

    def test_authorization_missing_moves_to_blocked(self):
        self.assertEqual(transition("incomplete", "authorization_missing"), "blocked")

    def test_blocked_to_ready_is_hard_blocked(self):
        self.assertEqual(transition("blocked", "all_gates_passed"), "blocked")

    def test_limited_to_ready_requires_gates(self):
        self.assertEqual(transition("limited", "all_gates_passed"), "ready")
        self.assertEqual(transition("limited", "scan_budget_exhausted"), "limited")

    def test_incomplete_cannot_jump_to_ready(self):
        self.assertEqual(transition("incomplete", "all_gates_passed"), "incomplete")

    def test_unknown_event_does_not_progress(self):
        self.assertEqual(transition("incomplete", "magic"), "incomplete")

    def test_authorization_for_share(self):
        self.assertTrue(requires_authorization_for_share("ready", "shareable_anonymous"))
        self.assertTrue(requires_authorization_for_share("ready", "shareable_with_attribution"))
        self.assertFalse(requires_authorization_for_share("ready", "private_only"))
        self.assertFalse(requires_authorization_for_share("limited", "shareable_anonymous"))

    def test_compute_final_state_aggregates(self):
        result = compute_final_state(
            gates_passed=["bundle_valid", "extraction_valid", "eval_passed", "scan_complete"],
            authorization_purpose="shareable_anonymous",
        )
        self.assertEqual(result, "ready")

    def test_compute_final_state_scan_inconclusive_demotes(self):
        result = compute_final_state(
            gates_passed=["bundle_valid", "extraction_valid", "eval_passed"],
            authorization_purpose="shareable_anonymous",
        )
        self.assertEqual(result, "limited")

    def test_compute_final_state_blocked(self):
        result = compute_final_state(
            gates_passed=["bundle_valid", "extraction_valid", "eval_passed", "scan_complete", "exact_copy_detected"],
            authorization_purpose="shareable_anonymous",
        )
        self.assertEqual(result, "blocked")


class InvalidatedTransitionHelperTests(unittest.TestCase):
    def test_blocked_transitions_table_is_complete(self):
        for state in STATES:
            self.assertIn(state, BLOCKED_TRANSITIONS, state)


if __name__ == "__main__":
    unittest.main()