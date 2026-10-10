"""Stage C Task 5: Style Bundle compiler.

The compiler takes the list of classified ``MechanismStatus`` records from
``mechanism_merger.classify_mechanism`` and produces a dict that conforms
to Stage A's ``style-bundle.schema.json``. The compiler enforces Ruling-C7
(no source-specific fields), and refuses to emit a Bundle if the mechanism
list is empty (excluded case).

The compiled Bundle is meant to be persisted by the CLI layer
(``scripts/cli_extract.py compile-bundle``) under ``--run-root``.
"""

from __future__ import annotations

import re
from typing import Any

from mechanism_merger import (
    APPROVED,
    EXCLUDED,
    LIMITED,
    MechanismStatus,
    compute_bundle_evidence_status,
)


_FORBIDDEN_FIELDS = {
    "book_name",
    "author_name",
    "character_name",
    "location_name",
    "publisher_name",
    "source_title",
    "original_excerpt",
    "body_excerpt",
    "body",
}

_FIVE_DIMENSIONS = {
    "narrative_voice",
    "sentence_rhythm",
    "scene_transition",
    "dialogue_subtext",
    "imagery_rhetoric",
}

_SIX_STAGES = (
    "write_entry",
    "scene_design",
    "character_beats",
    "prose_draft",
    "style_check",
    "revision",
)

_BUNDLE_EVIDENCE_STATUS = {"pending", "approved", "limited", "unsupported"}


def _semver(value: str) -> str:
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", value):
        raise ValueError(f"bundle_version must be semver X.Y.Z, got {value!r}")
    return value


def _hex12(value: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{12}", value):
        raise ValueError(f"source_id must be 12 lowercase hex, got {value!r}")
    return value


def compile_bundle(
    mechanisms: list[MechanismStatus],
    *,
    source_id: str,
    bundle_version: str,
    bundle_id: str | None = None,
    evaluation_ref: str = "private-ledger://stage-c/evaluation",
) -> dict[str, Any]:
    """Return a Stage-A-compliant Style Bundle dict.

    ``bundle_id`` is auto-derived as ``f"bundle-{source_id}-v{bundle_version}"``
    when not supplied. Callers that already have a stable bundle id (e.g.
    a hash across the source) should pass it explicitly so downstream
    consumers can use the same identifier across all manifests.
    """
    _semver(bundle_version)
    _hex12(source_id)
    if bundle_id is None:
        bundle_id = f"bundle-{source_id}-v{bundle_version}"

    # Source-isolation check (Ruling-C7): refuse any mechanism whose rule or
    # step text contains a forbidden field name as a literal token.
    for m in mechanisms:
        for forbidden in _FORBIDDEN_FIELDS:
            for text in (m.rule, m.forbidden_when, *m.do_steps):
                if forbidden in (text or "").lower().split():
                    raise ValueError(
                        f"mechanism {m.mechanism_id!r} contains source-specific field {forbidden!r}"
                    )

    bundle_status = compute_bundle_evidence_status(mechanisms)
    if bundle_status == EXCLUDED:
        raise ValueError("no mechanism passed the threshold; refusing to compile a Bundle")

    surviving = [m for m in mechanisms if m.bundle_status != EXCLUDED]

    # Map to style-bundle schema: keep only schema-allowed scalars.
    eligible_dimensions = sorted({m.dimension for m in surviving if m.dimension in _FIVE_DIMENSIONS})

    mechanisms_section = []
    for m in surviving:
        mechanisms_section.append({
            "mechanism_id": m.mechanism_id,
            "dimension": m.dimension,
            "rule": m.rule,
            "do_steps": list(m.do_steps),
            "forbidden_when": m.forbidden_when,
            "review_status": m.review_status,
            "stage_bindings": [b for b in m.stage_bindings if b in _SIX_STAGES],
            "evidence_summary": {
                "unique_scenes": m.unique_scenes,
                "unique_chapters": m.unique_chapters,
            },
        })

    # Compute stage_bindings: for each of the six stages, list mechanism_ids
    # bound to it. Empty list is allowed.
    stage_bindings = {stage: [] for stage in _SIX_STAGES}
    for m in surviving:
        for stage in m.stage_bindings:
            if stage in stage_bindings and m.mechanism_id not in stage_bindings[stage]:
                stage_bindings[stage].append(m.mechanism_id)

    # evidence_status field on the bundle mirrors approved/limited; "unsupported"
    # and "pending" are not allowed for ready bundles per schema.
    evidence_status = bundle_status if bundle_status in {"approved", "limited"} else "limited"

    return {
        "schema_version": "2",
        "bundle_version": bundle_version,
        "source_id": source_id,
        "evidence_status": evidence_status,
        "claimed_dimensions": eligible_dimensions,
        "mechanisms": mechanisms_section,
        "stage_bindings": stage_bindings,
        "content_exclusions": [
            "named_character_profiles",
            "verbatim_short_passages",
        ],
        "evaluation_ref": evaluation_ref,
    }


def bundle_contains_no_source_body(bundle: dict) -> bool:
    """Defensive depth-first scan. Catches accidental source-specific keys."""
    forbidden_keys = {"book_name", "author_name", "character_name", "original_excerpt", "body_excerpt", "body"}
    stack: list = [bundle]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            for key, value in node.items():
                if key in forbidden_keys:
                    return False
                stack.append(value)
        elif isinstance(node, list):
            stack.extend(node)
    return True


__all__ = [
    "compile_bundle",
    "bundle_contains_no_source_body",
    "APPROVED",
    "LIMITED",
    "EXCLUDED",
]