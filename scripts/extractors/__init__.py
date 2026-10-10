"""Stage C extractors.

Five independent method modules that the ``wenfeng-distill`` factory Skill
calls in fixed order. Local stub mode uses ``_stub_model_call`` to keep the
pipeline reproducible without a live model; the production path replaces the
stub wholesale (Ruling-C5).

Public surface (per spec §4.3):
    extract_dimension(normalized_text, chunks, holdout_ids, *, prompt_version)
        -> list[dict]

Each dict must satisfy ``candidate-mechanism.schema.json`` after the
caller has applied evidence validation.
"""

from . import (  # noqa: F401
    dialogue_subtext,
    imagery_rhetoric,
    narrative_voice,
    scene_transition,
    sentence_rhythm,
)
from .base import (  # noqa: F401
    DIMENSION_ORDER,
    EXTRACTION_PROMPT_VERSIONS,
    PROMPT_TEMPLATE_V1,
    StubModelCall,
    _stub_model_call,
    extract_dimension,
)

__all__ = [
    "DIMENSION_ORDER",
    "EXTRACTION_PROMPT_VERSIONS",
    "PROMPT_TEMPLATE_V1",
    "StubModelCall",
    "_stub_model_call",
    "extract_dimension",
]