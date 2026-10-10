"""Stage A Task 1: source / chunk / run manifest contract tests.

These tests pin the schema shape for the run-time input pipelines. They use
the vendored Draft 2020-12 subset and the synthetic fixtures shipped under
``schemas/examples/``.

Spec anchors: docs/superpowers/specs/2026-10-09-wenfeng-skill-design.md §4.1.
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


def _load(name: str) -> dict:
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


def _example(name: str) -> dict:
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


SOURCE_SCHEMA = _load("source-manifest.schema.json")
CHUNK_SCHEMA = _load("chunk-manifest.schema.json")
RUN_SCHEMA = _load("run-manifest.schema.json")


class HappyPathTests(unittest.TestCase):
    def test_source_example_is_valid(self):
        self.assertEqual(validate(_example("source-manifest.example.json"), SOURCE_SCHEMA), [])

    def test_chunk_example_is_valid(self):
        self.assertEqual(validate(_example("chunk-manifest.example.json"), CHUNK_SCHEMA), [])

    def test_run_example_is_valid(self):
        self.assertEqual(validate(_example("run-manifest.example.json"), RUN_SCHEMA), [])


class SourceContractNegativeTests(unittest.TestCase):
    def test_missing_source_id(self):
        data = _example("source-manifest.example.json")
        del data["source_id"]
        errors = validate(data, SOURCE_SCHEMA)
        self.assertTrue(any("source_id" in e for e in errors), errors)

    def test_missing_raw_hash_rejected(self):
        data = _example("source-manifest.example.json")
        del data["raw_sha256"]
        errors = validate(data, SOURCE_SCHEMA)
        self.assertTrue(any("raw_sha256" in e for e in errors), errors)

    def test_source_id_must_be_12_hex(self):
        data = _example("source-manifest.example.json")
        data["source_id"] = "Book-Title-12"
        errors = validate(data, SOURCE_SCHEMA)
        self.assertTrue(any("source_id" in e for e in errors), errors)

    def test_missing_model_processing_authorization(self):
        data = _example("source-manifest.example.json")
        data["authorization"]["scope"].pop("model_processing", None)
        errors = validate(data, SOURCE_SCHEMA)
        self.assertTrue(any("authorization" in e or "model_processing" in e for e in errors), errors)


class ChunkContractNegativeTests(unittest.TestCase):
    def test_chunk_start_must_be_less_than_end(self):
        data = _example("chunk-manifest.example.json")
        data["chunks"][0]["char_offset"] = [10, 5]
        errors = validate(data, CHUNK_SCHEMA)
        self.assertTrue(any("char_offset" in e for e in errors), errors)

    def test_chunk_must_not_carry_body(self):
        data = _example("chunk-manifest.example.json")
        data["chunks"][0]["body"] = "do-not-echo-source-text"
        errors = validate(data, CHUNK_SCHEMA)
        self.assertTrue(any("additional" in e or "body" in e for e in errors), errors)


class RunContractNegativeTests(unittest.TestCase):
    def test_run_must_declare_budget_policy_version(self):
        data = _example("run-manifest.example.json")
        del data["run_model_budget_policy_version"]
        errors = validate(data, RUN_SCHEMA)
        self.assertTrue(any("model_budget_policy" in e or "budget" in e.lower() for e in errors), errors)


class ErrorPathTests(unittest.TestCase):
    def test_errors_carry_field_path(self):
        data = _example("chunk-manifest.example.json")
        data["chunks"][0]["char_offset"] = [10, 5]
        errors = validate(data, CHUNK_SCHEMA)
        joined = " | ".join(errors)
        self.assertIn("chunks", joined, errors)


if __name__ == "__main__":
    unittest.main()
