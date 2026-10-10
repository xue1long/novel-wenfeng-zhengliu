"""Stage A Task 3: Style Bundle + stage-context contract tests.

Spec anchors: §4.4 (Bundle isolation), §4.6 (stage-context & state machine).
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "vendor"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from json_schema_validate import validate  # noqa: E402

SCHEMAS = PROJECT_ROOT / "schemas"
EXAMPLES = SCHEMAS / "examples"


def _schema(name: str) -> dict:
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


def _example(name: str) -> dict:
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


BUNDLE_SCHEMA = _schema("style-bundle.schema.json")
STAGE_CONTEXT_SCHEMA = _schema("stage-context.schema.json")


class BundleHappyPathTests(unittest.TestCase):
    def test_limited_bundle_example_is_valid(self):
        self.assertEqual(validate(_example("style-bundle.limited.example.json"), BUNDLE_SCHEMA), [])

    def test_ready_bundle_example_is_valid(self):
        self.assertEqual(validate(_example("style-bundle.ready.example.json"), BUNDLE_SCHEMA), [])


class BundleNegativeTests(unittest.TestCase):
    def test_unknown_claimed_dimension_rejected(self):
        data = _example("style-bundle.limited.example.json")
        data["claimed_dimensions"].append("lexical_density")
        self.assertTrue(validate(data, BUNDLE_SCHEMA))

    def test_stage_bindings_malformed_mechanism_id_rejected_by_schema(self):
        data = _example("style-bundle.limited.example.json")
        data["stage_bindings"]["prose_draft"] = ["not-an-id"]
        errors = validate(data, BUNDLE_SCHEMA)
        self.assertTrue(any("pattern" in e for e in errors), errors)

    def test_stage_bindings_reference_missing_mechanism_rejected_by_cross_ref(self):
        data = _example("style-bundle.limited.example.json")
        data["stage_bindings"]["prose_draft"] = ["M99"]
        # Schema alone accepts the well-formed id; the cross-reference checker must reject it.
        self.assertEqual(validate(data, BUNDLE_SCHEMA), [])
        from check_bundle_cross_refs import validate_bundle_cross_refs
        errors = validate_bundle_cross_refs(data)
        self.assertTrue(any("M99" in e and "missing mechanism" in e for e in errors), errors)

    def test_stage_bindings_include_unknown_stage_rejected_by_cross_ref(self):
        data = _example("style-bundle.limited.example.json")
        data["stage_bindings"]["epilogue_polish"] = []
        # Schema rejects via additionalProperties:false on stage_bindings object.
        errors = validate(data, BUNDLE_SCHEMA)
        self.assertTrue(any("additional" in e or "epilogue" in e for e in errors), errors)

    def test_bundle_must_not_contain_source_body(self):
        data = _example("style-bundle.limited.example.json")
        data["mechanisms"][0]["original_excerpt"] = "do-not-echo"
        self.assertTrue(validate(data, BUNDLE_SCHEMA))

    def test_content_exclusions_must_not_list_source_specific_categories_rejected_by_cross_ref(self):
        data = _example("style-bundle.limited.example.json")
        data["content_exclusions"].append("book_name")
        # Schema enum does not list source-specific categories, so the schema must reject.
        errors = validate(data, BUNDLE_SCHEMA)
        self.assertTrue(any("book_name" in e or "enum" in e for e in errors), errors)


class BundleFieldPathTests(unittest.TestCase):
    def test_error_messages_include_field_path(self):
        data = _example("style-bundle.limited.example.json")
        data["stage_bindings"]["prose_draft"] = ["not-an-id"]
        errors = validate(data, BUNDLE_SCHEMA)
        joined = " | ".join(errors)
        self.assertIn("prose_draft", joined, errors)


class StageContextTests(unittest.TestCase):
    def test_valid_mid_chain_stage_context(self):
        self.assertEqual(validate(_example("stage-context.example.json"), STAGE_CONTEXT_SCHEMA), [])

    def test_retry_count_must_be_in_range(self):
        data = _example("stage-context.example.json")
        data["retry_count"] = 4
        self.assertTrue(validate(data, STAGE_CONTEXT_SCHEMA))

    def test_stage_id_must_be_known(self):
        data = _example("stage-context.example.json")
        data["stage_id"] = "polish"
        self.assertTrue(validate(data, STAGE_CONTEXT_SCHEMA))


if __name__ == "__main__":
    unittest.main()