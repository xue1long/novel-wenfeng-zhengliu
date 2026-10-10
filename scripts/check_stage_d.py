"""Stage D aggregate acceptance gate.

Verifies:
  - Six Skill templates parse cleanly and match the data contract.
  - The six-stage state machine accepts the legal handoff chain and
    rejects every illegal edge from the test plan.
  - Downstream reference invalidation propagates per spec §4.6.

Exit codes:
  0 — PASS
  1 — invariant failure
  2 — IO / subprocess failure
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from six_stage_contract import STAGE_ORDER  # noqa: E402
from six_stage_state_machine import (  # noqa: E402
    IllegalTransitionError,
    RetryExhausted,
    partial_replay_targets,
    validate_retry_count,
    validate_transition,
)
from stage_context_validator import invalidate_stage_context  # noqa: E402
from template_contract_checker import check_all_templates  # noqa: E402


def check_templates_ready() -> list[str]:
    results = check_all_templates(PROJECT_ROOT / "templates" / "stages")
    failures: list[str] = []
    for stage_id in STAGE_ORDER:
        errors = results.get(stage_id, [f"template for {stage_id} missing"])
        failures.extend(f"{stage_id}: {e}" for e in errors)
    return failures


def check_state_machine_legal_and_illegal() -> list[str]:
    """Confirm every legal handoff works and every illegal edge raises."""
    failures: list[str] = []
    chain = [
        ("write_entry", "scene_design"),
        ("scene_design", "character_beats"),
        ("character_beats", "prose_draft"),
        ("prose_draft", "style_check"),
        ("style_check", "revision"),
        ("revision", "completed"),
    ]
    for current, nxt in chain:
        try:
            validate_transition(current, nxt)
        except IllegalTransitionError as exc:
            failures.append(f"expected legal handoff {current} -> {nxt} rejected: {exc}")

    illegal = [
        ("write_entry", "prose_draft"),
        ("completed", "revision"),
        ("character_beats", "prose_draft", "character_beats"),  # return_to == current
        ("character_beats", "prose_draft", "style_check"),       # return_to after current
        ("prose_draft", "style_check", "completed"),              # return_to = terminal
    ]
    for entry in illegal:
        current, nxt = entry[0], entry[1]
        return_to = entry[2] if len(entry) > 2 else None
        try:
            validate_transition(current, nxt, return_to=return_to)
            failures.append(f"illegal handoff {current} -> {nxt} (return_to={return_to}) was accepted")
        except IllegalTransitionError:
            pass

    # Retry count sanity.
    try:
        validate_retry_count(4)
    except RetryExhausted:
        pass
    else:
        failures.append("retry_count 4 should raise RetryExhausted")
    try:
        validate_retry_count(3)
    except RetryExhausted as exc:
        failures.append(f"retry_count 3 should pass, got {exc}")

    # Partial replay.
    targets = partial_replay_targets("character_beats", "prose_draft")
    if targets != ["character_beats", "prose_draft"]:
        failures.append(f"partial_replay_targets mismatch: {targets}")
    return failures


def check_downstream_invalidation() -> list[str]:
    from invalidation_rules import InvalidationClass  # noqa: E402

    failures: list[str] = []
    extraction = invalidate_stage_context({}, InvalidationClass.EXTRACTION_PROMPT_VERSION)
    if "prose_draft" not in extraction:
        failures.append("extraction invalidation should hit prose_draft")
    scan = invalidate_stage_context({}, InvalidationClass.SCAN_POLICY_VERSION)
    if scan:
        failures.append("scan invalidation should not affect writing chain")
    return failures


def main() -> int:
    failures: list[str] = []
    failures.extend(check_templates_ready())
    failures.extend(check_state_machine_legal_and_illegal())
    failures.extend(check_downstream_invalidation())
    if failures:
        print("Stage D aggregate gate FAILED:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("Stage D aggregate gate PASSED:")
    print("- six Skill templates parse and match the data contract")
    print("- six-stage state machine accepts legal handoffs and rejects every illegal edge")
    print("- downstream reference invalidation propagates per spec §4.6")
    print("- templates ready for the wenfeng-distill factory Skill; this gate does NOT validate runtime behavior")
    return 0


if __name__ == "__main__":
    sys.exit(main())
