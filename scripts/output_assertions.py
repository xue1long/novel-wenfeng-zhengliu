"""Stage F Task 2: per-stage output contract assertions.

Pure stdlib. Validates that each stage's projected output satisfies the
data contract from Stage D (``six_stage_contract.STAGE_DATA_CONTRACT``):

  - ``required_inputs`` keys must appear in ``output``;
  - ``primary_output`` field name must match the contract's primary_output;
  - at least one ``stop_condition_hit`` key must be present in ``output`` if
    the contract lists stop_conditions;
  - if a ``bundle`` is supplied, the output must not reference excluded
    mechanism ids (a bundle-level hard gate).

Stage §4.8 (3): mechanical asserts MUST reach 100% pass; missing output
falls to ``incomplete`` rather than counted as a pass.

This module never makes a model call. It only inspects the dict the
caller hands it.
"""

from __future__ import annotations

from six_stage_contract import STAGE_DATA_CONTRACT, StageContract


SIX_STAGES: tuple[str, ...] = (
    "write_entry",
    "scene_design",
    "character_beats",
    "prose_draft",
    "style_check",
    "revision",
)


class OutputContractError(Exception):
    def __init__(self, message: str, *, error_type: str = "output_contract_error") -> None:
        super().__init__(message)
        self.error_type = error_type


def _normalize_inputs(stage_id: str) -> tuple[str, ...]:
    contract = STAGE_DATA_CONTRACT[stage_id]
    out: list[str] = []
    for key in contract.required_inputs:
        if key.startswith("stage_context_input_refs."):
            out.append(key.split(".", 1)[1])
    return tuple(out)


def assert_output_contract(
    stage_id: str,
    output: dict,
    *,
    bundle: dict | None = None,
) -> list[str]:
    """Return error messages. Empty list = the output passes the contract."""
    errors: list[str] = []
    if stage_id not in STAGE_DATA_CONTRACT:
        return [f"unknown stage_id {stage_id!r}"]
    if not isinstance(output, dict):
        return [f"output must be a JSON object, got {type(output).__name__}"]
    contract: StageContract = STAGE_DATA_CONTRACT[stage_id]
    expected_inputs = _normalize_inputs(stage_id)
    missing = [k for k in expected_inputs if k not in output]
    if missing:
        errors.append(f"{stage_id}: missing required inputs {missing!r}")
    if "primary_output" not in output:
        errors.append(f"{stage_id}: missing primary_output field")
    elif output["primary_output"] != contract.primary_output:
        errors.append(
            f"{stage_id}: primary_output mismatch (expected {contract.primary_output!r}, "
            f"got {output['primary_output']!r})"
        )
    if "stop_condition_hit" not in output:
        errors.append(f"{stage_id}: missing stop_condition_hit field")
    elif output["stop_condition_hit"] not in contract.constraints:
        errors.append(
            f"{stage_id}: stop_condition_hit {output['stop_condition_hit']!r} not in "
            f"contract constraints {list(contract.constraints)!r}"
        )
    if bundle is not None:
        excluded_ids = {
            m["mechanism_id"]
            for m in (bundle.get("mechanisms") or [])
            if m.get("review_status") == "excluded" and m.get("mechanism_id")
        }
        referenced = (output.get("mechanism_ids_applied") or [])
        if excluded_ids and any(mid in excluded_ids for mid in referenced):
            errors.append(
                f"{stage_id}: output references excluded mechanism(s) "
                f"{sorted(excluded_ids & set(referenced))!r}"
            )
    return errors


def evaluate_all_stages(
    results: dict[str, dict],
    *,
    bundle: dict | None = None,
) -> dict:
    """Aggregate contract check across all six stages.

    ``results`` maps ``stage_id -> output_dict``. A stage whose output is
    missing entirely is reported in ``missing_outputs`` and contributes to
    ``incomplete`` (spec §4.8 (3) "缺输出为 incomplete").

    Returns a dict with ``passed`` / ``failed`` / ``mechanical_pass_rate`` /
    ``missing_outputs``.
    """
    passed = 0
    failed = 0
    missing_outputs: list[str] = []
    details: dict[str, dict] = {}
    for stage_id in SIX_STAGES:
        if stage_id not in results:
            missing_outputs.append(stage_id)
            details[stage_id] = {"status": "incomplete", "errors": ["output missing"]}
            continue
        errs = assert_output_contract(stage_id, results[stage_id], bundle=bundle)
        if errs:
            failed += 1
            details[stage_id] = {"status": "failed", "errors": errs}
        else:
            passed += 1
            details[stage_id] = {"status": "passed", "errors": []}
    denom = len(SIX_STAGES)
    return {
        "passed": passed,
        "failed": failed,
        "missing_outputs": missing_outputs,
        "mechanical_pass_rate": passed / denom if denom else 0.0,
        "details": details,
    }


__all__ = [
    "SIX_STAGES",
    "OutputContractError",
    "assert_output_contract",
    "evaluate_all_stages",
]