"""Stage G Task 5 tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from package_state_gate import (  # noqa: E402
    PackageGateDecision,
    PackageGateError,
    PackageProfile,
    assert_decision,
    deny_reason,
    evaluate_package_state,
)


class ShareableProfileTests(unittest.TestCase):
    def test_ready_anonymous_allowed(self):
        d = evaluate_package_state("ready", "shareable_anonymous", PackageProfile.SHAREABLE)
        self.assertEqual(d, PackageGateDecision.ALLOWED)

    def test_ready_with_attribution_allowed(self):
        d = evaluate_package_state("ready", "shareable_with_attribution", PackageProfile.SHAREABLE)
        self.assertEqual(d, PackageGateDecision.ALLOWED)

    def test_ready_private_only_denied(self):
        d = evaluate_package_state("ready", "private_only", PackageProfile.SHAREABLE)
        self.assertEqual(d, PackageGateDecision.DENIED)

    def test_limited_shareable_denied(self):
        d = evaluate_package_state("limited", "shareable_anonymous", PackageProfile.SHAREABLE)
        self.assertEqual(d, PackageGateDecision.DENIED)
        self.assertIn("requires final_state=ready", deny_reason("limited", "shareable_anonymous", PackageProfile.SHAREABLE))

    def test_blocked_shareable_denied(self):
        d = evaluate_package_state("blocked", "shareable_anonymous", PackageProfile.SHAREABLE)
        self.assertEqual(d, PackageGateDecision.DENIED)

    def test_incomplete_shareable_denied(self):
        d = evaluate_package_state("incomplete", "shareable_anonymous", PackageProfile.SHAREABLE)
        self.assertEqual(d, PackageGateDecision.DENIED)


class PrivatePreviewProfileTests(unittest.TestCase):
    def test_limited_private_preview_allowed(self):
        d = evaluate_package_state("limited", "private_only", PackageProfile.PRIVATE_PREVIEW)
        self.assertEqual(d, PackageGateDecision.PRIVATE_ALLOWED)

    def test_blocked_private_preview_denied(self):
        d = evaluate_package_state("blocked", "private_only", PackageProfile.PRIVATE_PREVIEW)
        self.assertEqual(d, PackageGateDecision.DENIED)

    def test_incomplete_private_preview_denied(self):
        d = evaluate_package_state("incomplete", "private_only", PackageProfile.PRIVATE_PREVIEW)
        self.assertEqual(d, PackageGateDecision.DENIED)

    def test_ready_private_preview_denied(self):
        # ready should not produce a private preview; it goes through shareable.
        d = evaluate_package_state("ready", "private_only", PackageProfile.PRIVATE_PREVIEW)
        self.assertEqual(d, PackageGateDecision.DENIED)


class AssertDecisionTests(unittest.TestCase):
    def test_assert_decision_allowed_returns(self):
        d = assert_decision("ready", "shareable_anonymous", PackageProfile.SHAREABLE)
        self.assertEqual(d, PackageGateDecision.ALLOWED)

    def test_assert_decision_denied_raises(self):
        with self.assertRaises(PackageGateError):
            assert_decision("blocked", "shareable_anonymous", PackageProfile.SHAREABLE)

    def test_assert_decision_private_allowed(self):
        d = assert_decision("limited", "private_only", PackageProfile.PRIVATE_PREVIEW)
        self.assertEqual(d, PackageGateDecision.PRIVATE_ALLOWED)


if __name__ == "__main__":
    unittest.main()