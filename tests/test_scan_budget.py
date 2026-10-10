"""Stage B Task 7: scan budget estimator.

Spec anchor: §6 阶段 B 验收'预算估算可解释,窗口清单完整且可续跑'.

Each numeric field in the resulting plan MUST be derivable from
``(chunks, content-scan-policy)`` — no magic constants other than the ones
pinned at the top of ``scripts/scan_budget.py``.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from chunker import chunk_text  # noqa: E402
from scan_budget import (  # noqa: E402
    ScanBudgetIncompleteError,
    estimate_scan_budget,
    resume_windows,
    TOKEN_CHARS_PER_TOKEN,
    BATCH_WINDOW_CODEPOINTS,
)


def _policy() -> dict:
    return {
        "policy_version": "0.1.0",
        "shingle_size": 12,
        "min_continuous_match": "TBD_locked_by_phase_a_calibration",
        "overlimit_policy": "degrade_to_limited",
        "controls": {
            "positives_count": 20,
            "negatives_count": 20,
            "negative_misblock_max": 1,
            "positive_miss_block_max": 0,
        },
    }


def _chunks():
    text = "第一章\n" + ("这是用于测试的一段正文。" * 30)
    return chunk_text(text, chunker_version="v1")


class ScanBudgetHappyPathTests(unittest.TestCase):
    def test_estimate_returns_required_fields(self):
        plan = estimate_scan_budget(_chunks(), _policy(), fingerprint="fp", chunker_version="v1")
        self.assertEqual(plan["policy_version"], "0.1.0")
        self.assertEqual(plan["fingerprint"], "fp")
        self.assertEqual(plan["chunker_version"], "v1")
        self.assertIn("windows", plan)
        self.assertIn("aggregate", plan)
        self.assertGreater(len(plan["windows"]), 0)

    def test_each_window_has_required_fields(self):
        plan = estimate_scan_budget(_chunks(), _policy(), fingerprint="fp", chunker_version="v1")
        window = plan["windows"][0]
        for field in ("window_id", "chunk_id", "estimated_codepoints", "estimated_tokens"):
            self.assertIn(field, window, f"window missing {field}")

    def test_aggregate_explains_every_number(self):
        chunks = _chunks()
        plan = estimate_scan_budget(chunks, _policy(), fingerprint="fp", chunker_version="v1")
        agg = plan["aggregate"]
        # Total codepoints comes from the chunks directly (sum of char_offset spans).
        total_codepoints = sum((c.char_offset[1] - c.char_offset[0]) for c in chunks)
        self.assertEqual(agg["total_codepoints"], total_codepoints)
        # Estimated requests = ceil(total_codepoints / batch window).
        expected_requests = -(-total_codepoints // BATCH_WINDOW_CODEPOINTS)
        self.assertEqual(agg["estimated_requests"], expected_requests)
        # Estimated tokens = codepoints / 4.
        self.assertEqual(agg["estimated_tokens_total"], total_codepoints // TOKEN_CHARS_PER_TOKEN)
        self.assertEqual(agg["estimated_tokens_per_batch"], BATCH_WINDOW_CODEPOINTS // TOKEN_CHARS_PER_TOKEN)


class ScanBudgetResumabilityTests(unittest.TestCase):
    def test_resume_returns_only_incomplete_windows(self):
        plan = estimate_scan_budget(_chunks(), _policy(), fingerprint="fp", chunker_version="v1")
        all_ids = [w["window_id"] for w in plan["windows"]]
        first_half = all_ids[: max(1, len(all_ids) // 2)]
        resumed = resume_windows(plan, completed_ids=set(first_half))
        resumed_ids = [w["window_id"] for w in resumed]
        self.assertEqual(set(resumed_ids), set(all_ids) - set(first_half))

    def test_resume_with_all_complete_returns_empty(self):
        plan = estimate_scan_budget(_chunks(), _policy(), fingerprint="fp", chunker_version="v1")
        all_ids = {w["window_id"] for w in plan["windows"]}
        resumed = resume_windows(plan, completed_ids=all_ids)
        self.assertEqual(resumed, [])

    def test_resume_with_no_completed_returns_all_windows(self):
        plan = estimate_scan_budget(_chunks(), _policy(), fingerprint="fp", chunker_version="v1")
        resumed = resume_windows(plan, completed_ids=set())
        self.assertEqual(len(resumed), len(plan["windows"]))


class ScanBudgetMissingFieldsTests(unittest.TestCase):
    def test_missing_policy_version_raises(self):
        policy = _policy()
        del policy["policy_version"]
        with self.assertRaises(ScanBudgetIncompleteError) as cm:
            estimate_scan_budget(_chunks(), policy, fingerprint="fp", chunker_version="v1")
        self.assertIn("policy_version", str(cm.exception))

    def test_chunk_missing_chunk_id_raises(self):
        bad_chunks = [{"chunk_id": "", "char_offset": [0, 100], "window_hash": "x"}]
        with self.assertRaises(ScanBudgetIncompleteError):
            estimate_scan_budget(bad_chunks, _policy(), fingerprint="fp", chunker_version="v1")


class ScanBudgetMonotonicityTests(unittest.TestCase):
    def test_more_codepoints_yields_more_requests(self):
        small = estimate_scan_budget(_chunks(), _policy(), fingerprint="fp", chunker_version="v1")
        text_b = "第二章\n" + ("另一段非常长的正文用于让总码点超过 BATCH_WINDOW_CODEPOINTS。" * 10000)
        from chunker import chunk_text as _chunk_text
        big_chunks = _chunk_text(text_b, chunker_version="v1")
        big = estimate_scan_budget(big_chunks, _policy(), fingerprint="fp", chunker_version="v1")
        self.assertGreater(
            big["aggregate"]["total_codepoints"],
            BATCH_WINDOW_CODEPOINTS,
        )
        self.assertGreater(
            big["aggregate"]["estimated_requests"],
            small["aggregate"]["estimated_requests"],
        )


if __name__ == "__main__":
    unittest.main()