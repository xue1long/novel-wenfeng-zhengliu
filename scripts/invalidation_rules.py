"""Stage A invalidation rule engine.

Pure functions only. Encodes spec §4.6's invalidation rules:

  - source fingerprint / normalizer version / chunker version changed →
    sampling, holdout, extraction, bundle, compilation, evaluation, release
  - extraction prompt / review model / candidate schema changed →
    extraction, bundle, compilation, evaluation, release
  - bundle / template / compiler changed →
    compilation, evaluation, release
  - scoring model / rubric changed →
    evaluation, release
  - scan model or scan policy changed →
    scan, release
  - increasing scan budget only → completed windows survive; incomplete
    windows get resumed; release is NOT invalidated.
"""

from __future__ import annotations

from enum import Enum


class InvalidationClass(str, Enum):
    SOURCE_FINGERPRINT = "source_fingerprint"
    NORMALIZER_VERSION = "normalizer_version"
    CHUNKER_VERSION = "chunker_version"
    EXTRACTION_PROMPT_VERSION = "extraction_prompt_version"
    REVIEW_MODEL_ID = "review_model_id"
    CANDIDATE_SCHEMA_VERSION = "candidate_schema_version"
    BUNDLE_VERSION = "bundle_version"
    TEMPLATE_VERSION = "template_version"
    COMPILER_VERSION = "compiler_version"
    SCORING_MODEL_ID = "scoring_model_id"
    SCORING_RUBRIC_VERSION = "scoring_rubric_version"
    SCAN_MODEL_ID = "scan_model_id"
    SCAN_POLICY_VERSION = "scan_policy_version"


_DOWNSTREAM = (
    "extraction",
    "bundle",
    "compilation",
    "evaluation",
    "release",
)


_DOWNSTREAM_FROM_SCAN = ("scan", "release")


def _class_to_targets(klass: InvalidationClass) -> tuple[str, ...]:
    if klass in (
        InvalidationClass.SOURCE_FINGERPRINT,
        InvalidationClass.NORMALIZER_VERSION,
        InvalidationClass.CHUNKER_VERSION,
    ):
        return ("sampling", "holdout") + _DOWNSTREAM
    if klass in (
        InvalidationClass.EXTRACTION_PROMPT_VERSION,
        InvalidationClass.REVIEW_MODEL_ID,
        InvalidationClass.CANDIDATE_SCHEMA_VERSION,
    ):
        return _DOWNSTREAM
    if klass in (
        InvalidationClass.BUNDLE_VERSION,
        InvalidationClass.TEMPLATE_VERSION,
        InvalidationClass.COMPILER_VERSION,
    ):
        return ("compilation", "evaluation", "release")
    if klass in (
        InvalidationClass.SCORING_MODEL_ID,
        InvalidationClass.SCORING_RUBRIC_VERSION,
    ):
        return ("evaluation", "release")
    if klass in (
        InvalidationClass.SCAN_MODEL_ID,
        InvalidationClass.SCAN_POLICY_VERSION,
    ):
        return _DOWNSTREAM_FROM_SCAN
    raise ValueError(f"unhandled invalidation class: {klass}")


def compute_invalidation(
    existing_hashes: dict,
    changed_classes: list[InvalidationClass],
    increased_scan_budget: bool,
) -> dict:
    invalidated: set[str] = set()
    for klass in changed_classes:
        invalidated.update(_class_to_targets(klass))

    completed_windows_preserved: list[str] = []
    windows_needing_resume: list[str] = []
    if increased_scan_budget and not invalidated:
        windows = (existing_hashes.get("scan_windows") or {})
        for window_id, payload in windows.items():
            if payload.get("completed"):
                completed_windows_preserved.append(window_id)
            else:
                windows_needing_resume.append(window_id)

    return {
        "invalidated": sorted(invalidated),
        "completed_windows_preserved": completed_windows_preserved,
        "windows_needing_resume": windows_needing_resume,
    }


__all__ = [
    "InvalidationClass",
    "compute_invalidation",
]