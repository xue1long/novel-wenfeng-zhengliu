"""Stage F Task 4: final-state aggregation.

Pure stdlib. Composes Stage A's ``state_machine.compute_final_state`` with
the three eval gates plus two hardening checks:

  - missing_outputs (Stage §4.8 (3)): any missing stage output flips the
    final state to ``incomplete``.
  - has_unredacted_artifacts: if the eval-report still carries private
    fields, the final state is forced to ``blocked`` (Ruling-F4).
"""

from __future__ import annotations

from typing import Iterable

from state_machine import compute_final_state


class StateAggregationError(Exception):
    def __init__(self, message: str, *, error_type: str = "state_aggregation_error") -> None:
        super().__init__(message)
        self.error_type = error_type


# Mirrors state_machine.STATES but cached here for tests.
STATES = ("incomplete", "blocked", "limited", "ready")


def record_state_transition(
    run_journal_path,
    *,
    from_state: str,
    to_state: str,
    evidence: dict,
) -> None:
    """Append a state-transition entry to ``run-manifest.json``'s ``step_log``.

    Idempotent on the (from_state, to_state, evidence_hash) triple. The
    evidence is not permitted to contain source-specific fields; we strip
    any ``source_body`` / ``book_name`` keys defensively.
    """
    import json
    from pathlib import Path

    path = Path(run_journal_path)
    if not path.is_file():
        raise StateAggregationError(f"run-manifest.json missing at {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    cleaned_evidence = {
        key: value
        for key, value in evidence.items()
        if key not in {"source_body", "book_name", "author_name"}
    }
    evidence_hash = str(sorted(cleaned_evidence.items()))
    log = data.setdefault("step_log", [])
    for entry in log:
        if (
            entry.get("step_id") == f"state:{from_state}->{to_state}"
            and entry.get("error_type") == evidence_hash
        ):
            return
    log.append({
        "step_id": f"state:{from_state}->{to_state}",
        "input_hash": "0" * 64,
        "prompt_template_version": "wenfeng-final-state@0.1.0",
        "model_id": "synthetic-model",
        "output_path": f"private-ledger://{data.get('run_id', 'unknown')}/state-transition",
        "output_hash": "0" * 64,
        "status": "succeeded",
        "retry_count": 0,
        "error_type": evidence_hash,
    })
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def compute_run_state(
    gates_passed: set[str],
    authorization_purpose: str,
) -> str:
    """Re-export of stage A's compute_final_state for stage F callers."""
    return compute_final_state(gates_passed, authorization_purpose)


def evaluate_evaluation_state(
    trigger: dict,
    output_eval: dict,
    end_to_end: dict,
    *,
    has_unredacted_artifacts: bool,
    missing_outputs: Iterable[str],
    authorization_purpose: str = "shareable_anonymous",
) -> str:
    """Aggregate three gates + two hardening checks into a final state.

    ``authorization_purpose`` is passed to the stage A state machine: it
    determines whether a fully-green run can land at ``ready`` (only
    ``shareable_*`` purposes allow that) or must stay at ``limited`` /
    ``incomplete`` (private_only).

    Default is ``shareable_anonymous`` because the Stage F CLI itself does
    not gate on user-provided authorization; callers that have a real
    private_only run should pass it explicitly.
    """
    gates: set[str] = set()
    if trigger.get("all_stages_meet_precision_and_recall_threshold"):
        gates.add("bundle_valid")
    if trigger.get("stages_with_full_coverage", 0) > 0:
        gates.add("extraction_valid")
    if output_eval.get("mechanical_pass_rate", 0.0) >= 1.0:
        gates.add("eval_passed")
    if end_to_end.get("verdict") == "pass":
        gates.add("scan_complete")
    if output_eval.get("mechanical_pass_rate", 0.0) >= 1.0 and end_to_end.get("verdict") == "pass":
        gates.add("all_gates_passed")
    state = compute_run_state(gates, authorization_purpose=authorization_purpose)
    missing = list(missing_outputs)
    if missing:
        state = "incomplete"
    if has_unredacted_artifacts:
        state = "blocked"
    return state


__all__ = [
    "STATES",
    "StateAggregationError",
    "record_state_transition",
    "compute_run_state",
    "evaluate_evaluation_state",
]