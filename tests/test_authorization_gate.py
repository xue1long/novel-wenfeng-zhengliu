"""Stage B Task 5: model-processing consent and share-scope gate.

Spec anchor: §4.1 '授权声明' and §6 阶段 B 验收'授权缺失不调用模型'.

The gate is pure-Python and never writes files; it returns a list of error
messages (empty means allowed). Stage B-T8 CLI uses this gate before
creating any run-root contents.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from authorization_gate import (  # noqa: E402
    AuthorizationBlocked,
    assert_authorized_or_block,
    check_authorization,
)


def _auth(**overrides) -> dict:
    base = {
        "scope": {
            "model_processing": "hosted_with_consent",
        },
        "evidence_basis": "user_declaration",
    }
    for key, value in overrides.items():
        if "." in key:
            head, tail = key.split(".", 1)
            base[head][tail] = value
        else:
            base[key] = value
    return base


class AuthorizationNegativeTests(unittest.TestCase):
    def test_missing_model_processing_rejected(self):
        auth = _auth()
        del auth["scope"]["model_processing"]
        errors = check_authorization(auth, requested_model_id="local", requested_purpose="private_only")
        self.assertTrue(any("model_processing" in e for e in errors), errors)

    def test_missing_derivative_use_allowed_for_private_only(self):
        auth = _auth()
        errors = check_authorization(auth, requested_model_id="local", requested_purpose="private_only")
        self.assertEqual(errors, [], errors)

    def test_missing_derivative_use_rejected_for_shareable(self):
        errors = check_authorization(
            _auth(), requested_model_id="local", requested_purpose="shareable_anonymous"
        )
        self.assertTrue(any("derivative_use" in e for e in errors), errors)

    def test_hosted_model_with_local_only_scope_rejected(self):
        auth = _auth(**{"scope.model_processing": "local_only"})
        errors = check_authorization(auth, requested_model_id="gpt-4", requested_purpose="private_only")
        self.assertTrue(any("model_processing" in e or "local_only" in e for e in errors), errors)

    def test_shareable_purpose_with_private_use_rejected(self):
        auth = _auth(**{"scope.derivative_use": "private_only"})
        errors = check_authorization(auth, requested_model_id="local", requested_purpose="shareable_anonymous")
        self.assertTrue(any("shareable" in e or "derivative_use" in e for e in errors), errors)

    def test_empty_authorization_rejected(self):
        errors = check_authorization({}, requested_model_id="local", requested_purpose="private_only")
        self.assertGreater(len(errors), 0)


class AuthorizationHappyPathTests(unittest.TestCase):
    def test_local_model_with_private_use_passes(self):
        auth = _auth(**{"scope.model_processing": "local_only"})
        errors = check_authorization(auth, requested_model_id="local", requested_purpose="private_only")
        self.assertEqual(errors, [], errors)

    def test_hosted_with_consent_and_shareable_anonymous_passes(self):
        auth = _auth(**{"scope.derivative_use": "shareable_anonymous"})
        errors = check_authorization(auth, requested_model_id="gpt-4", requested_purpose="shareable_anonymous")
        self.assertEqual(errors, [], errors)

    def test_hosted_only_with_shareable_with_attribution_passes(self):
        auth = _auth(**{
            "scope.model_processing": "hosted_only",
            "scope.derivative_use": "shareable_with_attribution",
        })
        errors = check_authorization(auth, requested_model_id="gpt-4", requested_purpose="shareable_with_attribution")
        self.assertEqual(errors, [], errors)


class AuthorizationBlockHelperTests(unittest.TestCase):
    def test_assert_helper_raises_on_failure(self):
        auth = _auth(**{"scope.model_processing": "local_only"})
        with self.assertRaises(AuthorizationBlocked) as cm:
            assert_authorized_or_block(auth, requested_model_id="gpt-4", requested_purpose="private_only")
        self.assertEqual(cm.exception.error_type, "authorization_missing")

    def test_assert_helper_returns_none_on_success(self):
        auth = _auth()
        self.assertIsNone(assert_authorized_or_block(auth, requested_model_id="gpt-4", requested_purpose="private_only"))


if __name__ == "__main__":
    unittest.main()
