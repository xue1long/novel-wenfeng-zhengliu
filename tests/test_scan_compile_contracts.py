"""Stage A Task 5: content-scan / compile / release manifest contracts.

Spec anchors: §4.4 (scan), §4.7 (compile manifest), §4.9 (release manifest).
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


SCAN_SCHEMA = _schema("content-scan-report.schema.json")
COMPILE_SCHEMA = _schema("compile-manifest.schema.json")
RELEASE_SCHEMA = _schema("release-manifest.schema.json")


class HappyPathTests(unittest.TestCase):
    def test_scan_report_example_is_valid(self):
        self.assertEqual(validate(_example("content-scan-report.example.json"), SCAN_SCHEMA), [])

    def test_compile_manifest_example_is_valid(self):
        self.assertEqual(validate(_example("compile-manifest.example.json"), COMPILE_SCHEMA), [])

    def test_release_manifest_example_is_valid(self):
        self.assertEqual(validate(_example("release-manifest.example.json"), RELEASE_SCHEMA), [])


class ScanReportNegativeTests(unittest.TestCase):
    def test_missing_policy_version_rejected(self):
        data = _example("content-scan-report.example.json")
        del data["policy_version"]
        self.assertTrue(validate(data, SCAN_SCHEMA))

    def test_window_result_enum_enforced(self):
        data = _example("content-scan-report.example.json")
        data["windows"][0]["result"] = "probably_fine"
        self.assertTrue(validate(data, SCAN_SCHEMA))


class CompileManifestNegativeTests(unittest.TestCase):
    FORBIDDEN = ["generated_at", "timestamp", "created_at", "build_time", "build_date"]

    def test_no_generation_timestamps_allowed(self):
        for forbidden in self.FORBIDDEN:
            data = _example("compile-manifest.example.json")
            data[forbidden] = "2026-10-09T00:00:00Z"
            self.assertTrue(
                validate(data, COMPILE_SCHEMA),
                f"{forbidden} should be rejected",
            )

    def test_must_contain_six_stage_hashes(self):
        data = _example("compile-manifest.example.json")
        del data["skill_hashes"]["revision"]
        self.assertTrue(validate(data, COMPILE_SCHEMA))


class ReleaseManifestNegativeTests(unittest.TestCase):
    def test_shareable_true_without_authorization_rejected_by_handler(self):
        """Stage A schema has no ``shareable`` field; adding it is rejected
        by the schema. The semantic check that shareable=true requires
        authorization_purpose=shareable_* lives in
        scripts/package_state_gate.py and is exercised in T5."""
        data = _example("release-manifest.example.json")
        data["shareable"] = True
        data["authorization_purpose"] = "private_only"
        # Schema rejects the unknown property.
        self.assertNotEqual(validate(data, RELEASE_SCHEMA), [])

    def test_release_must_not_carry_source_body(self):
        data = _example("release-manifest.example.json")
        data["body_excerpt"] = "do-not-echo"
        self.assertNotEqual(validate(data, RELEASE_SCHEMA), [])

    def test_window_field_enumeration_for_scan_summary(self):
        data = _example("release-manifest.example.json")
        data["content_scan_summary"] = {"window_results": {"weird_state": 1}}
        # Schema rejects the unknown property.
        self.assertNotEqual(validate(data, RELEASE_SCHEMA), [])


if __name__ == "__main__":
    unittest.main()