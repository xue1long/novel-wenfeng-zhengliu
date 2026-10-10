"""Stage A Task 2: candidate-mechanism + evidence-ledger contract tests.

Spec anchors: §4.3 (extraction loop) and §4.4 (Bundle isolation).
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


CANDIDATE_SCHEMA = _schema("candidate-mechanism.schema.json")
LEDGER_SCHEMA = _schema("evidence-ledger.schema.json")


def _evidence_ref(scene_id: str = "SC01", chapter_id: str = "C001") -> dict:
    return {
        "chunk_id": "ck-0001-opening",
        "chapter_id": chapter_id,
        "scene_id": scene_id,
        "char_offset": [0, 200],
        "excerpt_hash": "5" * 64,
    }


def _counterexample(scene_id: str = "SC03", chapter_id: str = "C001") -> dict:
    return {
        "chunk_id": "ck-0003-skip",
        "chapter_id": chapter_id,
        "scene_id": scene_id,
        "char_offset": [200, 400],
        "excerpt_hash": "6" * 64,
        "note": "Continuous factual summary does not need the same beat.",
    }


def _approved_candidate() -> dict:
    return {
        "mechanism_id": "M01",
        "dimension": "dialogue_subtext",
        "rule": "After a consequential turn, place one visible response beat.",
        "applies_when": "Any exchange that flips a decision.",
        "do_steps": ["Add a single response beat after the consequential turn."],
        "forbidden_when": "The exchange is a continuous factual summary.",
        "stage_bindings": ["prose_draft", "revision"],
        "evidence_refs": [
            _evidence_ref("SC01", "C001"),
            _evidence_ref("SC02", "C002"),
            _evidence_ref("SC04", "C003"),
        ],
        "counterexample_refs": [_counterexample()],
        "extraction_prompt_version": "extractors/dialogue_subtext.md@0.1.0",
        "review_status": "supported",
    }


def _limited_candidate() -> dict:
    return {
        "mechanism_id": "M02",
        "dimension": "imagery_rhetoric",
        "rule": "Use one shared concrete image in the opening paragraph.",
        "applies_when": "Stories that open inside a single setting.",
        "do_steps": ["Place one concrete image in the opening paragraph."],
        "forbidden_when": "Openings that switch settings in the first scene.",
        "stage_bindings": ["scene_design"],
        "evidence_refs": [_evidence_ref("SC10", "C010"), _evidence_ref("SC11", "C010")],
        "counterexample_refs": [_counterexample("SC99", "C010")],
        "extraction_prompt_version": "extractors/imagery-rhetoric.md@0.1.0",
        "review_status": "limited",
    }


class HappyPathTests(unittest.TestCase):
    def test_approved_example_is_valid(self):
        self.assertEqual(validate(_example("candidate-mechanism.example.json"), CANDIDATE_SCHEMA), [])

    def test_limited_example_is_valid(self):
        self.assertEqual(validate(_example("candidate-mechanism.limited.example.json"), CANDIDATE_SCHEMA), [])

    def test_ledger_example_is_valid(self):
        self.assertEqual(validate(_example("evidence-ledger.example.json"), LEDGER_SCHEMA), [])


class CandidateNegativeTests(unittest.TestCase):
    def test_missing_mechanism_id(self):
        data = _approved_candidate()
        del data["mechanism_id"]
        self.assertTrue(validate(data, CANDIDATE_SCHEMA))

    def test_unknown_dimension_rejected(self):
        data = _approved_candidate()
        data["dimension"] = "lexical_density"
        self.assertTrue(validate(data, CANDIDATE_SCHEMA))

    def test_unknown_review_status_rejected(self):
        data = _approved_candidate()
        data["review_status"] = "model_approved"
        self.assertTrue(validate(data, CANDIDATE_SCHEMA))

    def test_evidence_ref_must_not_carry_body(self):
        data = _approved_candidate()
        data["evidence_refs"][0]["excerpt_body"] = "do-not-echo"
        self.assertTrue(validate(data, CANDIDATE_SCHEMA))

    def test_unknown_stage_in_stage_bindings_rejected(self):
        data = _approved_candidate()
        data["stage_bindings"].append("epilogue_polish")
        self.assertTrue(validate(data, CANDIDATE_SCHEMA))

    def test_counterexample_without_note_rejected(self):
        data = _approved_candidate()
        data["counterexample_refs"][0].pop("note")
        self.assertTrue(validate(data, CANDIDATE_SCHEMA))


class LedgerCodepointLimitTests(unittest.TestCase):
    def test_excerpt_at_200_codepoints_passes(self):
        data = json.loads((EXAMPLES / "evidence-ledger.example.json").read_text(encoding="utf-8"))
        excerpt = data["entries"][0]["excerpt"]
        self.assertEqual(len(excerpt), 200)
        self.assertEqual(validate(data, LEDGER_SCHEMA), [])

    def test_excerpt_at_201_codepoints_rejected(self):
        data = json.loads((EXAMPLES / "evidence-ledger.example.json").read_text(encoding="utf-8"))
        data["entries"][0]["excerpt"] = data["entries"][0]["excerpt"] + "X"
        self.assertEqual(len(data["entries"][0]["excerpt"]), 201)
        self.assertTrue(validate(data, LEDGER_SCHEMA))


if __name__ == "__main__":
    unittest.main()