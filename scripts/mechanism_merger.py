"""Stage C Task 4: candidate dedup + mechanism counting + status merging.

Spec anchor: §4.3 第 4 步'规则引擎合并模型复核结果与机械证据门槛'.

The function ``classify_mechanism`` returns a list of ``MechanismStatus``
records. Each record carries the evidence summary the Bundle compiler will
need; the Bundle itself stays schema-clean (no body text, no source names).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


SUPPORTED = "supported"
LIMITED = "limited"
UNSUPPORTED = "unsupported"

# Per-dimension approved thresholds (spec §4.3).
APPROVED_MIN_UNIQUE_SCENES = 3
APPROVED_MIN_UNIQUE_CHAPTERS = 2
LIMITED_MIN_UNIQUE_SCENES = 2

# Resulting bundle_status.
APPROVED = "approved"
EXCLUDED = "excluded"


@dataclass
class MechanismStatus:
    mechanism_id: str
    dimension: str
    rule: str
    do_steps: list[str]
    forbidden_when: str
    stage_bindings: list[str]
    review_status: str
    unique_scenes: int
    unique_chapters: int
    counterexample_count: int
    evidence_refs: list[dict] = field(default_factory=list)
    counterexample_refs: list[dict] = field(default_factory=list)
    extraction_prompt_version: str = ""
    bundle_status: str = EXCLUDED
    reasons: list[str] = field(default_factory=list)


def _normalize_rule(rule: str) -> str:
    return " ".join(rule.split())


def _normalize_steps(steps: list[str]) -> tuple[str, ...]:
    return tuple(" ".join(s.split()) for s in steps)


def _dedupe_candidates(candidates: list[dict]) -> list[dict]:
    """Collapse candidates that share the same (normalized_rule, normalized_do_steps).

    Same key + same do_steps → merge refs into the first occurrence.
    Same key + different do_steps → mark both as conflicting; do not merge.
    Different keys → keep separately.
    """
    by_key: dict[tuple[str, tuple[str, ...]], dict] = {}
    for candidate in candidates:
        key = (_normalize_rule(candidate.get("rule", "")), _normalize_steps(candidate.get("do_steps", [])))
        if key in by_key:
            existing = by_key[key]
            existing_steps = _normalize_steps(existing.get("do_steps", []))
            new_steps = _normalize_steps(candidate.get("do_steps", []))
            if set(existing_steps) != set(new_steps):
                # Same rule, different do_steps → conflict; keep both flagged.
                candidate = dict(candidate)
                candidate["_conflict_with"] = existing.get("mechanism_id")
                existing["_conflict_with"] = candidate.get("mechanism_id")
                by_key[f"__conflict_{candidate.get('mechanism_id', id(candidate))}__"] = candidate
                continue
            for ref in candidate.get("evidence_refs", []):
                if ref not in existing["evidence_refs"]:
                    existing["evidence_refs"].append(ref)
            for ref in candidate.get("counterexample_refs", []):
                if ref not in existing["counterexample_refs"]:
                    existing["counterexample_refs"].append(ref)
        else:
            by_key[key] = {
                "mechanism_id": candidate.get("mechanism_id"),
                "dimension": candidate.get("dimension"),
                "rule": candidate.get("rule", ""),
                "do_steps": list(candidate.get("do_steps", [])),
                "forbidden_when": candidate.get("forbidden_when", ""),
                "stage_bindings": list(candidate.get("stage_bindings", [])),
                "evidence_refs": list(candidate.get("evidence_refs", [])),
                "counterexample_refs": list(candidate.get("counterexample_refs", [])),
                "extraction_prompt_version": candidate.get("extraction_prompt_version", ""),
                "review_status": candidate.get("review_status", UNSUPPORTED),
            }
    return list(by_key.values())


def _detect_chunk_conflicts(candidates: list[dict]) -> dict[str, list[str]]:
    """If two candidates share an evidence chunk_id but differ on the leading
    verb of any do_step, record each as conflicting with the other.

    Returns ``{mechanism_id: [other_mechanism_id, ...]}``.
    """
    by_chunk: dict[str, list[tuple[str, list[str]]]] = {}
    for candidate in candidates:
        for ref in candidate.get("evidence_refs", []):
            cid = ref.get("chunk_id")
            if cid:
                by_chunk.setdefault(cid, []).append(
                    (candidate.get("mechanism_id", "?"), candidate.get("do_steps", []))
                )
    conflicts: dict[str, set[str]] = {}
    for cid, entries in by_chunk.items():
        # Use the first verb of each do_step as a coarse conflict signal.
        signatures = {
            mid: tuple(step.split(" ", 1)[0].strip().lower() for step in steps if step)
            for mid, steps in entries
        }
        mids = list(signatures.keys())
        for i in range(len(mids)):
            for j in range(i + 1, len(mids)):
                if signatures[mids[i]] != signatures[mids[j]]:
                    conflicts.setdefault(mids[i], set()).add(mids[j])
                    conflicts.setdefault(mids[j], set()).add(mids[i])
    return {mid: sorted(values) for mid, values in conflicts.items()}


def _classify_one(candidate: dict, *, seen_mechanism_ids: set[str], chunk_conflicts: dict[str, list[str]]) -> MechanismStatus:
    reasons: list[str] = []
    scenes = {ref.get("scene_id") for ref in candidate.get("evidence_refs", []) if ref.get("scene_id")}
    chapters = {ref.get("chapter_id") for ref in candidate.get("evidence_refs", []) if ref.get("chapter_id")}
    counter_count = len(candidate.get("counterexample_refs", []))

    mid = candidate.get("mechanism_id", "")
    if mid in seen_mechanism_ids:
        reasons.append(f"duplicate mechanism_id {mid!r}")
    seen_mechanism_ids.add(mid)

    if counter_count == 0:
        reasons.append("no counterexamples")
    review_status = candidate.get("review_status", UNSUPPORTED)
    if review_status == UNSUPPORTED:
        reasons.append("review_status=unsupported")

    conflicts = candidate.get("_conflict_with") or None
    if not conflicts:
        chunk_conflict = chunk_conflicts.get(mid) or []
        if chunk_conflict:
            conflicts = chunk_conflict
    if conflicts:
        reasons.append(f"conflicts with mechanisms: {sorted(set(conflicts))}")

    status = EXCLUDED
    if (
        mid
        and counter_count > 0
        and review_status == SUPPORTED
        and len(scenes) >= APPROVED_MIN_UNIQUE_SCENES
        and len(chapters) >= APPROVED_MIN_UNIQUE_CHAPTERS
        and not conflicts
    ):
        status = APPROVED
    elif (
        mid
        and counter_count > 0
        and review_status in {SUPPORTED, LIMITED}
        and len(scenes) >= LIMITED_MIN_UNIQUE_SCENES
        and not conflicts
    ):
        status = LIMITED

    return MechanismStatus(
        mechanism_id=mid,
        dimension=candidate.get("dimension", ""),
        rule=candidate.get("rule", ""),
        do_steps=list(candidate.get("do_steps", [])),
        forbidden_when=candidate.get("forbidden_when", ""),
        stage_bindings=list(candidate.get("stage_bindings", [])),
        review_status=review_status,
        unique_scenes=len(scenes),
        unique_chapters=len(chapters),
        counterexample_count=counter_count,
        evidence_refs=list(candidate.get("evidence_refs", [])),
        counterexample_refs=list(candidate.get("counterexample_refs", [])),
        extraction_prompt_version=candidate.get("extraction_prompt_version", ""),
        bundle_status=status,
        reasons=reasons,
    )


def classify_mechanism(candidates: list[dict]) -> list[MechanismStatus]:
    """Run dedup, detect chunk-level conflicts, then classify each candidate."""
    deduped = _dedupe_candidates(candidates)
    chunk_conflicts = _detect_chunk_conflicts(deduped)
    seen: set[str] = set()
    return [
        _classify_one(c, seen_mechanism_ids=seen, chunk_conflicts=chunk_conflicts)
        for c in deduped
    ]


def compute_bundle_evidence_status(mechanisms: list[MechanismStatus]) -> str:
    """Spec §4.3 第 4 步: 5 维度全 approved 才 ready; 否则 limited; 无任何通过 excluded."""
    if not mechanisms:
        return EXCLUDED
    if any(m.bundle_status == APPROVED for m in mechanisms):
        return APPROVED
    if any(m.bundle_status == LIMITED for m in mechanisms):
        return LIMITED
    return EXCLUDED


__all__ = [
    "MechanismStatus",
    "classify_mechanism",
    "compute_bundle_evidence_status",
    "APPROVED",
    "LIMITED",
    "EXCLUDED",
]