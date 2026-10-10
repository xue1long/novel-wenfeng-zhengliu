"""Stage C dimension: narrative_voice (叙述视角与叙述者口吻)."""

from __future__ import annotations

from .base import EXTRACTION_PROMPT_VERSIONS, extract_dimension


PROMPT_VERSION = EXTRACTION_PROMPT_VERSIONS["narrative_voice"]


def extract(normalized_text, chunks, holdout_ids, **kwargs):
    return extract_dimension(
        normalized_text,
        chunks,
        holdout_ids,
        dimension="narrative_voice",
        prompt_version=PROMPT_VERSION,
        **kwargs,
    )


__all__ = ["PROMPT_VERSION", "extract"]