"""Self-tests for the vendored JSON Schema validator subset.

Stage A Task 0 requires the vendored file to actually work for the keyword set
the stage A schemas depend on. These tests pin its behaviour before any other
schema is written on top of it.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "vendor"))

from json_schema_validate import SchemaUnsupportedError, is_valid, validate  # noqa: E402


class TypeKeywordTests(unittest.TestCase):
    def test_string_accepted(self):
        self.assertEqual(validate("hi", {"type": "string"}), [])

    def test_integer_rejects_bool_subclass_unlike_draft(self):
        # Vendored subset intentionally keeps bool separate from int to avoid the
        # "true is 1" foot-gun for required strings such as IDs and enums.
        errors = validate(True, {"type": "integer"})
        self.assertTrue(errors, "booleans must not satisfy type:integer here")


class EnumAndConstTests(unittest.TestCase):
    def test_enum_miss_reports_value(self):
        errors = validate("c", {"enum": ["a", "b"]})
        self.assertTrue(errors and "enum" in errors[0])

    def test_const_match_passes(self):
        self.assertEqual(validate("ready", {"const": "ready"}), [])


class NumberKeywordTests(unittest.TestCase):
    def test_maximum_rejects(self):
        errors = validate(11, {"maximum": 10})
        self.assertTrue(errors and "maximum" in errors[0])


class StringKeywordTests(unittest.TestCase):
    def test_min_length_and_pattern(self):
        schema = {"type": "string", "minLength": 3, "pattern": r"^[a-z]+$"}
        self.assertEqual(validate("abc", schema), [])
        self.assertTrue(validate("AB", schema))
        self.assertTrue(validate("aBc", schema))


class ArrayKeywordTests(unittest.TestCase):
    def test_unique_items_detects_duplicates(self):
        schema = {"type": "array", "uniqueItems": True, "items": {"type": "integer"}}
        self.assertTrue(validate([1, 2, 1], schema))

    def test_min_items(self):
        schema = {"type": "array", "minItems": 2, "items": {"type": "string"}}
        self.assertEqual(validate(["a", "b"], schema), [])
        self.assertTrue(validate(["a"], schema))


class ObjectKeywordTests(unittest.TestCase):
    def test_required_missing_field(self):
        schema = {"type": "object", "required": ["x"], "properties": {"x": {"type": "integer"}}}
        errors = validate({}, schema)
        self.assertTrue(any("x" in e for e in errors))

    def test_additional_properties_false(self):
        schema = {
            "type": "object",
            "properties": {"a": {"type": "string"}},
            "additionalProperties": False,
        }
        errors = validate({"a": "ok", "b": "no"}, schema)
        self.assertTrue(any("additional" in e for e in errors))

    def test_nested_object_validation(self):
        schema = {
            "type": "object",
            "properties": {
                "child": {
                    "type": "object",
                    "required": ["name"],
                    "properties": {"name": {"type": "string", "minLength": 1}},
                }
            },
        }
        self.assertEqual(validate({"child": {"name": "x"}}, schema), [])
        self.assertTrue(validate({"child": {}}, schema))


class RefTests(unittest.TestCase):
    def test_internal_ref_resolves(self):
        schema = {
            "$defs": {"pos": {"type": "integer", "minimum": 0}},
            "type": "object",
            "properties": {"x": {"$ref": "#/$defs/pos"}},
        }
        self.assertEqual(validate({"x": 1}, schema), [])
        self.assertTrue(validate({"x": -1}, schema))


class CompositionKeywordTests(unittest.TestCase):
    def test_oneOf_requires_exactly_one(self):
        schema = {"oneOf": [{"type": "integer"}, {"type": "string"}]}
        self.assertEqual(validate(1, schema), [])
        self.assertEqual(validate("a", schema), [])
        self.assertTrue(validate(1.5, schema))

    def test_not_rejects_matching(self):
        schema = {"not": {"type": "string"}}
        self.assertEqual(validate(1, schema), [])
        self.assertTrue(validate("x", schema))


class UnsupportedKeywordTests(unittest.TestCase):
    def test_unknown_type_raises(self):
        with self.assertRaises(SchemaUnsupportedError):
            validate(1, {"type": "datetime"})


class FormatKeywordTests(unittest.TestCase):
    def test_uri_reference_requires_non_empty(self):
        schema = {"type": "string", "format": "uri-reference"}
        self.assertEqual(validate("private-ledger://synthetic-run", schema), [])
        self.assertTrue(validate("", schema))


class IsValidShortcuts(unittest.TestCase):
    def test_is_valid_returns_bool(self):
        self.assertTrue(is_valid({"x": 1}, {"type": "object"}))
        self.assertFalse(is_valid("nope", {"type": "integer"}))


class WenfengVendoredExtensionTests(unittest.TestCase):
    def test_open_range_rejects_equal_or_reversed(self):
        schema = {"type": "array", "minItems": 2, "maxItems": 2, "items": {"type": "integer"}, "x-wenfengRange": "open"}
        self.assertEqual(validate([0, 5], schema), [])
        self.assertTrue(validate([5, 5], schema))
        self.assertTrue(validate([10, 5], schema))

    def test_open_range_requires_integers(self):
        schema = {"type": "array", "minItems": 2, "maxItems": 2, "x-wenfengRange": "open"}
        self.assertTrue(validate([0.5, 1.5], schema))
        self.assertTrue(validate([0, "x"], schema))

    def test_codepoint_max_distinguishes_unicode(self):
        # The vendored cap counts Unicode codepoints. An emoji like 😀 is 1
        # codepoint but 2 UTF-16 code units; the cap must see it as 1.
        schema = {"type": "string", "x-wenfengCodepointMax": 4}
        self.assertEqual(validate("abcd", schema), [])
        self.assertTrue(validate("abcde", schema))
        self.assertEqual(validate("\U0001F600" * 4, schema), [])  # 4 emoji = 4 codepoints
        self.assertTrue(validate("\U0001F600" * 5, schema))


if __name__ == "__main__":
    unittest.main()