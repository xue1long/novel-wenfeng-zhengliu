"""Stage C dimension: scene_transition (场景构造与转场)."""

from __future__ import annotations

from .base import EXTRACTION_PROMPT_VERSIONS, extract_dimension


PROMPT_VERSION = EXTRACTION_PROMPT_VERSIONS["scene_transition"]


def extract(normalized_text, chunks, holdout_ids, **kwargs):
    return extract_dimension(
        normalized_text,
        chunks,
        holdout_ids,
        dimension="scene_transition",
        prompt_version=PROMPT_VERSION,
        **kwargs,
    )


__all__ = ["PROMPT_VERSION", "extract"]