"""Stage A Task 6: evaluation / content-scan / model-budget policy gate tests.

Spec anchors: §4.8 (eval gates), §4.4 (scan controls), §4.1 (budget profile).
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "vendor"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from check_policy_gate import (  # noqa: E402
    check_evaluation_policy,
    check_content_scan_policy,
    check_model_budget_policy,
    compute_readiness,
    gate_reason_categories,
)


def _load(name: str) -> dict:
    return json.loads((Path(__file__).resolve().parents[1] / "policies" / name).read_text(encoding="utf-8"))


class EvaluationPolicyTests(unittest.TestCase):
    def test_valid_evaluation_policy_passes(self):
        self.assertEqual(check_evaluation_policy(_load("evaluation-policy.json")), [])

    def test_must_trigger_below_10_rejected(self):
        data = _load("evaluation-policy.json")
        data["trigger_cases"]["must_trigger_count"] = 5
        errors = check_evaluation_policy(data)
        self.assertTrue(any("must_trigger" in e for e in errors), errors)

    def test_precision_threshold_below_0_90_rejected(self):
        data = _load("evaluation-policy.json")
        data["thresholds"]["precision_min"] = 0.85
        errors = check_evaluation_policy(data)
        self.assertTrue(any("precision_min" in e for e in errors), errors)


class ContentScanPolicyTests(unittest.TestCase):
    def test_valid_content_scan_policy_passes(self):
        self.assertEqual(check_content_scan_policy(_load("content-scan-policy.json")), [])

    def test_negatives_below_20_rejected(self):
        data = _load("content-scan-policy.json")
        data["controls"]["negative_misblock_max"] = 0
        data["controls"]["negatives_count"] = 19
        errors = check_content_scan_policy(data)
        self.assertTrue(any("negatives_count" in e or "negatives" in e for e in errors), errors)

    def test_overlimit_policy_must_be_known(self):
        data = _load("content-scan-policy.json")
        data["overlimit_policy"] = "best_effort"
        errors = check_content_scan_policy(data)
        self.assertTrue(any("overlimit_policy" in e for e in errors), errors)


class ModelBudgetPolicyTests(unittest.TestCase):
    def test_valid_model_budget_policy_passes(self):
        self.assertEqual(check_model_budget_policy(_load("model-budget-policy.json")), [])

    def test_missing_profile_field_blocks_readiness(self):
        data = _load("model-budget-policy.json")
        del data["profiles"]["synthetic-model"]["max_input_tokens_total"]
        errors = check_model_budget_policy(data)
        self.assertTrue(any("max_input_tokens_total" in e for e in errors), errors)
        # Readiness for this model must be False.
        ready, _ = compute_readiness(data, "synthetic-model")
        self.assertFalse(ready, "model without full numeric profile must not be ready")

    def test_unknown_model_id_rejected(self):
        data = _load("model-budget-policy.json")
        data["profiles"]["ghost-model"] = data["profiles"]["synthetic-model"]
        # Adding an unknown profile must not by itself raise an error.
        errors = check_model_budget_policy(data)
        # But requesting the unknown model id at compute time must fail.
        ready, reason = compute_readiness(data, "ghost-model")
        self.assertFalse(ready)
        self.assertTrue("ghost-model" in reason, reason)

    def test_overlimit_policy_out_of_enum_rejected(self):
        data = _load("model-budget-policy.json")
        data["profiles"]["synthetic-model"]["overlimit_policy"] = "abort_hard"
        errors = check_model_budget_policy(data)
        self.assertTrue(any("overlimit_policy" in e for e in errors), errors)


class GateReasonSummaryTests(unittest.TestCase):
    def test_reason_categories_match_known_blocks(self):
        expected = {
            "evaluation_policy_incomplete",
            "content_scan_policy_incomplete",
            "model_budget_profile_incomplete",
        }
        self.assertTrue(expected.issubset(set(gate_reason_categories())))