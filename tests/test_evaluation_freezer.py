"""Stage F Task 5 tests."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from evaluation_freezer import (  # noqa: E402
    FreezerError,
    freeze_all_artifacts,
    write_eval_cases,
    write_eval_report,
    write_eval_suite,
)


def _good_suite() -> dict:
    return {
        "suite_version": "0.1.0",
        "policy_version": "0.1.0",
        "model": {"id": "synthetic-model", "version": "0.1.0"},
        "prompt_version": "wenfeng-eval-prompts@0.1.0",
        "tool_version": "wenfeng-skill@0.1.0",
        "case_version": "cases@0.1.0",
        "generation_params": {"temperature": 0.0},
        "budget": {
            "max_requests": 64,
            "max_input_tokens_total": 200000,
            "max_tokens_per_batch": 8000,
            "overlimit_policy": "degrade_to_limited",
        },
        "entries": [],
    }


def _good_cases() -> dict:
    return {
        "case_version": "0.1.0",
        "trigger_cases": {
            "must_trigger": [
                {"case_id": f"T-MT-{i:02d}", "stage_id": "prose_draft", "input_excerpt": "x"}
                for i in range(10)
            ],
            "must_not_trigger": [
                {"case_id": f"T-NT-{i:02d}", "stage_id": "prose_draft", "input_excerpt": "y"}
                for i in range(10)
            ],
            "boundary": [
                {"case_id": f"T-BD-{i:02d}", "input_excerpt": "z"}
                for i in range(5)
            ],
        },
        "output_cases": [
            {"case_id": "O-001", "stage_id": "prose_draft", "kind": "normal"},
        ],
        "end_to_end_pairs": [
            {"pair_id": f"EP-{i:02d}", "brief": "b", "scenario_class": "opening_meet"}
            for i in range(6)
        ],
    }


def _good_report() -> dict:
    return {
        "report_version": "0.1.0",
        "bundle_id": "bundle-x-v0_1_0",
        "gate_results": {
            "trigger": {"precision": 1.0, "recall": 1.0, "passed": True},
            "output": {"mechanical_pass_rate": 1.0, "passed": True},
            "end_to_end": {
                "verdict": "pass",
                "winning_pairs": 6,
                "style_fit_median": 4.5,
                "pairing_median_delta": 1.5,
                "quality_median_delta": 0.0,
                "undetermined_dimensions": [],
                "passed": True,
            },
        },
        "summary": {"final_state": "limited", "notes": "happy"},
    }


def _staging(tmp: Path) -> Path:
    root = tmp / "staging"
    root.mkdir()
    (root / "scene_design").mkdir()
    (root / "scene_design" / "SKILL.md").write_text("# scene_design", encoding="utf-8")
    (root / "compile-manifest.json").write_text('{"k":"v"}', encoding="utf-8")
    return root


class HappyPathTests(unittest.TestCase):
    def test_full_cycle_writes_three_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            staging = _staging(Path(tmp))
            write_eval_suite(staging, _good_suite())
            write_eval_cases(staging, _good_cases())
            write_eval_report(
                staging, _good_report(),
                source_id="0" * 12, bundle_id="bundle-x-v0_1_0",
            )
            for name in ("eval-suite.json", "eval-cases.json", "eval-report.json"):
                self.assertTrue((staging / name).is_file())

    def test_redact_strips_private_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            staging = _staging(Path(tmp))
            r = _good_report()
            r["unblinding_map"] = {"EP-00": "private"}
            write_eval_report(
                staging, r,
                source_id="0" * 12, bundle_id="bundle-x-v0_1_0",
            )
            written = json.loads((staging / "eval-report.json").read_text(encoding="utf-8"))
            self.assertNotIn("unblinding_map", written)
            self.assertIn("unblinding_map", written["summary"]["notes"])

    def test_freeze_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            staging = _staging(Path(tmp))
            r1 = _good_report()
            hashes1 = freeze_all_artifacts(
                staging, eval_generation_text={"EP-00": "first"}, report=r1
            )
            # The second call uses a fresh, structurally identical report so
            # the hashes match deterministically.
            r2 = _good_report()
            hashes2 = freeze_all_artifacts(
                staging, eval_generation_text={"EP-00": "first"}, report=r2
            )
            self.assertEqual(hashes1, hashes2)
            self.assertIn("scene_design/SKILL.md", hashes1)
            self.assertIn("case:EP-00", hashes1)


class NegativeTests(unittest.TestCase):
    def test_suite_missing_required_field_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            staging = _staging(Path(tmp))
            bad = _good_suite()
            del bad["model"]
            with self.assertRaises(FreezerError):
                write_eval_suite(staging, bad)

    def test_cases_missing_precision_field_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            staging = _staging(Path(tmp))
            bad = _good_cases()
            bad["trigger_cases"]["must_trigger"] = bad["trigger_cases"]["must_trigger"][:5]
            with self.assertRaises(FreezerError):
                write_eval_cases(staging, bad)

    def test_redact_requires_source_and_bundle_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            staging = _staging(Path(tmp))
            with self.assertRaises(FreezerError):
                write_eval_report(staging, _good_report())


if __name__ == "__main__":
    unittest.main()