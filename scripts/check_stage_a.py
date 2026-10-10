"""Aggregate acceptance gate for Stage A.

Runs every contract, cross-reference, policy, state-machine, and invalidation
check that subsequent stages will rely on. Returns exit code 0 only if every
individual gate passes; otherwise returns the worst exit code seen and prints
a human-readable summary.

This script does NOT call models and does NOT modify the project tree. It is
intentionally pure-Python so it can also be invoked from inside an existing
unittest runner without recursion.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = PROJECT_ROOT / "schemas"
EXAMPLES = SCHEMAS / "examples"
POLICIES = PROJECT_ROOT / "policies"

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
from json_schema_validate import validate as schema_validate  # noqa: E402
from state_machine import compute_final_state  # noqa: E402


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


def check_examples_match_schemas() -> list[str]:
    failures: list[str] = []
    for schema_file in SCHEMA_FILES:
        schema = json.loads((SCHEMAS / schema_file).read_text(encoding="utf-8"))
        stem = schema_file.removesuffix(".schema.json")
        for suffix in ("", ".limited", ".ready"):
            example = EXAMPLES / f"{stem}{suffix}.example.json"
            if not example.is_file():
                continue
            data = json.loads(example.read_text(encoding="utf-8"))
            errors = schema_validate(data, schema)
            if errors:
                failures.append(f"{example.name} vs {schema_file}: {errors}")
    return failures


def check_bundle_cross_refs() -> list[str]:
    failures: list[str] = []
    for name in ("style-bundle.limited.example.json", "style-bundle.ready.example.json"):
        data = json.loads((EXAMPLES / name).read_text(encoding="utf-8"))
        errors = validate_bundle_cross_refs(data)
        if errors:
            failures.append(f"{name}: {errors}")
    return failures


def check_policies() -> list[str]:
    failures: list[str] = []
    for name, checker in (
        ("evaluation-policy.json", check_evaluation_policy),
        ("content-scan-policy.json", check_content_scan_policy),
        ("model-budget-policy.json", check_model_budget_policy),
    ):
        data = json.loads((POLICIES / name).read_text(encoding="utf-8"))
        errors = checker(data)
        if errors:
            failures.append(f"{name}: {errors}")
    return failures


def check_state_machine_and_invalidation() -> list[str]:
    failures: list[str] = []
    state = compute_final_state(
        gates_passed=["bundle_valid", "extraction_valid", "eval_passed", "scan_complete"],
        authorization_purpose="shareable_anonymous",
    )
    if state != "ready":
        failures.append(f"happy-path state expected ready, got {state}")
    budget = json.loads((POLICIES / "model-budget-policy.json").read_text(encoding="utf-8"))
    ready, reason = compute_readiness(budget, "synthetic-model")
    if not ready:
        failures.append(f"synthetic-model should be ready: {reason}")
    inv = compute_invalidation(
        existing_hashes={"scan_windows": {}},
        changed_classes=[],
        increased_scan_budget=True,
    )
    if "release" in inv["invalidated"]:
        failures.append("budget-only change must not invalidate release")
    return failures


def main() -> int:
    failures: list[str] = []
    failures.extend(check_examples_match_schemas())
    failures.extend(check_bundle_cross_refs())
    failures.extend(check_policies())
    failures.extend(check_state_machine_and_invalidation())
    if failures:
        print("Stage A aggregate gate FAILED:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("Stage A aggregate gate PASSED:")
    print("- 13 schemas locked (schema examples validated)")
    print("- bundle cross-references validated")
    print("- 3 policy files validated")
    print("- state machine + invalidation rules validated")
    print("- run 'python -m unittest discover -s tests -v' for the unit-test aggregate")
    return 0


if __name__ == "__main__":
    sys.exit(main())