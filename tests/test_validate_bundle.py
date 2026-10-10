import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from validate_bundle import main, validate_bundle  # noqa: E402


def evidence(scene_id: str, chapter_id: str, start: int = 1, end: int = 3) -> dict:
    return {"scene_id": scene_id, "chapter_id": chapter_id, "lines": [start, end]}


def mechanism(
    *,
    status: str = "model_limited",
    evidence_refs: list[dict] | None = None,
    dimension: str = "dialogue_and_subtext",
) -> dict:
    return {
        "mechanism_id": "M01",
        "dimension": dimension,
        "rule": "Use a brief response beat when it changes the scene.",
        "actions": ["Add a visible response after a consequential turn."],
        "scope": "Local scenes where the exchange changes a decision.",
        "evidence": evidence_refs or [evidence("SC01", "C001"), evidence("SC02", "C001")],
        "counterexamples": [
            {
                "scene_id": "SC03",
                "chapter_id": "C001",
                "lines": [4, 5],
                "note": "A continuous factual summary does not need dialogue beats.",
            }
        ],
        "decision_status": status,
        "decision_reason": "Two independent local scenes support this scoped technique.",
    }


def bundle() -> dict:
    return {
        "schema_version": "1",
        "source_id": "012345abcdef",
        "evidence_status": "limited",
        "claimed_dimensions": ["dialogue_and_subtext"],
        "mechanisms": [mechanism()],
        "content_exclusions": [],
        "evaluation_ref": "private-ledger://synthetic-run",
    }


class ValidateBundleTests(unittest.TestCase):
    def test_accepts_a_scoped_limited_bundle(self):
        self.assertEqual(validate_bundle(bundle()), [])

    def test_rejects_empty_mechanism_list(self):
        data = bundle()
        data["mechanisms"] = []
        self.assertTrue(any("at least one" in error for error in validate_bundle(data)))

    def test_rejects_approved_mechanism_below_cross_chapter_threshold(self):
        data = bundle()
        data["mechanisms"] = [
            mechanism(
                status="model_approved",
                evidence_refs=[evidence("SC01", "C001"), evidence("SC02", "C001")],
            )
        ]
        self.assertTrue(any("model_approved" in error for error in validate_bundle(data)))

    def test_rejects_ready_bundle_with_uncovered_claimed_dimension(self):
        data = bundle()
        data["evidence_status"] = "ready"
        data["claimed_dimensions"].append("scene_construction")
        data["mechanisms"][0]["decision_status"] = "model_approved"
        data["mechanisms"][0]["evidence"] = [
            evidence("SC01", "C001"), evidence("SC02", "C002"), evidence("SC03", "C002")
        ]
        self.assertTrue(any("claimed dimension" in error for error in validate_bundle(data)))

    def test_rejects_duplicate_mechanism_ids(self):
        data = bundle()
        second = mechanism(evidence_refs=[evidence("SC04", "C003"), evidence("SC05", "C003")])
        data["mechanisms"].append(second)
        self.assertTrue(any("duplicate mechanism_id" in error for error in validate_bundle(data)))

    def test_rejects_invalid_source_id_and_line_range(self):
        data = bundle()
        data["source_id"] = "Book-Title"
        data["mechanisms"][0]["evidence"][0]["lines"] = [0, 1]
        errors = validate_bundle(data)
        self.assertTrue(any("source_id" in error for error in errors))
        self.assertTrue(any("line range" in error for error in errors))

    def test_reports_unexpected_status_types_without_crashing(self):
        data = bundle()
        data["evidence_status"] = []
        data["mechanisms"][0]["decision_status"] = {}
        errors = validate_bundle(data)
        self.assertTrue(any("evidence_status" in error for error in errors))
        self.assertTrue(any("decision_status" in error for error in errors))

    def test_cli_reports_invalid_json_without_echoing_contents(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "bad.json"
            path.write_text('{"private":"do-not-echo",', encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = main([str(path)])
        self.assertNotEqual(result, 0)
        self.assertNotIn("do-not-echo", output.getvalue())
        self.assertIn("invalid JSON", output.getvalue())


if __name__ == "__main__":
    unittest.main()
