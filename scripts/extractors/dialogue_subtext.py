"""Stage C dimension: dialogue_subtext (对白与潜台词)."""

from __future__ import annotations

from .base import EXTRACTION_PROMPT_VERSIONS, extract_dimension


PROMPT_VERSION = EXTRACTION_PROMPT_VERSIONS["dialogue_subtext"]


def extract(normalized_text, chunks, holdout_ids, **kwargs):
    return extract_dimension(
        normalized_text,
        chunks,
        holdout_ids,
        dimension="dialogue_subtext",
        prompt_version=PROMPT_VERSION,
        **kwargs,
    )


__all__ = ["PROMPT_VERSION", "extract"]