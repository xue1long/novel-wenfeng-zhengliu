"""Stage A Task 8: exercise the five synthetic scenarios end-to-end."""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "vendor"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from check_policy_gate import (  # noqa: E402
    check_evaluation_policy,
    check_model_budget_policy,
    compute_readiness,
)
from invalidation_rules import compute_invalidation  # noqa: E402
from state_machine import compute_final_state  # noqa: E402


def _scenario_normal() -> dict[str, Any]:
    return {
        "name": "normal",
        "policy_patch": {},
        "expected_check_evaluation_policy": [],
        "expected_check_model_budget_policy": [],
        "expected_compute_final_state": "ready",
        "expected_compute_readiness": True,
        "expected_invalidation_release": False,
    }


def _scenario_failure() -> dict[str, Any]:
    return {
        "name": "failure",
        "policy_patch": {"trigger_cases": {"must_trigger_count": 5}},
        "expected_check_evaluation_policy_fragment": "must_trigger",
        "expected_compute_final_state": "limited",
        "expected_compute_readiness": True,
        "expected_invalidation_release": False,
    }


def _scenario_overbudget() -> dict[str, Any]:
    return {
        "name": "overbudget",
        "policy_patch": {"profiles": {"synthetic-model": {"max_input_tokens_total": 0}}},
        "expected_check_model_budget_policy_fragment": "max_input_tokens_total",
        "expected_compute_readiness": False,
        "expected_invalidation_release": False,
    }


def _scenario_resume() -> dict[str, Any]:
    return {
        "name": "resume",
        "policy_patch": {},
        "scan_windows": {
            "w-1": {"input_hash": "x", "prompt_hash": "p", "model_hash": "m", "completed": True},
            "w-2": {"input_hash": "y", "prompt_hash": "p", "model_hash": "m", "completed": False},
        },
        "increased_scan_budget": True,
        "expected_completed_preserved": ["w-1"],
        "expected_needing_resume": ["w-2"],
        "expected_invalidation_release": False,
    }


def _scenario_unauthorized() -> dict[str, Any]:
    return {
        "name": "unauthorized",
        "policy_patch": {},
        "expected_compute_final_state_with_purpose_private_only": "limited",
        "expected_invalidation_release": False,
    }


SCENARIOS = [
    _scenario_normal(),
    _scenario_failure(),
    _scenario_overbudget(),
    _scenario_resume(),
    _scenario_unauthorized(),
]


POLICY_FILES = {
    "evaluation-policy.json": PROJECT_ROOT / "policies" / "evaluation-policy.json",
    "model-budget-policy.json": PROJECT_ROOT / "policies" / "model-budget-policy.json",
}


def _patched(name: str, patch: dict) -> dict:
    base = json.loads(POLICY_FILES[name].read_text(encoding="utf-8"))
    if not patch:
        return base
    base_copy = copy.deepcopy(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(base_copy.get(key), dict):
            base_copy[key].update(value)
        else:
            base_copy[key] = value
    return base_copy


class StageAScenarioTests(unittest.TestCase):
    def test_normal_scenario_is_clean(self):
        scenario = SCENARIOS[0]
        self.assertEqual(scenario["name"], "normal")
        eval_policy = _patched("evaluation-policy.json", scenario["policy_patch"])
        budget_policy = _patched("model-budget-policy.json", scenario["policy_patch"])
        self.assertEqual(check_evaluation_policy(eval_policy), [])
        self.assertEqual(check_model_budget_policy(budget_policy), [])
        state = compute_final_state(
            gates_passed=["bundle_valid", "extraction_valid", "eval_passed", "scan_complete"],
            authorization_purpose="shareable_anonymous",
        )
        self.assertEqual(state, scenario["expected_compute_final_state"])
        ready, _ = compute_readiness(budget_policy, "synthetic-model")
        self.assertTrue(ready)

    def test_failure_scenario_reports_evaluation_policy_error(self):
        scenario = SCENARIOS[1]
        eval_policy = _patched("evaluation-policy.json", scenario["policy_patch"])
        errors = check_evaluation_policy(eval_policy)
        self.assertTrue(
            any(scenario["expected_check_evaluation_policy_fragment"] in e for e in errors),
            errors,
        )

    def test_overbudget_scenario_blocks_readiness(self):
        scenario = SCENARIOS[2]
        budget_policy = _patched("model-budget-policy.json", scenario["policy_patch"])
        errors = check_model_budget_policy(budget_policy)
        self.assertTrue(
            any(scenario["expected_check_model_budget_policy_fragment"] in e for e in errors),
            errors,
        )
        ready, _ = compute_readiness(budget_policy, "synthetic-model")
        self.assertFalse(ready)

    def test_resume_scenario_preserves_completed_windows(self):
        scenario = SCENARIOS[3]
        result = compute_invalidation(
            existing_hashes={"scan_windows": scenario["scan_windows"]},
            changed_classes=[],
            increased_scan_budget=scenario["increased_scan_budget"],
        )
        self.assertEqual(result["completed_windows_preserved"], scenario["expected_completed_preserved"])
        self.assertEqual(result["windows_needing_resume"], scenario["expected_needing_resume"])
        self.assertNotIn("release", result["invalidated"])

    def test_unauthorized_scenario_demotes_to_limited(self):
        scenario = SCENARIOS[4]
        state = compute_final_state(
            gates_passed=["bundle_valid", "extraction_valid", "eval_passed", "scan_complete"],
            authorization_purpose="private_only",
        )
        self.assertEqual(state, scenario["expected_compute_final_state_with_purpose_private_only"])


if __name__ == "__main__":
    unittest.main()