"""Stage G Task 7 tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))


class ShareableHappyPathTests(unittest.TestCase):
    def test_shareable_package_then_verify(self):
        import check_stage_g  # noqa: E402
        failures = check_stage_g.check_shareable_happy_path()
        self.assertEqual(failures, [], msg=failures)


class PrivatePreviewTests(unittest.TestCase):
    def test_private_preview_package_then_verify(self):
        import check_stage_g  # noqa: E402
        failures = check_stage_g.check_private_preview_path()
        self.assertEqual(failures, [], msg=failures)


class BlockedPathTests(unittest.TestCase):
    def test_blocked_denied_on_both_profiles(self):
        import check_stage_g  # noqa: E402
        failures = check_stage_g.check_blocked_path_denied()
        self.assertEqual(failures, [], msg=failures)


class InstallDryRunTests(unittest.TestCase):
    def test_dry_run_does_not_touch_target(self):
        import check_stage_g  # noqa: E402
        failures = check_stage_g.check_install_dry_run_does_not_touch_target()
        self.assertEqual(failures, [], msg=failures)


class InstallUserScopeTests(unittest.TestCase):
    def test_user_scope_writes_and_refuses_standard(self):
        import check_stage_g  # noqa: E402
        failures = check_stage_g.check_install_user_writes_and_refuses_standard()
        self.assertEqual(failures, [], msg=failures)


class NoNetworkImportTests(unittest.TestCase):
    def test_no_network_module_imported(self):
        import check_stage_g  # noqa: E402
        failures = check_stage_g.check_no_network_import()
        self.assertEqual(failures, [], msg=failures)


class ReleaseManifestPrivateFieldsTests(unittest.TestCase):
    def test_release_manifest_refuses_private_fields(self):
        import check_stage_g  # noqa: E402
        failures = check_stage_g.check_release_manifest_refuses_private()
        self.assertEqual(failures, [], msg=failures)


if __name__ == "__main__":
    unittest.main()
