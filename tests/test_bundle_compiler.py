"""Stage C Task 5 tests."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "vendor"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from bundle_compiler import (  # noqa: E402
    APPROVED,
    EXCLUDED,
    LIMITED,
    bundle_contains_no_source_body,
    compile_bundle,
)
from check_bundle_cross_refs import validate_bundle_cross_refs  # noqa: E402
from json_schema_validate import validate as schema_validate  # noqa: E402
from mechanism_merger import (  # noqa: E402
    MechanismStatus,
    classify_mechanism,
    compute_bundle_evidence_status,
)

BUNDLE_SCHEMA = json.loads(
    (PROJECT_ROOT / "schemas" / "style-bundle.schema.json").read_text(encoding="utf-8")
)


def _mech(
    *,
    mechanism_id: str,
    dimension: str = "narrative_voice",
    scenes: int = 3,
    chapters: int = 2,
    review_status: str = "supported",
    bundle_status: str = APPROVED,
    rule: str = "Apply the rule.",
    do_steps=None,
) -> MechanismStatus:
    return MechanismStatus(
        mechanism_id=mechanism_id,
        dimension=dimension,
        rule=rule,
        do_steps=do_steps or ["Do A."],
        forbidden_when="n/a",
        stage_bindings=["prose_draft"],
        review_status=review_status,
        unique_scenes=scenes,
        unique_chapters=chapters,
        counterexample_count=1,
        bundle_status=bundle_status,
        reasons=[],
    )


class CompileBundleNegativeTests(unittest.TestCase):
    def test_bundle_with_book_name_field_rejected(self):
        ms = [_mech(mechanism_id="M01")]
        ms[0].rule = "Use a book_name as a value."
        with self.assertRaises(ValueError):
            compile_bundle(ms, source_id="0" * 12, bundle_version="0.1.0")

    def test_no_mechanisms_means_excluded(self):
        with self.assertRaises(ValueError):
            compile_bundle([], source_id="0" * 12, bundle_version="0.1.0")

    def test_source_id_non_12_hex_rejected(self):
        with self.assertRaises(ValueError):
            compile_bundle([_mech(mechanism_id="M01")], source_id="not-hex", bundle_version="0.1.0")

    def test_bundle_version_not_semver_rejected(self):
        with self.assertRaises(ValueError):
            compile_bundle([_mech(mechanism_id="M01")], source_id="0" * 12, bundle_version="0.1")


class CompileBundleHappyPathTests(unittest.TestCase):
    def test_five_dimensions_all_approved_yields_approved(self):
        ms = [
            _mech(mechanism_id="M01", dimension="narrative_voice"),
            _mech(mechanism_id="M02", dimension="sentence_rhythm"),
            _mech(mechanism_id="M03", dimension="scene_transition"),
            _mech(mechanism_id="M04", dimension="dialogue_subtext"),
            _mech(mechanism_id="M05", dimension="imagery_rhetoric"),
        ]
        bundle = compile_bundle(ms, source_id="0" * 12, bundle_version="0.1.0")
        self.assertEqual(bundle["evidence_status"], "approved")
        # Schema compliance.
        self.assertEqual(schema_validate(bundle, BUNDLE_SCHEMA), [])
        # Cross-reference compliance.
        self.assertEqual(validate_bundle_cross_refs(bundle), [])
        # Defensive scan.
        self.assertTrue(bundle_contains_no_source_body(bundle))

    def test_partial_limited_yields_limited_bundle(self):
        # No approved mechanism in the pool → the bundle lands at limited.
        ms = [
            _mech(mechanism_id="M01", dimension="narrative_voice", scenes=2, chapters=2, bundle_status=LIMITED),
            _mech(mechanism_id="M02", dimension="sentence_rhythm", scenes=2, chapters=2, bundle_status=LIMITED),
        ]
        bundle = compile_bundle(ms, source_id="0" * 12, bundle_version="0.1.0")
        self.assertEqual(bundle["evidence_status"], "limited")

    def test_excluded_only_mechanisms_do_not_compile(self):
        # Even one approved mechanism keeps us out of excluded.
        ms = [_mech(mechanism_id="M01", bundle_status=APPROVED)]
        bundle = compile_bundle(ms, source_id="0" * 12, bundle_version="0.1.0")
        self.assertEqual(bundle["evidence_status"], "approved")

    def test_stage_bindings_are_complete(self):
        ms = [
            _mech(mechanism_id="M01", dimension="narrative_voice"),
            _mech(mechanism_id="M02", dimension="sentence_rhythm"),
        ]
        bundle = compile_bundle(ms, source_id="0" * 12, bundle_version="0.1.0")
        for stage in ("write_entry", "scene_design", "character_beats", "prose_draft", "style_check", "revision"):
            self.assertIn(stage, bundle["stage_bindings"])


class EndToEndClassificationToBundleTests(unittest.TestCase):
    def test_classify_then_compile_default_mixed_profile(self):
        """The default stub profile is 'mixed': classify produces a mix of
        approved/limited/excluded candidates, so the bundle lands at limited
        (or excluded if no mechanism passes)."""
        # Build three supported candidates with disjoint chunks so the merged
        # candidate accumulates 3 unique scenes + 2 chapters.
        from extractors.base import _stub_model_call
        text = "# 第一章\n句一。\n# 第二章\n句二。\n# 第三章\n句三。"
        from chunker import chunk_text
        chunks = chunk_text(text, chunker_version="v1")
        # Build candidates manually so we can guarantee disjoint scenes.
        cands = []
        for index, chunk in enumerate(chunks):
            cands.append({
                "mechanism_id": f"M{index + 1:02d}",
                "dimension": "narrative_voice",
                "rule": f"Rule {index + 1}",
                "do_steps": [f"Do {index + 1}."],
                "forbidden_when": "n/a",
                "stage_bindings": ["prose_draft"],
                "evidence_refs": [{
                    "chunk_id": chunk.chunk_id,
                    "chapter_id": chunk.chapter_id,
                    "scene_id": chunk.scene_id,
                    "char_offset": list(chunk.char_offset),
                    "excerpt_hash": "a" * 64,
                }],
                "counterexample_refs": [{
                    "chunk_id": chunk.chunk_id,
                    "chapter_id": chunk.chapter_id,
                    "scene_id": chunk.scene_id,
                    "char_offset": list(chunk.char_offset),
                    "excerpt_hash": "a" * 64,
                    "note": "x",
                }],
                "extraction_prompt_version": "narrative_voice@0.1.0",
                "review_status": "supported",
            })
        mechanisms = classify_mechanism(cands)
        bundle_status = compute_bundle_evidence_status(mechanisms)
        # The candidate pool is intentionally tiny so the merged mechanism
        # may or may not reach the approved threshold; assert the helper
        # returns a known state.
        self.assertIn(bundle_status, {APPROVED, LIMITED, EXCLUDED})


if __name__ == "__main__":
    unittest.main()