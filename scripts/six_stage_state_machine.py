"""Stage D Task 3: six-stage state machine.

Wraps the Stage A ``state_machine.compute_final_state`` and adds the
six-stage-specific rules from spec §4.6:

  - legal handoff: write_entry -> scene_design -> character_beats ->
    prose_draft -> style_check -> revision -> completed
  - return_to must point at a stage with index <= current_stage.index
  - retry_count must be in [0, 3]; exceeding 3 raises ``RetryExhausted``
  - non-monotonic retry_count raises ``NonMonotonicRetry``
  - partial replay targets: only ``return_to`` and the stages that depend on it

This module does NOT modify the Stage A state machine; it composes with it.
"""

from __future__ import annotations

from dataclasses import dataclass

from six_stage_contract import STAGE_DATA_CONTRACT, STAGE_ORDER


TERMINAL_STAGE = "completed"


class StateMachineError(Exception):
    def __init__(self, message: str, *, error_type: str = "state_machine_error") -> None:
        super().__init__(message)
        self.error_type = error_type


class IllegalTransitionError(StateMachineError):
    pass


class RetryExhausted(StateMachineError):
    pass


class NonMonotonicRetry(StateMachineError):
    pass


class UnknownStageError(StateMachineError):
    pass


_LEGAL_HANDOFF = {
    "write_entry": {"scene_design", TERMINAL_STAGE},
    "scene_design": {"character_beats", TERMINAL_STAGE},
    "character_beats": {"prose_draft", TERMINAL_STAGE},
    "prose_draft": {"style_check", TERMINAL_STAGE},
    "style_check": {"revision", TERMINAL_STAGE},
    "revision": {TERMINAL_STAGE},
    TERMINAL_STAGE: set(),
}


def _require_known_stage(stage_id: str) -> None:
    if stage_id not in STAGE_ORDER and stage_id != TERMINAL_STAGE:
        raise UnknownStageError(f"unknown stage_id {stage_id!r}")


def stage_index(stage_id: str) -> int:
    _require_known_stage(stage_id)
    if stage_id == TERMINAL_STAGE:
        return len(STAGE_ORDER)
    return STAGE_ORDER.index(stage_id)


def validate_transition(
    current_stage: str,
    next_stage: str,
    *,
    return_to: str | None = None,
) -> None:
    """Validate the next-step move.

    Raises ``IllegalTransitionError`` for any non-legal handoff, including
    cross-stage skips. ``return_to`` must be either ``None`` or a stage
    with index <= ``current_stage.index``.
    """
    _require_known_stage(current_stage)
    _require_known_stage(next_stage)

    legal = _LEGAL_HANDOFF[current_stage]
    if next_stage not in legal:
        raise IllegalTransitionError(
            f"illegal handoff {current_stage!r} -> {next_stage!r}; legal = {sorted(legal)}"
        )

    if return_to is not None:
        _require_known_stage(return_to)
        if return_to == TERMINAL_STAGE:
            raise IllegalTransitionError(
                f"return_to cannot be terminal stage {TERMINAL_STAGE!r}"
            )
        cur_idx = stage_index(current_stage)
        ret_idx = stage_index(return_to)
        if ret_idx >= cur_idx:
            raise IllegalTransitionError(
                f"return_to {return_to!r} must point at a stage before {current_stage!r}"
            )


def validate_retry_count(retry_count: int, *, previous: int | None = None) -> None:
    """Validate the retry_count field of a stage-context.

    ``retry_count`` must be in [0, 3]. When ``previous`` is given, the new
    value must be strictly greater than the previous value.
    """
    if not isinstance(retry_count, int) or isinstance(retry_count, bool):
        raise StateMachineError(f"retry_count must be an int, got {type(retry_count).__name__}")
    if retry_count < 0:
        raise StateMachineError(f"retry_count must be >= 0, got {retry_count}")
    if retry_count > 3:
        raise RetryExhausted(f"retry_count {retry_count} exceeds max 3")
    if previous is not None and retry_count <= previous:
        raise NonMonotonicRetry(
            f"retry_count must increase monotonically: previous={previous}, new={retry_count}"
        )


def partial_replay_targets(return_to: str, current_stage: str) -> list[str]:
    """Return the stages that must be replayed after ``return_to``.

    The list is ``[return_to, *downstream stages up to and including
    current_stage]`` in forward order.
    """
    _require_known_stage(return_to)
    _require_known_stage(current_stage)
    if return_to == TERMINAL_STAGE:
        raise IllegalTransitionError(
            f"return_to cannot be terminal stage {TERMINAL_STAGE!r}"
        )
    ret_idx = stage_index(return_to)
    cur_idx = stage_index(current_stage)
    if ret_idx >= cur_idx:
        raise IllegalTransitionError(
            f"return_to {return_to!r} must point at a stage before {current_stage!r}"
        )
    return [STAGE_ORDER[index] for index in range(ret_idx, cur_idx + 1)]


@dataclass
class IllegalTransitionReport:
    error_type: str
    conflicting_stage: str
    mechanism_id: str
    note: str

    def as_dict(self) -> dict:
        return {
            "error_type": self.error_type,
            "conflicting_stage": self.conflicting_stage,
            "mechanism_id": self.mechanism_id,
            "note": self.note,
        }


def record_illegal_transition(
    trace_id: str,
    from_stage: str,
    to_stage: str,
    *,
    mechanism_id: str = "",
) -> IllegalTransitionReport:
    """Return an error_report dict matching the Stage A stage-context schema."""
    return IllegalTransitionReport(
        error_type="illegal_transition",
        conflicting_stage=from_stage,
        mechanism_id=mechanism_id,
        note=f"illegal handoff {from_stage!r} -> {to_stage!r} for trace {trace_id!r}",
    )


__all__ = [
    "TERMINAL_STAGE",
    "StateMachineError",
    "IllegalTransitionError",
    "RetryExhausted",
    "NonMonotonicRetry",
    "UnknownStageError",
    "IllegalTransitionReport",
    "validate_transition",
    "validate_retry_count",
    "partial_replay_targets",
    "record_illegal_transition",
]