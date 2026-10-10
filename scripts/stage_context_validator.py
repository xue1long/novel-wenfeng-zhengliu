"""Stage D Task 4: stage-context validator + downstream reference invalidation.

Composes the Stage A ``stage-context.schema.json`` with Stage D business
checks:

  - stage_id is one of the six stages or ``completed``.
  - retry_count in [0, 3] and monotonically increasing across calls.
  - stage_snapshot.input_refs / output_refs only reference keys that exist
    in the active bundle.
  - mechanism_id references resolve to an entry in ``bundle.mechanisms``.

Downstream reference invalidation reuses ``scripts/invalidation_rules.py``
to determine which stages must be replayed when an upstream dependency
changes.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

# Local import to avoid touching the Stage A vendored schema until we need it.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "vendor"))
from json_schema_validate import validate as _schema_validate  # noqa: E402

from invalidation_rules import InvalidationClass, compute_invalidation  # noqa: E402
from six_stage_state_machine import (  # noqa: E402
    TERMINAL_STAGE,
    RetryExhausted,
    UnknownStageError,
    validate_retry_count,
    stage_index,
)


SIX_STAGE_IDS = (
    "write_entry",
    "scene_design",
    "character_beats",
    "prose_draft",
    "style_check",
    "revision",
    TERMINAL_STAGE,
)


class StageContextError(Exception):
    def __init__(self, message: str, *, error_type: str = "stage_context_error") -> None:
        super().__init__(message)
        self.error_type = error_type


class StaleMechanismReference(StageContextError):
    pass


class UnknownStageId(StageContextError):
    pass


class MissingInput(StageContextError):
    pass


def _validate_with_schema(context: dict) -> list[str]:
    """Delegate the Stage A schema check."""
    schema = json.loads(
        (PROJECT_ROOT / "schemas" / "stage-context.schema.json").read_text(encoding="utf-8")
    )
    return _schema_validate(context, schema)


def _bundle_mechanism_ids(bundle: dict) -> set[str]:
    return {
        m.get("mechanism_id")
        for m in (bundle.get("mechanisms") or [])
        if isinstance(m, dict) and m.get("mechanism_id")
    }


def validate_stage_context(
    context: dict,
    *,
    bundle: dict | None = None,
    previous_retry_count: int | None = None,
) -> list[str]:
    """Run all Stage A schema + Stage D business checks."""
    errors: list[str] = []
    errors.extend(_validate_with_schema(context))

    stage_id = context.get("stage_id")
    if stage_id not in SIX_STAGE_IDS:
        errors.append(f"stage_id {stage_id!r} not in six-stage enum")
        return errors

    retry_count = context.get("retry_count")
    if not isinstance(retry_count, int) or isinstance(retry_count, bool):
        errors.append(f"retry_count must be int, got {type(retry_count).__name__}")
    else:
        try:
            validate_retry_count(retry_count, previous=previous_retry_count)
        except RetryExhausted as exc:
            errors.append(f"retry_count validation: {exc}")

    snapshot = context.get("stage_snapshot") or {}
    if not isinstance(snapshot, dict):
        errors.append("stage_snapshot must be an object")
        return errors
    changed = snapshot.get("changed_fields")
    if not isinstance(changed, list) or not changed:
        errors.append("stage_snapshot.changed_fields must be a non-empty list")

    if bundle is not None:
        known = _bundle_mechanism_ids(bundle)
        if known:
            for ref_key in ("input_refs", "output_refs"):
                refs = snapshot.get(ref_key) or []
                if not isinstance(refs, list):
                    errors.append(f"stage_snapshot.{ref_key} must be a list")
                    continue
                for index, ref in enumerate(refs):
                    mid = _extract_mechanism_id_from_ref(ref)
                    if mid and mid not in known:
                        errors.append(
                            f"stage_snapshot.{ref_key}[{index}] references "
                            f"unknown mechanism_id {mid!r}"
                        )
    return errors


_MECHANISM_URI_RE = re.compile(r"^bundle://mechanism/(?P<mid>M[0-9]+)$")


def _extract_mechanism_id_from_ref(ref: Any) -> str | None:
    """Pull a mechanism_id out of a stage_snapshot ref.

    Stage D references are strings of the form ``bundle://mechanism/M01``.
    Plain ledger strings (e.g. ``private-ledger://...``) do not carry a
    mechanism_id and return ``None``.
    """
    if not isinstance(ref, str):
        return None
    match = _MECHANISM_URI_RE.match(ref)
    return match.group("mid") if match else None


def raise_stage_context_errors(errors: list[str]) -> None:
    """Convert an error list into typed exceptions for the CLI layer."""
    if not errors:
        return
    for err in errors:
        if "mechanism_id" in err:
            raise StaleMechanismReference(err)
        if "stage_id" in err:
            raise UnknownStageId(err)
        if "retry_count" in err:
            raise RetryExhausted(err)
        if "required field" in err or "missing" in err:
            raise MissingInput(err)
    raise StageContextError("; ".join(errors))


def invalidate_stage_context(
    context: dict,
    invalidation_class: InvalidationClass,
    *,
    all_chunks: list | None = None,
    increased_scan_budget: bool = False,
) -> list[str]:
    """Return the stage_ids that must be replayed because of the invalidation.

    The mapping from invalidation class → stage replay is fixed:

      - ``SCAN_MODEL_ID`` / ``SCAN_POLICY_VERSION`` → no stage replay (content
        scan does not feed the writing chain).
      - ``EXTRACTION_PROMPT`` / ``REVIEW_MODEL`` / ``CANDIDATE_SCHEMA`` / ``BUNDLE``
        / ``TEMPLATE`` / ``COMPILER`` → all stages downstream of style_check
        must re-evaluate.
      - ``SOURCE_FINGERPRINT`` / ``NORMALIZER_VERSION`` / ``CHUNKER_VERSION``
        → the entire chain must replay.

    The function deliberately keeps the mapping human-readable so the
    spec mapping can be inspected without rerunning the system.
    """
    result = compute_invalidation(
        existing_hashes={},
        changed_classes=[invalidation_class],
        increased_scan_budget=increased_scan_budget,
    )
    invalidated = set(result["invalidated"])
    # Map invalidation_rules output → stage ids.
    if "extraction" in invalidated or "bundle" in invalidated:
        invalidated.update({"character_beats", "prose_draft", "style_check", "revision"})
    if "sampling" in invalidated or "holdout" in invalidated:
        invalidated.update(SIX_STAGE_IDS)
    # ``scan`` invalidation does not feed the writing chain; ignore.
    invalidated.discard("scan")
    if invalidated & set(SIX_STAGE_IDS):
        return sorted(invalidated & set(SIX_STAGE_IDS))
    return []


__all__ = [
    "SIX_STAGE_IDS",
    "StageContextError",
    "StaleMechanismReference",
    "UnknownStageId",
    "MissingInput",
    "validate_stage_context",
    "raise_stage_context_errors",
    "invalidate_stage_context",
]