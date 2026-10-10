"""Stage D Task 4 tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from invalidation_rules import InvalidationClass  # noqa: E402
from stage_context_validator import (  # noqa: E402
    MissingInput,
    StaleMechanismReference,
    UnknownStageId,
    invalidate_stage_context,
    raise_stage_context_errors,
    validate_stage_context,
)


def _minimal(stage_id: str = "scene_design", *, refs: list[str] | None = None) -> dict:
    return {
        "contract_version": "0.1.0",
        "trace_id": "trace-2026-10-09-synthetic",
        "bundle_id": "bundle-0a1b2c3d4e5f-v0_1_0",
        "stage_id": stage_id,
        "retry_count": 0,
        "stage_snapshot": {
            "input_refs": refs if refs is not None else ["private-ledger://synthetic"],
            "output_refs": [],
            "changed_fields": ["scene_plan"],
        },
        "error_report": {"error_type": "none"},
        "next_stage": "character_beats",
        "return_to": None,
    }


def _bundle(mechanism_ids: list[str]) -> dict:
    return {
        "mechanisms": [
            {"mechanism_id": mid, "stage_bindings": ["prose_draft"]}
            for mid in mechanism_ids
        ],
    }


class NegativeTests(unittest.TestCase):
    def test_unknown_stage_id(self):
        ctx = _minimal()
        ctx["stage_id"] = "epilogue_polish"
        errors = validate_stage_context(ctx)
        self.assertTrue(any("stage_id" in e for e in errors), errors)

    def test_retry_count_4(self):
        ctx = _minimal()
        ctx["retry_count"] = 4
        errors = validate_stage_context(ctx)
        self.assertTrue(any("retry_count" in e for e in errors), errors)

    def test_stale_mechanism_reference(self):
        ctx = _minimal(refs=["bundle://mechanism/M02"])
        bundle = _bundle(["M01"])
        errors = validate_stage_context(ctx, bundle=bundle)
        self.assertTrue(any("M02" in e for e in errors), errors)

    def test_missing_changed_fields(self):
        ctx = _minimal()
        ctx["stage_snapshot"]["changed_fields"] = []
        errors = validate_stage_context(ctx)
        self.assertTrue(any("changed_fields" in e for e in errors), errors)


class PositiveTests(unittest.TestCase):
    def test_full_context_passes(self):
        ctx = _minimal(refs=["bundle://mechanism/M01"])
        errors = validate_stage_context(ctx, bundle=_bundle(["M01"]))
        self.assertEqual(errors, [], errors)

    def test_return_to_null_passes(self):
        ctx = _minimal()
        ctx["return_to"] = None
        errors = validate_stage_context(ctx)
        self.assertEqual(errors, [], errors)

    def test_terminal_stage_passes(self):
        ctx = _minimal(stage_id="completed")
        errors = validate_stage_context(ctx)
        self.assertEqual(errors, [], errors)


class StaleReferenceDownstreamBlockTests(unittest.TestCase):
    def test_stale_reference_raises(self):
        ctx = _minimal(refs=["bundle://mechanism/M99"])
        bundle = _bundle(["M01"])
        errors = validate_stage_context(ctx, bundle=bundle)
        self.assertTrue(any("M99" in e for e in errors), errors)
        with self.assertRaises(StaleMechanismReference):
            raise_stage_context_errors(errors)


class InvalidateStageContextTests(unittest.TestCase):
    def test_extraction_prompt_change_invalidates_downstream(self):
        result = invalidate_stage_context({}, InvalidationClass.EXTRACTION_PROMPT_VERSION)
        self.assertIn("prose_draft", result)

    def test_source_fingerprint_change_invalidates_all(self):
        result = invalidate_stage_context({}, InvalidationClass.SOURCE_FINGERPRINT)
        self.assertIn("write_entry", result)
        self.assertIn("revision", result)

    def test_scan_policy_change_does_not_touch_chain(self):
        result = invalidate_stage_context({}, InvalidationClass.SCAN_POLICY_VERSION)
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()