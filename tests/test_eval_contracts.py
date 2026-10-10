"""Stage A Task 4: eval-suite / eval-report / eval-cases contract tests.

Spec anchor: §4.8 (evaluation system).
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "vendor"))

from json_schema_validate import validate  # noqa: E402

SCHEMAS = PROJECT_ROOT / "schemas"
EXAMPLES = SCHEMAS / "examples"


def _schema(name: str) -> dict:
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


def _example(name: str) -> dict:
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


SUITE_SCHEMA = _schema("eval-suite.schema.json")
REPORT_SCHEMA = _schema("eval-report.schema.json")
CASES_SCHEMA = _schema("eval-cases.schema.json")


class HappyPathTests(unittest.TestCase):
    def test_suite_example_is_valid(self):
        self.assertEqual(validate(_example("eval-suite.example.json"), SUITE_SCHEMA), [])

    def test_cases_example_is_valid(self):
        self.assertEqual(validate(_example("eval-cases.example.json"), CASES_SCHEMA), [])

    def test_report_example_is_valid(self):
        self.assertEqual(validate(_example("eval-report.example.json"), REPORT_SCHEMA), [])


class SuiteNegativeTests(unittest.TestCase):
    def test_missing_model_version_rejected(self):
        data = _example("eval-suite.example.json")
        data["model"]["version"] = ""
        self.assertTrue(validate(data, SUITE_SCHEMA))

    def test_completion_status_must_be_complete_or_incomplete(self):
        data = _example("eval-suite.example.json")
        data["entries"][0]["completion_status"] = "partial"
        self.assertTrue(validate(data, SUITE_SCHEMA))


class CasesNegativeTests(unittest.TestCase):
    def test_pair_diffs_must_be_an_array_of_objects(self):
        data = _example("eval-cases.example.json")
        data["end_to_end_pairs"][0]["baseline_score"] = "not-a-number"
        self.assertTrue(validate(data, CASES_SCHEMA))

    def test_required_case_counts(self):
        data = _example("eval-cases.example.json")
        data["trigger_cases"]["must_trigger"] = data["trigger_cases"]["must_trigger"][:5]
        self.assertTrue(validate(data, CASES_SCHEMA))


class ReportTests(unittest.TestCase):
    def test_gate_results_keys(self):
        data = _example("eval-report.example.json")
        for gate in ("trigger", "output", "end_to_end"):
            self.assertIn(gate, data["gate_results"], data)


class EffectGateCalculatorSmokeTests(unittest.TestCase):
    """The end-to-end effect gate is a numeric predicate (spec §4.8). Stage A
    only ships the calculator scaffold; per-pair deltas get populated by the
    scoring flow in stage F.
    """

    def setUp(self):
        sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
        from effect_gate import evaluate_effect_gate
        self.evaluate_effect_gate = evaluate_effect_gate

    def test_passing_six_pair_set(self):
        result = self.evaluate_effect_gate({
            "pairs": [
                {"style_fit_baseline": 3.0, "style_fit_six_stage": 4.5, "quality_baseline": 4.0, "quality_six_stage": 4.0},
                {"style_fit_baseline": 2.5, "style_fit_six_stage": 4.0, "quality_baseline": 4.0, "quality_six_stage": 4.0},
                {"style_fit_baseline": 3.5, "style_fit_six_stage": 4.0, "quality_baseline": 4.0, "quality_six_stage": 3.8},
                {"style_fit_baseline": 2.0, "style_fit_six_stage": 4.0, "quality_baseline": 4.0, "quality_six_stage": 4.0},
                {"style_fit_baseline": 3.0, "style_fit_six_stage": 3.5, "quality_baseline": 4.0, "quality_six_stage": 4.0},
                {"style_fit_baseline": 3.0, "style_fit_six_stage": 4.0, "quality_baseline": 4.0, "quality_six_stage": 3.7},
            ],
            "disagreement_per_dimension": {"style_fit": 0.5, "quality": 0.4},
        })
        self.assertEqual(result["verdict"], "pass")
        self.assertGreaterEqual(result["winning_pairs"], 4)
        self.assertGreaterEqual(result["style_fit_median"], 4.0)
        self.assertGreaterEqual(result["pairing_median_delta"], 0.5)
        self.assertGreaterEqual(result["quality_median_delta"], -0.5)
        self.assertEqual(result["undetermined_dimensions"], [])

    def test_below_threshold_demotes_to_limited(self):
        result = self.evaluate_effect_gate({
            "pairs": [
                {"style_fit_baseline": 3.0, "style_fit_six_stage": 3.0, "quality_baseline": 4.0, "quality_six_stage": 4.0}
            ] * 6,
            "disagreement_per_dimension": {"style_fit": 0.0, "quality": 0.0},
        })
        self.assertEqual(result["verdict"], "limited")


if __name__ == "__main__":
    unittest.main()