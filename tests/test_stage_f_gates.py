"""Stage F Task 7 tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))


class HappyPathTests(unittest.TestCase):
    def test_happy_yields_ready(self):
        import check_stage_f  # noqa: E402
        failures = check_stage_f.check_happy_yields_ready()
        self.assertEqual(failures, [], msg=failures)

    def test_mixed_yields_limited(self):
        import check_stage_f  # noqa: E402
        failures = check_stage_f.check_mixed_yields_limited()
        self.assertEqual(failures, [], msg=failures)

    def test_contains_private_yields_blocked(self):
        import check_stage_f  # noqa: E402
        failures = check_stage_f.check_contains_private_yields_blocked()
        self.assertEqual(failures, [], msg=failures)


class NoNetworkImportTests(unittest.TestCase):
    def test_no_network_module_imported(self):
        import check_stage_f  # noqa: E402
        failures = check_stage_f.check_no_network_import()
        self.assertEqual(failures, [], msg=failures)


if __name__ == "__main__":
    unittest.main()
