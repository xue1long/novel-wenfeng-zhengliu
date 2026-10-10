"""Stage F Task 3 tests."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from end_to_end_eval import (  # noqa: E402
    PairResult,
    RedactionError,
    evaluate_effect_gate,
    freeze_evaluation_artifacts,
    redact_eval_report,
)


SIX_STAGES = (
    "write_entry", "scene_design", "character_beats",
    "prose_draft", "style_check", "revision",
)


def _good_pair(idx: int) -> PairResult:
    """Six pairs, each with baseline below six_stage by ~0.7."""
    return PairResult(
        pair_id=f"EP-{idx:02d}",
        scenario_class="opening_meet" if idx % 2 == 0 else "conflict_climax",
        baseline_score=3.0,
        six_stage_score=4.5,
        quality_baseline=4.0,
        quality_six_stage=4.0,
    )


class HappyPathTests(unittest.TestCase):
    def test_six_pairs_all_winning_yields_ready(self):
        pairs = [_good_pair(i) for i in range(6)]
        result = evaluate_effect_gate(pairs)
        self.assertEqual(result["verdict"], "pass")
        self.assertGreaterEqual(result["winning_pairs"], 4)
        self.assertGreaterEqual(result["style_fit_median"], 4.0)
        self.assertGreaterEqual(result["pairing_median_delta"], 0.5)
        self.assertGreaterEqual(result["quality_median_delta"], -0.5)
        self.assertEqual(result["undetermined_dimensions"], [])

    def test_redact_strips_private_fields(self):
        report = {
            "summary": {"final_state": "ready", "notes": "happy path"},
            "gate_results": {"trigger": {"passed": True}},
            "unblinding_map": {"EP-00": "pair-00-baseline-text"},
            "pair_results": [{"pair_id": "EP-00", "score": 4.5}],
            "rating_secrets": {"EP-00": 0.9},
        }
        redacted = redact_eval_report(report, source_id="0" * 12, bundle_id="bundle-x")
        self.assertNotIn("unblinding_map", redacted)
        self.assertNotIn("pair_results", redacted)
        self.assertNotIn("rating_secrets", redacted)
        self.assertIn("unblinding_map", redacted["summary"]["notes"])
        self.assertEqual(redacted["summary"]["final_state"], "ready")

    def test_freeze_artifacts_is_idempotent_and_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "scene_design").mkdir()
            (root / "scene_design" / "SKILL.md").write_text("# scene_design", encoding="utf-8")
            (root / "compile-manifest.json").write_text('{"k":"v"}', encoding="utf-8")
            generation = {"EP-00": "first generation", "EP-01": "second"}
            report = {"gate_results": {"end_to_end": {"passed": True}}}
            frozen1 = freeze_evaluation_artifacts(
                staging_root=root, eval_generation_text=generation, report=report
            )
            frozen2 = freeze_evaluation_artifacts(
                staging_root=root, eval_generation_text=generation, report=report
            )
            self.assertEqual(frozen1, frozen2)
            self.assertIn("scene_design/SKILL.md", frozen1)
            self.assertIn("compile-manifest.json", frozen1)
            self.assertIn("case:EP-00", frozen1)
            self.assertIn("case:EP-01", frozen1)
            self.assertIn("report", frozen1)


class NegativeTests(unittest.TestCase):
    def test_pairs_lt_six_demotes_to_limited(self):
        pairs = [_good_pair(i) for i in range(3)]
        result = evaluate_effect_gate(pairs)
        self.assertEqual(result["verdict"], "limited")
        self.assertEqual(result["reason"], "need at least 6 pairs, got 3")

    def test_winning_pairs_below_threshold_demotes(self):
        # Only 3 of 6 pairs have six_stage winning -> winning_pairs = 3 < 4.
        pairs = []
        for i in range(6):
            if i < 3:
                # baseline wins
                pairs.append(PairResult(
                    pair_id=f"EP-{i:02d}", scenario_class="x",
                    baseline_score=4.5, six_stage_score=3.0,
                    quality_baseline=4.0, quality_six_stage=4.0,
                ))
            else:
                # six_stage wins
                pairs.append(PairResult(
                    pair_id=f"EP-{i:02d}", scenario_class="x",
                    baseline_score=3.0, six_stage_score=4.5,
                    quality_baseline=4.0, quality_six_stage=4.0,
                ))
        result = evaluate_effect_gate(pairs)
        self.assertEqual(result["winning_pairs"], 3)
        # median delta = +0.0 (3 wins of +1.5 vs 3 wins of -1.5) which is < +0.5
        # so the verdict must be "limited".
        self.assertEqual(result["verdict"], "limited")

    def test_quality_delta_below_threshold_demotes(self):
        pairs = []
        for i in range(6):
            pairs.append(PairResult(
                pair_id=f"EP-{i:02d}", scenario_class="x",
                baseline_score=3.0, six_stage_score=4.5,
                quality_baseline=4.0, quality_six_stage=2.0,  # quality drops
            ))
        result = evaluate_effect_gate(pairs)
        self.assertEqual(result["verdict"], "limited")
        # median quality delta = -2.0 < -0.5

    def test_disagreement_above_one_demotes_to_limited(self):
        pairs = [_good_pair(i) for i in range(6)]
        result = evaluate_effect_gate(
            pairs, disagreement_per_dimension={"style_fit": 1.5}
        )
        self.assertEqual(result["verdict"], "limited")
        self.assertIn("style_fit", result["undetermined_dimensions"])


class RedactionNegativeTests(unittest.TestCase):
    def test_redaction_records_removed_fields(self):
        redacted = redact_eval_report(
            {"summary": {}, "unblinding_map": {"a": "b"}, "pair_results": [{"x": 1}]},
            source_id="0" * 12, bundle_id="bundle-x",
        )
        notes = redacted["summary"]["notes"]
        self.assertIn("unblinding_map", notes)
        self.assertIn("pair_results", notes)

    def test_redaction_rejects_non_dict(self):
        with self.assertRaises(RedactionError):
            redact_eval_report("not a dict", source_id="0" * 12, bundle_id="bundle-x")


if __name__ == "__main__":
    unittest.main()