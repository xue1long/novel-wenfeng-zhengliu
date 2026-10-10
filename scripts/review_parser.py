"""Stage C Task 3b: parse + apply review output.

The factory Skill in ``wenfeng-distill`` calls the model with the prompt
from ``review_prompts.build_review_prompt``. The model returns a string;
this module MUST reject anything that is not strict JSON with the documented
shape (Ruling-C6).
"""

from __future__ import annotations

import ast
import json
from typing import Any


VALID_REVIEW_STATUSES = {"supported", "limited", "unsupported"}


class ReviewParseError(Exception):
    """Raised when a model output cannot be turned into a valid review."""

    def __init__(self, message: str, *, error_type: str = "review_parse_error") -> None:
        super().__init__(message)
        self.error_type = error_type


def parse_review_output(raw: str) -> dict[str, Any]:
    """Parse a strict-JSON review response. Returns ``{review_status, reasons}``.

    Raises ``ReviewParseError`` on any non-conforming input. The factory
    Skill should wrap this in its own retry loop; local scripts treat the
    exception as a hard rejection of the candidate's review step.
    """
    if not isinstance(raw, str):
        raise ReviewParseError("review output must be a string")
    text = raw.strip()
    if not text:
        raise ReviewParseError("review output is empty")
    # First try strict JSON.
    data: Any
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        # Some models wrap JSON in prose; tolerate a single top-level dict if
        # it can be parsed by ast.literal_eval as a fallback.
        try:
            data = ast.literal_eval(text)
        except (ValueError, SyntaxError) as exc2:
            raise ReviewParseError(f"review output is not JSON: {exc}") from exc2
    if not isinstance(data, dict):
        raise ReviewParseError("review output must be a JSON object")
    status = data.get("review_status")
    if status not in VALID_REVIEW_STATUSES:
        raise ReviewParseError(
            f"review_status must be one of {sorted(VALID_REVIEW_STATUSES)}, got {status!r}"
        )
    reasons = data.get("reasons")
    if not isinstance(reasons, list) or not reasons:
        raise ReviewParseError("reasons must be a non-empty list of strings")
    if any(not isinstance(r, str) or not r for r in reasons):
        raise ReviewParseError("each reason must be a non-empty string")
    return {"review_status": status, "reasons": reasons}


def apply_review_to_candidate(
    candidate: dict, parsed_review: dict
) -> dict:
    """Merge a parsed review into a candidate dict. Returns the same dict."""
    candidate = dict(candidate)
    candidate["review_status"] = parsed_review["review_status"]
    candidate["review_reasons"] = list(parsed_review["reasons"])
    return candidate


__all__ = [
    "VALID_REVIEW_STATUSES",
    "ReviewParseError",
    "parse_review_output",
    "apply_review_to_candidate",
]