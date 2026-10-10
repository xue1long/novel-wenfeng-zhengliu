"""Stage A Task 7: invalidation rule tests.

Spec §4.6 lists five invalidation triggers and explicitly carves out the case
where increasing only the scan budget must NOT invalidate already-completed
windows. These tests pin those rules.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from invalidation_rules import (  # noqa: E402
    InvalidationClass,
    compute_invalidation,
)


class InvalidationTriggerTests(unittest.TestCase):
    def test_source_or_parser_change_invalidates_extraction(self):
        result = compute_invalidation(
            existing_hashes={},
            changed_classes=[
                InvalidationClass.SOURCE_FINGERPRINT,
                InvalidationClass.NORMALIZER_VERSION,
                InvalidationClass.CHUNKER_VERSION,
            ],
            increased_scan_budget=False,
        )
        self.assertIn("sampling", result["invalidated"])
        self.assertIn("holdout", result["invalidated"])
        self.assertIn("extraction", result["invalidated"])
        self.assertIn("bundle", result["invalidated"])
        self.assertIn("compilation", result["invalidated"])
        self.assertIn("evaluation", result["invalidated"])
        self.assertIn("release", result["invalidated"])

    def test_prompt_or_review_model_change_invalidates_extraction_only(self):
        result = compute_invalidation(
            existing_hashes={},
            changed_classes=[
                InvalidationClass.EXTRACTION_PROMPT_VERSION,
                InvalidationClass.REVIEW_MODEL_ID,
                InvalidationClass.CANDIDATE_SCHEMA_VERSION,
            ],
            increased_scan_budget=False,
        )
        self.assertIn("extraction", result["invalidated"])
        self.assertNotIn("sampling", result["invalidated"])
        self.assertIn("bundle", result["invalidated"])
        self.assertIn("compilation", result["invalidated"])
        self.assertIn("evaluation", result["invalidated"])
        self.assertIn("release", result["invalidated"])

    def test_bundle_or_compiler_change_invalidates_from_compilation(self):
        result = compute_invalidation(
            existing_hashes={},
            changed_classes=[
                InvalidationClass.BUNDLE_VERSION,
                InvalidationClass.TEMPLATE_VERSION,
                InvalidationClass.COMPILER_VERSION,
            ],
            increased_scan_budget=False,
        )
        self.assertNotIn("extraction", result["invalidated"])
        self.assertIn("compilation", result["invalidated"])
        self.assertIn("evaluation", result["invalidated"])
        self.assertIn("release", result["invalidated"])

    def test_scoring_model_change_invalidates_eval_and_release(self):
        result = compute_invalidation(
            existing_hashes={},
            changed_classes=[
                InvalidationClass.SCORING_MODEL_ID,
                InvalidationClass.SCORING_RUBRIC_VERSION,
            ],
            increased_scan_budget=False,
        )
        self.assertNotIn("compilation", result["invalidated"])
        self.assertIn("evaluation", result["invalidated"])
        self.assertIn("release", result["invalidated"])

    def test_scan_model_or_policy_change_invalidates_scan_and_release(self):
        result = compute_invalidation(
            existing_hashes={},
            changed_classes=[
                InvalidationClass.SCAN_MODEL_ID,
                InvalidationClass.SCAN_POLICY_VERSION,
            ],
            increased_scan_budget=False,
        )
        self.assertIn("scan", result["invalidated"])
        self.assertIn("release", result["invalidated"])

    def test_increasing_only_scan_budget_does_not_invalidate_completed(self):
        """Spec §4.6 explicitly: '单纯增加扫描预算不使已完成且输入/提示/模型哈希一致
        的窗口失效，只续跑未完成窗口。'"""
        existing = {
            "scan_windows": {
                "w-1": {"input_hash": "x", "prompt_hash": "p", "model_hash": "m", "completed": True},
                "w-2": {"input_hash": "y", "prompt_hash": "p", "model_hash": "m", "completed": False},
            }
        }
        result = compute_invalidation(
            existing_hashes=existing,
            changed_classes=[],
            increased_scan_budget=True,
        )
        # Completed windows survive; incomplete ones are listed as needing-resume.
        self.assertEqual(result["completed_windows_preserved"], ["w-1"])
        self.assertEqual(result["windows_needing_resume"], ["w-2"])
        # And release is not invalidated by a budget-only change.
        self.assertNotIn("release", result["invalidated"])


if __name__ == "__main__":
    unittest.main()