"""Stage G Task 5: package state machine + authorization gate.

Pure stdlib. Decides whether ``package`` may run under a given
``final_state`` / ``authorization_purpose`` combination. Two profiles:

  - ``shareable``: requires ``final_state == "ready"`` AND
    ``authorization_purpose`` in {shareable_anonymous, shareable_with_attribution}.
  - ``private-preview``: requires ``final_state == "limited"``. Blocked
    and incomplete do NOT enter ``dist`` (spec §4.9 last paragraph).

Returns one of:
  - ``allowed``           -- shareable can proceed.
  - ``private-allowed``   -- private-preview can proceed.
  - ``denied``            -- refuse with a reason.

Reuses stage A ``state_machine.compute_final_state`` for downstream
consumers that want to cross-check the gate.
"""

from __future__ import annotations

from enum import Enum
from typing import Iterable

from state_machine import compute_final_state


class PackageProfile(str, Enum):
    SHAREABLE = "shareable"
    PRIVATE_PREVIEW = "private-preview"


SHAREABLE_PURPOSES: frozenset[str] = frozenset({
    "shareable_anonymous",
    "shareable_with_attribution",
})


class PackageGateDecision(str, Enum):
    ALLOWED = "allowed"
    PRIVATE_ALLOWED = "private-allowed"
    DENIED = "denied"


class PackageGateError(Exception):
    def __init__(self, message: str, *, error_type: str = "package_gate_error") -> None:
        super().__init__(message)
        self.error_type = error_type


def evaluate_package_state(
    final_state: str,
    authorization_purpose: str,
    profile: PackageProfile,
) -> PackageGateDecision:
    if profile == PackageProfile.SHAREABLE:
        if final_state == "ready" and authorization_purpose in SHAREABLE_PURPOSES:
            return PackageGateDecision.ALLOWED
        return PackageGateDecision.DENIED
    if profile == PackageProfile.PRIVATE_PREVIEW:
        if final_state == "limited":
            return PackageGateDecision.PRIVATE_ALLOWED
        return PackageGateDecision.DENIED
    return PackageGateDecision.DENIED


def deny_reason(
    final_state: str,
    authorization_purpose: str,
    profile: PackageProfile,
) -> str:
    if profile == PackageProfile.SHAREABLE:
        if final_state != "ready":
            return (
                f"shareable profile requires final_state=ready; got {final_state!r}"
            )
        if authorization_purpose not in SHAREABLE_PURPOSES:
            return (
                f"authorization_purpose {authorization_purpose!r} does not allow sharing; "
                f"need one of {sorted(SHAREABLE_PURPOSES)}"
            )
        return "denied: unknown reason"
    if profile == PackageProfile.PRIVATE_PREVIEW:
        if final_state != "limited":
            return (
                f"private-preview requires final_state=limited; got {final_state!r}"
            )
        return "denied: unknown reason"
    return f"unknown profile {profile!r}"


def assert_decision(
    final_state: str,
    authorization_purpose: str,
    profile: PackageProfile,
) -> PackageGateDecision:
    decision = evaluate_package_state(final_state, authorization_purpose, profile)
    if decision == PackageGateDecision.DENIED:
        raise PackageGateError(
            deny_reason(final_state, authorization_purpose, profile)
        )
    return decision


__all__ = [
    "PackageProfile",
    "SHAREABLE_PURPOSES",
    "PackageGateDecision",
    "PackageGateError",
    "evaluate_package_state",
    "deny_reason",
    "assert_decision",
]