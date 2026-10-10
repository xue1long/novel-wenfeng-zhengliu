"""Stage C Task 4 tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from mechanism_merger import (  # noqa: E402
    APPROVED,
    EXCLUDED,
    LIMITED,
    classify_mechanism,
    compute_bundle_evidence_status,
)


def _candidate(
    *,
    mechanism_id: str,
    dimension: str = "narrative_voice",
    scenes=None,
    chapters=None,
    counter_scenes=None,
    review_status: str = "supported",
    rule: str = "Apply technique when X.",
    do_steps=None,
) -> dict:
    scenes = scenes or ["SC01", "SC02", "SC03"]
    chapters = chapters or ["C001", "C002"]
    counter_scenes = counter_scenes or ["SC99"]
    counter_chapters = counter_scenes and ["C999"] or ["C999"]
    refs = [
        {"scene_id": s, "chapter_id": c, "char_offset": [0, 100], "excerpt_hash": "a" * 64}
        for s, c in zip(scenes, chapters * 5)
    ]
    # Keep them unique by (scene, chapter); never exceed len(scenes).
    refs = refs[: max(len(scenes), 1)]
    counter = [
        {"scene_id": cs, "chapter_id": counter_chapters[0], "char_offset": [200, 250], "excerpt_hash": "b" * 64, "note": "n"}
        for cs in counter_scenes
    ]
    return {
        "mechanism_id": mechanism_id,
        "dimension": dimension,
        "rule": rule,
        "do_steps": do_steps or ["Do A.", "Do B."],
        "forbidden_when": "n/a",
        "stage_bindings": ["prose_draft"],
        "evidence_refs": refs,
        "counterexample_refs": counter,
        "extraction_prompt_version": f"{dimension}@0.1.0",
        "review_status": review_status,
    }


class MechanismClassificationTests(unittest.TestCase):
    def test_duplicate_mechanism_id_marked_excluded(self):
        cands = [
            _candidate(mechanism_id="M01", rule="First rule."),
            _candidate(mechanism_id="M01", rule="Second rule."),
        ]
        out = classify_mechanism(cands)
        # Two candidates preserved (mechanism_id is never merged across rules).
        self.assertEqual(len(out), 2)
        # The second one is marked excluded with a duplicate reason.
        excluded_with_dup = [m for m in out if any("duplicate" in r for r in m.reasons)]
        self.assertEqual(len(excluded_with_dup), 1)

    def test_no_counterexample_marks_excluded(self):
        cand = _candidate(mechanism_id="M02", counter_scenes=[])
        cand["counterexample_refs"] = []
        out = classify_mechanism([cand])
        self.assertEqual(out[0].bundle_status, EXCLUDED)
        self.assertTrue(any("no counterexamples" in r for r in out[0].reasons), out[0].reasons)

    def test_supported_with_two_scenes_lands_limited(self):
        cand = _candidate(mechanism_id="M03", scenes=["SC01", "SC02"], chapters=["C001", "C002"])
        out = classify_mechanism([cand])
        self.assertEqual(out[0].bundle_status, LIMITED)

    def test_supported_with_three_scenes_one_chapter_lands_limited(self):
        cand = _candidate(
            mechanism_id="M04",
            scenes=["SC01", "SC02", "SC03"],
            chapters=["C001", "C001", "C001"],
        )
        out = classify_mechanism([cand])
        self.assertEqual(out[0].bundle_status, LIMITED)

    def test_supported_with_three_scenes_two_chapters_lands_approved(self):
        cand = _candidate(
            mechanism_id="M05",
            scenes=["SC01", "SC02", "SC03"],
            chapters=["C001", "C002", "C003"],
        )
        out = classify_mechanism([cand])
        self.assertEqual(out[0].bundle_status, APPROVED)

    def test_unsupported_review_status_never_lands_approved(self):
        cand = _candidate(
            mechanism_id="M06",
            scenes=["SC01", "SC02", "SC03"],
            chapters=["C001", "C002", "C003"],
            review_status="unsupported",
        )
        out = classify_mechanism([cand])
        self.assertEqual(out[0].bundle_status, EXCLUDED)


class CrossDimensionDedupTests(unittest.TestCase):
    def test_near_identical_rules_collapse(self):
        a = _candidate(
            mechanism_id="M10",
            scenes=["SC01", "SC02", "SC03"],
            chapters=["C001", "C002", "C003"],
            rule="Apply technique when X.",
            do_steps=["Do A.", "Do B."],
        )
        b = _candidate(
            mechanism_id="M10",
            scenes=["SC04", "SC05"],
            chapters=["C004", "C005"],
            rule="Apply  technique  when X.",
            do_steps=["Do A.", "Do B."],
        )
        out = classify_mechanism([a, b])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].bundle_status, APPROVED)

    def test_conflicting_do_steps_on_shared_chunk_mark_excluded(self):
        # Two distinct mechanism_ids share the same evidence chunk_id but use
        # different leading verbs in their do_steps. Spec §4.3 step 4 calls
        # this "冲突无法消解" → excluded.
        a = _candidate(
            mechanism_id="M20",
            scenes=["SC01", "SC02", "SC03"],
            chapters=["C001", "C002", "C003"],
            rule="Apply technique when X.",
            do_steps=["Do A.", "Do B."],
        )
        # Force shared chunk_id on M21.
        b = _candidate(
            mechanism_id="M21",
            scenes=["SC01", "SC02", "SC03"],
            chapters=["C001", "C002", "C003"],
            rule="Different rule.",
            do_steps=["Use C.", "Use D."],
        )
        shared_chunk = "ck-shared"
        for ref in a["evidence_refs"] + b["evidence_refs"]:
            ref["chunk_id"] = shared_chunk
        out = classify_mechanism([a, b])
        self.assertEqual(len(out), 2)
        excluded_conflict = [m for m in out if any("conflicts" in r for r in m.reasons)]
        self.assertEqual(len(excluded_conflict), 2)
        self.assertTrue(all(m.bundle_status == EXCLUDED for m in out))


class BundleEvidenceStatusTests(unittest.TestCase):
    def test_empty_returns_excluded(self):
        self.assertEqual(compute_bundle_evidence_status([]), EXCLUDED)

    def test_only_limited_returns_limited(self):
        cands = [_candidate(
            mechanism_id="M30",
            scenes=["SC01", "SC02"],
            chapters=["C001", "C002"],
            review_status="limited",
        )]
        self.assertEqual(compute_bundle_evidence_status(classify_mechanism(cands)), LIMITED)

    def test_any_approved_returns_approved(self):
        cands = [
            _candidate(
                mechanism_id="M40",
                scenes=["SC01", "SC02", "SC03"],
                chapters=["C001", "C002", "C003"],
            ),
            _candidate(
                mechanism_id="M41",
                dimension="sentence_rhythm",
                scenes=["SC01", "SC02"],
                chapters=["C001", "C002"],
                review_status="limited",
            ),
        ]
        self.assertEqual(compute_bundle_evidence_status(classify_mechanism(cands)), APPROVED)


if __name__ == "__main__":
    unittest.main()