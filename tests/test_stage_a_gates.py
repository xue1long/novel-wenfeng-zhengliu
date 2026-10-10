"""Stage A Task 8: aggregate acceptance gate.

This test loads every stage-A contract artifact and asserts that they are
internally consistent. The companion ``scripts/check_stage_a.py`` is the
command-line entry point that downstream stages depend on before they start.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "vendor"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from check_bundle_cross_refs import validate_bundle_cross_refs  # noqa: E402
from check_policy_gate import (  # noqa: E402
    check_content_scan_policy,
    check_evaluation_policy,
    check_model_budget_policy,
    compute_readiness,
)
from invalidation_rules import compute_invalidation  # noqa: E402
from json_schema_validate import validate  # noqa: E402
from state_machine import compute_final_state, transition  # noqa: E402

# Imported only to verify the aggregate CLI entry point runs without recursion
# when invoked from inside this test process.
import check_stage_a  # noqa: E402


SCHEMAS = PROJECT_ROOT / "schemas"
EXAMPLES = SCHEMAS / "examples"
POLICIES = PROJECT_ROOT / "policies"

SCHEMA_FILES = [
    "source-manifest.schema.json",
    "chunk-manifest.schema.json",
    "run-manifest.schema.json",
    "candidate-mechanism.schema.json",
    "evidence-ledger.schema.json",
    "style-bundle.schema.json",
    "stage-context.schema.json",
    "eval-suite.schema.json",
    "eval-cases.schema.json",
    "eval-report.schema.json",
    "content-scan-report.schema.json",
    "compile-manifest.schema.json",
    "release-manifest.schema.json",
]

EXAMPLE_BUNDLES = [
    "style-bundle.limited.example.json",
    "style-bundle.ready.example.json",
]


class AggregateGateTests(unittest.TestCase):
    def test_all_examples_match_their_schemas(self):
        for schema_file in SCHEMA_FILES:
            schema_path = SCHEMAS / schema_file
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            stem = schema_file.removesuffix(".schema.json")
            for suffix in ("", ".limited", ".ready"):
                example_path = EXAMPLES / f"{stem}{suffix}.example.json"
                if not example_path.is_file():
                    continue
                data = json.loads(example_path.read_text(encoding="utf-8"))
                errors = validate(data, schema)
                self.assertEqual(errors, [], f"{example_path.name} vs {schema_file}: {errors}")

    def test_bundle_cross_refs(self):
        for name in EXAMPLE_BUNDLES:
            data = json.loads((EXAMPLES / name).read_text(encoding="utf-8"))
            errors = validate_bundle_cross_refs(data)
            self.assertEqual(errors, [], f"{name}: {errors}")

    def test_policies_pass_their_gate(self):
        for name, checker in (
            ("evaluation-policy.json", check_evaluation_policy),
            ("content-scan-policy.json", check_content_scan_policy),
            ("model-budget-policy.json", check_model_budget_policy),
        ):
            data = json.loads((POLICIES / name).read_text(encoding="utf-8"))
            errors = checker(data)
            self.assertEqual(errors, [], f"{name}: {errors}")

    def test_ready_state_requires_authorization_for_share(self):
        result = compute_final_state(
            gates_passed=["bundle_valid", "extraction_valid", "eval_passed", "scan_complete"],
            authorization_purpose="private_only",
        )
        self.assertEqual(result, "limited")
        result = compute_final_state(
            gates_passed=["bundle_valid", "extraction_valid", "eval_passed", "scan_complete"],
            authorization_purpose="shareable_anonymous",
        )
        self.assertEqual(result, "ready")

    def test_blocked_state_is_unrecoverable(self):
        self.assertEqual(transition("blocked", "all_gates_passed"), "blocked")

    def test_increasing_scan_budget_alone_does_not_invalidate_release(self):
        result = compute_invalidation(
            existing_hashes={"scan_windows": {}},
            changed_classes=[],
            increased_scan_budget=True,
        )
        self.assertNotIn("release", result["invalidated"])

    def test_compute_readiness_returns_false_for_incomplete_profile(self):
        data = json.loads((POLICIES / "model-budget-policy.json").read_text(encoding="utf-8"))
        del data["profiles"]["synthetic-model"]["max_input_tokens_total"]
        ready, reason = compute_readiness(data, "synthetic-model")
        self.assertFalse(ready)
        self.assertIn("missing", reason)

    def test_check_stage_a_main_returns_zero(self):
        rc = check_stage_a.main()
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()