"""Read-only policy gate checks for Stage A.

Implements the structural gates named in spec §4.1, §4.4 and §4.8. Does not
modify any files and does not call any model.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


EVAL_REQUIRED_FIELDS = {
    "must_trigger_count",
    "must_not_trigger_count",
    "boundary_count",
    "precision_min",
    "recall_min",
    "end_to_end_min_pairs",
    "end_to_end_min_winning_pairs",
    "end_to_end_min_pairing_median_delta",
    "end_to_end_min_style_fit_median",
    "end_to_end_min_quality_median_delta",
    "end_to_end_disagreement_threshold",
}

SCAN_OVERLIMIT_OPTIONS = {"block", "degrade_to_limited", "retry"}
BUDGET_OVERLIMIT_OPTIONS = {"block", "degrade_to_limited", "retry"}
BUDGET_PROFILE_FIELDS = {
    "max_requests",
    "max_input_tokens_total",
    "max_tokens_per_batch",
    "overlimit_policy",
}


def check_evaluation_policy(data: dict) -> list[str]:
    errors: list[str] = []
    cases = data.get("trigger_cases") or {}
    thresholds = data.get("thresholds") or {}
    missing_cases = {"must_trigger_count", "must_not_trigger_count", "boundary_count"} - set(cases.keys())
    if missing_cases:
        errors.append(f"trigger_cases missing fields: {sorted(missing_cases)}")
    if cases.get("must_trigger_count", 0) < 10:
        errors.append("trigger_cases.must_trigger_count must be >= 10")
    if cases.get("must_not_trigger_count", 0) < 10:
        errors.append("trigger_cases.must_not_trigger_count must be >= 10")
    if cases.get("boundary_count", 0) < 5:
        errors.append("trigger_cases.boundary_count must be >= 5")
    missing_thresholds = EVAL_REQUIRED_FIELDS - set(thresholds.keys()) - {"must_trigger_count", "must_not_trigger_count", "boundary_count"}
    if missing_thresholds:
        errors.append(f"thresholds missing fields: {sorted(missing_thresholds)}")
    if thresholds.get("precision_min", 0) < 0.90:
        errors.append("thresholds.precision_min must be >= 0.90")
    if thresholds.get("recall_min", 0) < 0.90:
        errors.append("thresholds.recall_min must be >= 0.90")
    return errors


def check_content_scan_policy(data: dict) -> list[str]:
    errors: list[str] = []
    controls = data.get("controls") or {}
    if controls.get("positives_count", 0) < 20:
        errors.append("controls.positives_count must be >= 20")
    if controls.get("negatives_count", 0) < 20:
        errors.append("controls.negatives_count must be >= 20")
    if controls.get("negative_misblock_max", -1) < 0:
        errors.append("controls.negative_misblock_max must be >= 0")
    if controls.get("negative_misblock_max", 0) > controls.get("negatives_count", 0):
        errors.append("controls.negative_misblock_max cannot exceed negatives_count")
    if data.get("overlimit_policy") not in SCAN_OVERLIMIT_OPTIONS:
        errors.append(f"overlimit_policy must be one of {sorted(SCAN_OVERLIMIT_OPTIONS)}")
    return errors


def check_model_budget_policy(data: dict) -> list[str]:
    errors: list[str] = []
    supported = data.get("supported_models") or []
    if not isinstance(supported, list) or not supported:
        errors.append("supported_models must be a non-empty list")
        return errors
    profiles = data.get("profiles") or {}
    if not isinstance(profiles, dict):
        errors.append("profiles must be an object")
        return errors
    for model_id in supported:
        profile = profiles.get(model_id)
        if not isinstance(profile, dict):
            errors.append(f"profile missing for supported model: {model_id}")
            continue
        missing = BUDGET_PROFILE_FIELDS - set(profile.keys())
        if missing:
            errors.append(f"profile[{model_id}] missing fields: {sorted(missing)}")
        if profile.get("overlimit_policy") not in BUDGET_OVERLIMIT_OPTIONS:
            errors.append(
                f"profile[{model_id}].overlimit_policy must be one of {sorted(BUDGET_OVERLIMIT_OPTIONS)}"
            )
        for field in ("max_requests", "max_input_tokens_total", "max_tokens_per_batch"):
            if field in profile and not isinstance(profile[field], int) or (
                field in profile and profile[field] is not None and profile[field] < 1
            ):
                errors.append(f"profile[{model_id}].{field} must be a positive integer")
    return errors


def compute_readiness(policy: dict, model_id: str) -> tuple[bool, str]:
    supported = policy.get("supported_models") or []
    profiles = policy.get("profiles") or {}
    if model_id not in supported:
        return False, f"model {model_id!r} not declared in supported_models"
    profile = profiles.get(model_id)
    if not isinstance(profile, dict):
        return False, f"missing profile for model {model_id!r}"
    if BUDGET_PROFILE_FIELDS - set(profile.keys()):
        return False, f"profile for model {model_id!r} missing numeric fields"
    if profile.get("overlimit_policy") not in BUDGET_OVERLIMIT_OPTIONS:
        return False, f"profile for model {model_id!r} has invalid overlimit_policy"
    return True, "ready"


def gate_reason_categories() -> list[str]:
    return [
        "evaluation_policy_incomplete",
        "content_scan_policy_incomplete",
        "model_budget_profile_incomplete",
    ]


def _run(path: Path) -> int:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as error:
        print(f"invalid JSON in {path}: line {error.lineno}, column {error.colno}")
        return 2
    except OSError as error:
        print(f"could not read {path}: {error.strerror or 'file access failed'}")
        return 2
    name = path.stem
    if name == "evaluation-policy":
        errors = check_evaluation_policy(data)
    elif name == "content-scan-policy":
        errors = check_content_scan_policy(data)
    elif name == "model-budget-policy":
        errors = check_model_budget_policy(data)
    else:
        print(f"unknown policy file: {path}")
        return 2
    if errors:
        print(f"{name} is invalid:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"{name} is valid.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only policy gate checks for Stage A."
    )
    parser.add_argument("paths", nargs="+", help="Paths to policy JSON files")
    args = parser.parse_args(argv)
    exit_codes = []
    for raw in args.paths:
        path = Path(raw)
        exit_codes.append(_run(path))
    worst = max(exit_codes) if exit_codes else 2
    return worst


if __name__ == "__main__":
    sys.exit(main())