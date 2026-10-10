"""Stage A run state machine.

Pure functions only. No I/O, no model calls.

Spec §4.6 fixes the four legal states and the hard-blocked transitions:
  - incomplete / blocked / limited / ready
  - blocked cannot transition to ready
  - ready requires authorization_purpose to allow sharing
"""

from __future__ import annotations

STATES = ("incomplete", "blocked", "limited", "ready")

EVENT_TRANSITIONS: dict[tuple[str, str], str] = {
    ("incomplete", "step_resumed"): "incomplete",
    ("incomplete", "step_failed"): "incomplete",
    ("incomplete", "authorization_missing"): "blocked",
    ("incomplete", "scan_budget_exhausted"): "incomplete",
    ("incomplete", "evidence_quote_invalid"): "blocked",
    ("incomplete", "exact_copy_detected"): "blocked",
    ("incomplete", "semantic_risk_flagged"): "blocked",
    ("incomplete", "schema_validation_failed"): "blocked",
    ("limited", "all_gates_passed"): "ready",
    ("limited", "scan_budget_exhausted"): "limited",
    ("limited", "semantic_risk_flagged"): "blocked",
    ("limited", "evidence_quote_invalid"): "blocked",
    ("ready", "release_artifact_built"): "ready",
    ("ready", "post_release_drift_detected"): "blocked",
    ("blocked", "step_resumed"): "blocked",
}

BLOCKED_TRANSITIONS: dict[str, set[str]] = {
    state: {target for (src, _event), target in EVENT_TRANSITIONS.items() if src == state and target != state}
    for state in STATES
}


def transition(current: str, event: str) -> str:
    if current not in STATES:
        raise ValueError(f"unknown state: {current}")
    return EVENT_TRANSITIONS.get((current, event), current)


def requires_authorization_for_share(state: str, purpose: str) -> bool:
    return state == "ready" and purpose in {"shareable_anonymous", "shareable_with_attribution"}


def compute_final_state(gates_passed: list[str], authorization_purpose: str) -> str:
    required_for_ready = {"bundle_valid", "extraction_valid", "eval_passed", "scan_complete"}
    passed = set(gates_passed)
    missing = required_for_ready - passed

    if "exact_copy_detected" in gates_passed or "semantic_risk_flagged" in gates_passed:
        return "blocked"
    if "authorization_missing" in gates_passed:
        return "blocked"
    if missing == required_for_ready:
        return "incomplete"
    if missing:
        # Some gate inconclusive or partial: state degrades to limited unless
        # authorization explicitly forbids sharing.
        return "limited" if authorization_purpose != "private_only" else "incomplete"
    if not requires_authorization_for_share("ready", authorization_purpose):
        return "limited"
    return "ready"


__all__ = [
    "STATES",
    "EVENT_TRANSITIONS",
    "BLOCKED_TRANSITIONS",
    "transition",
    "requires_authorization_for_share",
    "compute_final_state",
]