"""Stage A Task 0: contracts meta must be locked.

Asserts that ``schemas/_meta.json`` exists, contains all required fields, and
that the two either/or fields have settled on a single concrete value rather
than a ``TBD`` placeholder. This file is the first gate any stage A work must
pass.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
META_PATH = PROJECT_ROOT / "schemas" / "_meta.json"

ALLOWED_DIALECTS = {"draft-2020-12", "draft-2019-09"}
ALLOWED_LIBRARIES = {"stdlib", "vendored"}


class ContractsMetaTests(unittest.TestCase):
    def test_meta_file_exists(self):
        self.assertTrue(
            META_PATH.is_file(),
            f"expected contracts meta file at {META_PATH}",
        )

    def test_meta_has_required_fields(self):
        data = json.loads(META_PATH.read_text(encoding="utf-8"))
        for field in ("schema_dialect", "schema_library", "locked_at", "owner"):
            self.assertIn(field, data, f"missing field: {field}")
            self.assertIsInstance(data[field], str, f"{field} must be a string")
            self.assertNotIn("TBD", data[field], f"{field} still contains TBD")

    def test_dialect_is_locked(self):
        data = json.loads(META_PATH.read_text(encoding="utf-8"))
        self.assertIn(
            data["schema_dialect"],
            ALLOWED_DIALECTS,
            f"schema_dialect must be one of {sorted(ALLOWED_DIALECTS)}",
        )

    def test_library_is_locked(self):
        data = json.loads(META_PATH.read_text(encoding="utf-8"))
        self.assertIn(
            data["schema_library"],
            ALLOWED_LIBRARIES,
            f"schema_library must be one of {sorted(ALLOWED_LIBRARIES)}",
        )

    def test_vendored_library_points_at_existing_file(self):
        data = json.loads(META_PATH.read_text(encoding="utf-8"))
        if data["schema_library"] == "vendored":
            self.assertIn("vendor_path", data, "vendored library must declare vendor_path")
            vendor_path = PROJECT_ROOT / data["vendor_path"]
            self.assertTrue(
                vendor_path.is_file(),
                f"vendored library file missing: {vendor_path}",
            )


if __name__ == "__main__":
    unittest.main()