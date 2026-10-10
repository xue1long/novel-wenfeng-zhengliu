"""Stage F Task 1 tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from trigger_metrics import (  # noqa: E402
    assert_trigger_thresholds,
    compute_trigger_metrics,
)


SIX_STAGES = (
    "write_entry", "scene_design", "character_beats",
    "prose_draft", "style_check", "revision",
)


def _suite_with_counts(
    *,
    pos_per_stage: int = 10,
    neg_per_stage: int = 10,
    bnd_per_stage: int = 5,
) -> dict:
    must_trigger = []
    must_not_trigger = []
    boundary = []
    for index, stage_id in enumerate(SIX_STAGES):
        for i in range(pos_per_stage):
            must_trigger.append({
                "case_id": f"{stage_id}-P-{i:02d}",
                "stage_id": stage_id,
                "input_excerpt": f"synthetic pos {stage_id} {i}",
            })
        for i in range(neg_per_stage):
            must_not_trigger.append({
                "case_id": f"{stage_id}-N-{i:02d}",
                "stage_id": stage_id,
                "input_excerpt": f"synthetic neg {stage_id} {i}",
            })
        for i in range(bnd_per_stage):
            boundary.append({
                "case_id": f"{stage_id}-B-{i:02d}",
                "stage_id": stage_id,
                "input_excerpt": f"synthetic boundary {stage_id} {i}",
            })
    return {
        "trigger_cases": {
            "must_trigger": must_trigger,
            "must_not_trigger": must_not_trigger,
            "boundary": boundary,
        }
    }


def _results_true_for_must_trigger(suite: dict) -> list[dict]:
    out: list[dict] = []
    for case in suite["trigger_cases"]["must_trigger"]:
        out.append({"case_id": case["case_id"], "stage_id": case["stage_id"], "triggered": True})
    for case in suite["trigger_cases"]["must_not_trigger"]:
        out.append({"case_id": case["case_id"], "stage_id": case["stage_id"], "triggered": False})
    for case in suite["trigger_cases"]["boundary"]:
        out.append({"case_id": case["case_id"], "stage_id": case["stage_id"], "triggered": False})
    return out


class HappyPathTests(unittest.TestCase):
    def test_all_stages_pass_with_perfect_results(self):
        suite = _suite_with_counts()
        results = _results_true_for_must_trigger(suite)
        metrics = compute_trigger_metrics(suite, results)
        summary = metrics["_summary"]
        self.assertEqual(summary["stages_with_full_coverage"], 6)
        self.assertEqual(summary["stages_meeting_precision_threshold"], 6)
        self.assertEqual(summary["stages_meeting_recall_threshold"], 6)
        for stage_id in SIX_STAGES:
            self.assertEqual(metrics[stage_id]["precision"], 1.0)
            self.assertEqual(metrics[stage_id]["recall"], 1.0)

    def test_assert_trigger_thresholds_passes_when_all_green(self):
        suite = _suite_with_counts()
        results = _results_true_for_must_trigger(suite)
        metrics = compute_trigger_metrics(suite, results)
        self.assertEqual(assert_trigger_thresholds(metrics), [])


class NegativeTests(unittest.TestCase):
    def test_precision_below_threshold_rejected(self):
        suite = _suite_with_counts()
        results = _results_true_for_must_trigger(suite)
        # Spoil precision for write_entry by making TWO must_not_trigger fire.
        for case_id in ("write_entry-N-00", "write_entry-N-01"):
            results = [r for r in results if not (r["case_id"] == case_id and r["triggered"] is False)]
            results.append({"case_id": case_id, "stage_id": "write_entry", "triggered": True})
        metrics = compute_trigger_metrics(suite, results)
        # precision = 10 / (10 + 2) = 0.833 < 0.90
        self.assertAlmostEqual(metrics["write_entry"]["precision"], 10 / 12)
        errors = assert_trigger_thresholds(metrics)
        self.assertTrue(any("precision" in e for e in errors), errors)

    def test_recall_below_threshold_rejected(self):
        suite = _suite_with_counts()
        results = _results_true_for_must_trigger(suite)
        # Spoil recall for scene_design by making TWO must_trigger miss.
        for case_id in ("scene_design-P-00", "scene_design-P-01"):
            results = [r for r in results if not (r["case_id"] == case_id and r["triggered"] is True)]
            results.append({"case_id": case_id, "stage_id": "scene_design", "triggered": False})
        metrics = compute_trigger_metrics(suite, results)
        # recall = 8 / (8 + 2) = 0.8 < 0.90
        self.assertAlmostEqual(metrics["scene_design"]["recall"], 8 / 10)
        errors = assert_trigger_thresholds(metrics)
        self.assertTrue(any("recall" in e for e in errors), errors)

    def test_insufficient_positive_cases_rejected(self):
        suite = _suite_with_counts(pos_per_stage=9)
        results = _results_true_for_must_trigger(suite)
        metrics = compute_trigger_metrics(suite, results)
        errors = assert_trigger_thresholds(metrics)
        self.assertTrue(any("positive" in e for e in errors), errors)

    def test_insufficient_negative_cases_rejected(self):
        suite = _suite_with_counts(neg_per_stage=9)
        results = _results_true_for_must_trigger(suite)
        metrics = compute_trigger_metrics(suite, results)
        errors = assert_trigger_thresholds(metrics)
        self.assertTrue(any("negative" in e for e in errors), errors)

    def test_boundary_cases_dont_affect_precision_recall(self):
        suite = _suite_with_counts()
        results = _results_true_for_must_trigger(suite)
        # Force every boundary case to "triggered" — they must NOT count.
        for case in suite["trigger_cases"]["boundary"]:
            results = [r for r in results if r["case_id"] != case["case_id"]]
            results.append({
                "case_id": case["case_id"], "stage_id": case["stage_id"], "triggered": True,
            })
        metrics = compute_trigger_metrics(suite, results)
        errors = assert_trigger_thresholds(metrics)
        self.assertEqual(errors, [], errors)
        # boundary_pass remains 0 even though all boundaries "triggered".
        for stage_id in SIX_STAGES:
            self.assertEqual(metrics[stage_id]["boundary_pass"], 0)


class DuplicateCaseTests(unittest.TestCase):
    def test_duplicate_case_id_rejected(self):
        suite = _suite_with_counts()
        # Force duplicate ids by mutating the suite.
        suite["trigger_cases"]["must_trigger"].append(
            suite["trigger_cases"]["must_trigger"][0]
        )
        with self.assertRaises(Exception):
            compute_trigger_metrics(suite, _results_true_for_must_trigger(suite))


class MissingFieldTests(unittest.TestCase):
    def test_result_missing_stage_id(self):
        suite = _suite_with_counts()
        with self.assertRaises(Exception):
            compute_trigger_metrics(suite, [{"case_id": "x", "triggered": True}])

    def test_result_missing_triggered_flag(self):
        suite = _suite_with_counts()
        with self.assertRaises(Exception):
            compute_trigger_metrics(suite, [
                {"case_id": "write_entry-P-00", "stage_id": "write_entry"},
            ])


if __name__ == "__main__":
    unittest.main()