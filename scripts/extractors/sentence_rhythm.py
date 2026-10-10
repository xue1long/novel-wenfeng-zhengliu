"""Stage C dimension: sentence_rhythm (句式与段落节奏)."""

from __future__ import annotations

from .base import EXTRACTION_PROMPT_VERSIONS, extract_dimension


PROMPT_VERSION = EXTRACTION_PROMPT_VERSIONS["sentence_rhythm"]


def extract(normalized_text, chunks, holdout_ids, **kwargs):
    return extract_dimension(
        normalized_text,
        chunks,
        holdout_ids,
        dimension="sentence_rhythm",
        prompt_version=PROMPT_VERSION,
        **kwargs,
    )


__all__ = ["PROMPT_VERSION", "extract"]