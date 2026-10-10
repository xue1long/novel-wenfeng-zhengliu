"""Stage C Task 3a: review prompt templates.

The ``wenfeng-distill`` factory Skill feeds the prompt built by
``build_review_prompt`` to the model. The model MUST respond with strict JSON
whose shape is described in ``review_parser``. Ruling-C6: nothing in this
file or its consumers may solicit user input.
"""

from __future__ import annotations

from typing import Any


REVIEW_PROMPT_VERSION = "wenfeng-review@0.1.0"

REVIEW_RUBRIC = {
    "supported": (
        "Rule is supported by evidence and counterexamples; rule is "
        "executable without source-specific phrasing."
    ),
    "limited": (
        "Rule is partially supported by evidence or counterexamples; "
        "scope must be restricted to the contexts the evidence covers."
    ),
    "unsupported": (
        "Rule is not supported by the cited evidence or counterexamples; "
        "or it embeds source-specific expressions."
    ),
}


def build_review_prompt(
    candidate: dict,
    evidence_refs: list[dict],
    counterexample_refs: list[dict],
    *,
    rubric: dict[str, str] | None = None,
) -> str:
    """Render a deterministic review prompt.

    The factory Skill sends this prompt and expects back the JSON shape
    documented in ``review_parser.parse_review_output``.
    """
    r = rubric if rubric is not None else REVIEW_RUBRIC
    return (
        "You are a writing-style reviewer. Given the candidate below and its "
        "evidence / counterexamples, classify the candidate's review_status as "
        "one of: supported, limited, unsupported.\n"
        f"Rubric:\n  supported: {r['supported']}\n"
        f"  limited: {r['limited']}\n"
        f"  unsupported: {r['unsupported']}\n\n"
        "Respond with strict JSON: "
        "{\"review_status\": <one of>, \"reasons\": [str, ...]}\n\n"
        f"Candidate: {candidate}\n"
        f"Evidence: {evidence_refs}\n"
        f"Counterexamples: {counterexample_refs}\n"
    )


__all__ = ["REVIEW_PROMPT_VERSION", "REVIEW_RUBRIC", "build_review_prompt"]