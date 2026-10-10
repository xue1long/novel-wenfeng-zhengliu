"""Stage E Task 7 tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))


class DeterminismTests(unittest.TestCase):
    def test_two_runs_byte_identical(self):
        import check_stage_e  # noqa: E402
        failures = check_stage_e.check_byte_identical_compile()
        self.assertEqual(failures, [], msg=failures)


class ValidateDistTests(unittest.TestCase):
    def test_validate_flags_tampering(self):
        import check_stage_e  # noqa: E402
        failures = check_stage_e.check_validate_dist_after_tamper()
        self.assertEqual(failures, [], msg=failures)


class FailureStagingUnidentifiableTests(unittest.TestCase):
    def test_failed_compile_does_not_write_manifest(self):
        import check_stage_e  # noqa: E402
        failures = check_stage_e.check_failure_staging_unidentifiable()
        self.assertEqual(failures, [], msg=failures)


class LiteralScanEndToEndTests(unittest.TestCase):
    def test_literal_scan_blocks_verbatim_copy(self):
        import check_stage_e  # noqa: E402
        failures = check_stage_e.check_literal_scan_blocks()
        self.assertEqual(failures, [], msg=failures)


if __name__ == "__main__":
    unittest.main()
