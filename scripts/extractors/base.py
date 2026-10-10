"""Stage C extractor base + stub model + dimension dispatch.

The five dimension modules (``narrative_voice`` etc.) all register against
this dispatcher. The factory Skill in ``wenfeng-distill`` plugs its real
model call into ``StubModelCall`` and re-uses the same dispatch to obtain
a structured extraction result.

The stub ``_stub_model_call`` is deterministic given its inputs. Tests use
it directly; CLI ``--stub`` mode uses it too. Production callers MUST pass
``StubModelCall`` that wraps a network call.
"""

from __future__ import annotations

import hashlib
from typing import Any, Callable, Iterable

from evidence_validator import compute_excerpt_hash


# Five dimensions, in the fixed order required by spec §4.3.
DIMENSION_ORDER = (
    "narrative_voice",
    "sentence_rhythm",
    "scene_transition",
    "dialogue_subtext",
    "imagery_rhetoric",
)


# Per-dimension prompt version constants. Bumping any value triggers
# invalidation_rules to mark extraction as invalid downstream.
EXTRACTION_PROMPT_VERSIONS = {
    "narrative_voice": "narrative_voice@0.1.0",
    "sentence_rhythm": "sentence_rhythm@0.1.0",
    "scene_transition": "scene_transition@0.1.0",
    "dialogue_subtext": "dialogue_subtext@0.1.0",
    "imagery_rhetoric": "imagery_rhetoric@0.1.0",
}


# Default prompt template. The factory Skill feeds this to the model along
# with the sampled windows; local tests feed the same template to the stub.
PROMPT_TEMPLATE_V1 = (
    "You are a writing-style analyst. Given the source chunks below, "
    "produce 0..3 candidate mechanisms for the dimension '{dimension}'. "
    "Each mechanism MUST cite at least 3 distinct scenes and at least 1 "
    "counterexample. Output strict JSON."
)


# Stage C Test plan Ruling-C (b): default stub returns a MIX of supported /
# limited / unsupported candidates so the end-to-end pipeline lands in
# 'limited' unless a caller explicitly asks for "all supported".
DEFAULT_STUB_PROFILE = "mixed"


StubModelCall = Callable[[str, dict], list[dict]]


def _stub_model_call(prompt: str, inputs: dict) -> list[dict]:
    """Deterministic stub used by tests and ``--stub`` CLI mode.

    The stub does NOT consult ``prompt`` for any decision; it derives its
    behavior from ``inputs["profile"]`` (defaults to ``DEFAULT_STUB_PROFILE``)
    and the chunks passed in. This keeps the stub simple and verifiable.

    Mechanism IDs are dimension-scoped so cross-dimension merging does not
    trigger duplicate detection (which would force every mechanism to
    ``excluded``). Each mechanism cites the first three non-holdout chunks
    so it crosses the approved-scene / approved-chapter thresholds whenever
    the source has at least three distinct scenes / two distinct chapters.
    """
    profile = inputs.get("profile", DEFAULT_STUB_PROFILE)
    chunks = inputs.get("chunks") or []
    if not chunks:
        return []

    profile_to_status = {
        "all_supported": "supported",
        "all_limited": "limited",
        "all_unsupported": "unsupported",
    }

    # Dimension-prefixed mechanism_ids stay unique across dimensions while
    # keeping the candidate-mechanism schema pattern (^M[0-9]{2,}$): the
    # leading "M" is followed by at least two digits, with the dimension
    # encoded as the first 1-2 digits.
    dim = inputs["dimension"]
    dim_to_index = {
        "narrative_voice": 1,
        "sentence_rhythm": 2,
        "scene_transition": 3,
        "dialogue_subtext": 4,
        "imagery_rhetoric": 5,
    }
    dim_index = dim_to_index.get(dim, 9)

    out: list[dict] = []
    chosen = chunks[:3]
    for index, _chunk in enumerate(chosen):
        if profile in profile_to_status:
            review_status = profile_to_status[profile]
        else:  # mixed
            review_status = ("supported", "limited", "unsupported")[index % 3]

        mechanism_id = f"M{dim_index}{index + 1:02d}"
        evidence_refs = []
        counter_refs = []
        for chunk in chosen:
            start, end = chunk.char_offset
            excerpt_hash = compute_excerpt_hash(
                inputs["normalized_text"], [start, end],
                chunker_version=inputs.get("chunker_version", "v1"),
            )
            evidence_refs.append({
                "chunk_id": chunk.chunk_id,
                "chapter_id": chunk.chapter_id,
                "scene_id": chunk.scene_id,
                "char_offset": [start, end],
                "excerpt_hash": excerpt_hash,
            })
            counter_refs.append({
                "chunk_id": chunk.chunk_id,
                "chapter_id": chunk.chapter_id,
                "scene_id": chunk.scene_id,
                "char_offset": [start, end],
                "excerpt_hash": excerpt_hash,
                "note": f"Counterexample for {mechanism_id}",
            })

        candidate: dict[str, Any] = {
            "mechanism_id": mechanism_id,
            "dimension": dim,
            "rule": f"Apply {dim} technique {index + 1} when relevant.",
            "applies_when": "the source presents a matching situation",
            "do_steps": [f"Perform the {behavior} step." for behavior in ("observe", "annotate", "refine")],
            "forbidden_when": "the situation does not match",
            "stage_bindings": ["prose_draft"],
            "evidence_refs": evidence_refs,
            "counterexample_refs": counter_refs,
            "extraction_prompt_version": inputs.get("extraction_prompt_version", ""),
            "review_status": review_status,
        }
        out.append(candidate)
    return out


def extract_dimension(
    normalized_text: str,
    chunks: Iterable,
    holdout_ids: set[str],
    *,
    dimension: str,
    prompt_version: str,
    chunker_version: str = "v1",
    model_call: StubModelCall | None = None,
    profile: str | None = None,
) -> list[dict]:
    """Run a single dimension. Returns candidate dicts.

    ``model_call`` defaults to ``_stub_model_call``. Holdout chunks are
    filtered out before the call so the stub and the factory Skill both
    receive the same non-holdout view of the corpus.
    """
    if dimension not in DIMENSION_ORDER:
        raise ValueError(f"unknown dimension: {dimension!r}")
    chunks = list(chunks)
    eligible = [c for c in chunks if getattr(c, "chunk_id", None) not in holdout_ids]
    inputs = {
        "dimension": dimension,
        "chunks": eligible,
        "normalized_text": normalized_text,
        "chunker_version": chunker_version,
        "extraction_prompt_version": prompt_version,
    }
    if profile is not None:
        inputs["profile"] = profile
    call = model_call or _stub_model_call
    return list(call(PROMPT_TEMPLATE_V1.format(dimension=dimension), inputs))


__all__ = [
    "DIMENSION_ORDER",
    "EXTRACTION_PROMPT_VERSIONS",
    "PROMPT_TEMPLATE_V1",
    "DEFAULT_STUB_PROFILE",
    "StubModelCall",
    "_stub_model_call",
    "extract_dimension",
]