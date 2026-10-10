"""Stage F Task 2 tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from output_assertions import (  # noqa: E402
    assert_output_contract,
    evaluate_all_stages,
)


SIX_STAGES = (
    "write_entry", "scene_design", "character_beats",
    "prose_draft", "style_check", "revision",
)


def _good_output(stage_id: str) -> dict:
    if stage_id == "write_entry":
        return {
            "stage_id": stage_id,
            "primary_output": "stage-context",
            "stop_condition_hit": "does_not_call_other_skills",
            "trace_id": "t-1",
            "stage_order": ["write_entry", "scene_design", "character_beats",
                              "prose_draft", "style_check", "revision"],
        }
    if stage_id == "scene_design":
        return {
            "stage_id": stage_id,
            "primary_output": "scene_plan",
            "stop_condition_hit": "no_source_plot",
            "user_brief": "...",
            "constraints": "...",
        }
    if stage_id == "character_beats":
        return {
            "stage_id": stage_id,
            "primary_output": "character_beats",
            "stop_condition_hit": "no_source_character_mapping",
            "scene_plan": "...",
            "user_characters": "...",
        }
    if stage_id == "prose_draft":
        return {
            "stage_id": stage_id,
            "primary_output": "prose_draft",
            "stop_condition_hit": "only_approved_or_limited_mechanisms",
            "scene_plan": "...",
            "character_beats": "...",
            "bundle_mechanisms": ["M01"],
            "mechanism_ids_applied": ["M01"],
        }
    if stage_id == "style_check":
        return {
            "stage_id": stage_id,
            "primary_output": "diagnostics",
            "stop_condition_hit": "diagnose_only",
            "prose_draft": "...",
            "bundle_mechanisms": ["M01"],
            "hard_constraints": "...",
        }
    if stage_id == "revision":
        return {
            "stage_id": stage_id,
            "primary_output": "final_text",
            "stop_condition_hit": "preserve_user_ending",
            "prose_draft": "...",
            "style_check_report": "...",
            "hard_constraints": "...",
        }
    raise ValueError(stage_id)


class HappyPathTests(unittest.TestCase):
    def test_every_stage_passes_clean(self):
        results = {sid: _good_output(sid) for sid in SIX_STAGES}
        agg = evaluate_all_stages(results)
        self.assertEqual(agg["passed"], 6)
        self.assertEqual(agg["failed"], 0)
        self.assertEqual(agg["missing_outputs"], [])
        self.assertEqual(agg["mechanical_pass_rate"], 1.0)

    def test_single_stage_pass(self):
        for sid in SIX_STAGES:
            errors = assert_output_contract(sid, _good_output(sid))
            self.assertEqual(errors, [], f"{sid}: {errors}")


class NegativeTests(unittest.TestCase):
    def test_missing_required_input(self):
        bad = _good_output("scene_design")
        del bad["user_brief"]
        errors = assert_output_contract("scene_design", bad)
        self.assertTrue(any("missing required inputs" in e for e in errors), errors)

    def test_primary_output_mismatch(self):
        bad = _good_output("scene_design")
        bad["primary_output"] = "wrong_field"
        errors = assert_output_contract("scene_design", bad)
        self.assertTrue(any("primary_output mismatch" in e for e in errors), errors)

    def test_excluded_mechanism_in_output(self):
        bad = _good_output("prose_draft")
        bad["mechanism_ids_applied"] = ["M99"]
        bundle = {"mechanisms": [{"mechanism_id": "M99", "review_status": "excluded"}]}
        errors = assert_output_contract("prose_draft", bad, bundle=bundle)
        self.assertTrue(any("excluded" in e for e in errors), errors)

    def test_stop_condition_invalid(self):
        bad = _good_output("scene_design")
        bad["stop_condition_hit"] = "totally_made_up_token"
        errors = assert_output_contract("scene_design", bad)
        self.assertTrue(any("not in contract constraints" in e for e in errors), errors)

    def test_output_format_wrong(self):
        errors = assert_output_contract("scene_design", "not a dict")  # type: ignore[arg-type]
        self.assertTrue(any("must be a JSON object" in e for e in errors), errors)

    def test_unknown_stage(self):
        errors = assert_output_contract("epilogue_polish", {})
        self.assertTrue(any("unknown stage_id" in e for e in errors), errors)


class MissingOutputTests(unittest.TestCase):
    def test_missing_output_marked_incomplete(self):
        results = {sid: _good_output(sid) for sid in SIX_STAGES}
        del results["style_check"]
        agg = evaluate_all_stages(results)
        self.assertEqual(agg["passed"], 5)
        self.assertEqual(agg["failed"], 0)
        self.assertEqual(agg["missing_outputs"], ["style_check"])


if __name__ == "__main__":
    unittest.main()