"""Stage C dimension: imagery_rhetoric (修辞与意象组织)."""

from __future__ import annotations

from .base import EXTRACTION_PROMPT_VERSIONS, extract_dimension


PROMPT_VERSION = EXTRACTION_PROMPT_VERSIONS["imagery_rhetoric"]


def extract(normalized_text, chunks, holdout_ids, **kwargs):
    return extract_dimension(
        normalized_text,
        chunks,
        holdout_ids,
        dimension="imagery_rhetoric",
        prompt_version=PROMPT_VERSION,
        **kwargs,
    )


__all__ = ["PROMPT_VERSION", "extract"]