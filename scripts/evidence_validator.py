"""Stage C Task 1: evidence offset + hash recompute validator.

Pure stdlib. Spec §4.3: every evidence reference MUST be re-validated
against the chunk manifest by re-deriving its excerpt_hash from the
canonical (chunker_version, char_offset) pair on the normalized text. A
reference that is out of bounds, points at an unknown chunk, or whose
excerpt_hash does not match the recomputation is rejected; downstream
extraction MUST refuse to use it.

Ruling-C4: the hash recipe here is identical to ``chunker._hash_window``
(``sha256(chunker_version || "\\0" || slice)``), so an evidence_ref built
on top of a chunker-produced window hash is self-consistent.
"""

from __future__ import annotations

import hashlib
from typing import Any


def compute_excerpt_hash(
    normalized_text: str,
    char_offset: list[int] | tuple[int, int],
    *,
    chunker_version: str,
) -> str:
    start, end = int(char_offset[0]), int(char_offset[1])
    payload = chunker_version.encode("utf-8") + b"\x00" + normalized_text[start:end].encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _field_error(field_path: str, message: str) -> str:
    return f"{field_path}: {message}"


def validate_evidence_ref(
    ref: Any,
    *,
    chunks: list,
    fingerprint: str,
    normalizer_version: str,
    chunker_version: str = "v1",
    normalized_text: str | None = None,
) -> list[str]:
    """Return a list of error messages; empty list means valid.

    ``normalized_text`` MUST be supplied when the reference is for a slice
    of the original text (most cases). It is intentionally not derived from
    chunks: callers must hand the canonical text to the validator so that a
    re-derived hash cannot be confused with chunker-side cached window hashes.
    """
    errors: list[str] = []
    if not isinstance(ref, dict):
        return ["evidence_ref must be an object"]

    for field in ("chunk_id", "chapter_id", "scene_id", "char_offset", "excerpt_hash"):
        if field not in ref:
            errors.append(_field_error(f"evidence_ref.{field}", "is required"))

    chunk_id = ref.get("chunk_id")
    chapter_id = ref.get("chapter_id")
    scene_id = ref.get("scene_id")
    char_offset = ref.get("char_offset")
    excerpt_hash = ref.get("excerpt_hash")

    if not isinstance(chunk_id, str) or not chunk_id:
        errors.append(_field_error("evidence_ref.chunk_id", "must be a non-empty string"))
    if not isinstance(chapter_id, str) or not chapter_id:
        errors.append(_field_error("evidence_ref.chapter_id", "must be a non-empty string"))
    if not isinstance(scene_id, str) or not scene_id:
        errors.append(_field_error("evidence_ref.scene_id", "must be a non-empty string"))
    if not isinstance(excerpt_hash, str) or len(excerpt_hash) != 64:
        errors.append(_field_error("evidence_ref.excerpt_hash", "must be 64-char hex"))

    if not isinstance(char_offset, list) or len(char_offset) != 2:
        errors.append(_field_error("evidence_ref.char_offset", "must be a [start,end] pair"))
        char_offset = None

    if errors:
        return errors

    start, end = char_offset[0], char_offset[1]
    if not isinstance(start, int) or not isinstance(end, int) or isinstance(start, bool) or isinstance(end, bool):
        errors.append(_field_error("evidence_ref.char_offset", "must contain integers"))
        return errors
    if start >= end:
        errors.append(_field_error("evidence_ref.char_offset", f"start >= end ({start} >= {end})"))
        return errors

    # Find the chunk by chunk_id.
    chunk = next((c for c in chunks if getattr(c, "chunk_id", None) == chunk_id), None)
    if chunk is None:
        errors.append(_field_error("evidence_ref.chunk_id", f"unknown chunk_id {chunk_id!r}"))
        return errors
    if getattr(chunk, "chapter_id", None) != chapter_id:
        errors.append(_field_error(
            "evidence_ref.chapter_id",
            f"chapter {chapter_id!r} does not match chunk {chunk_id!r} (chunk says {getattr(chunk, 'chapter_id', None)!r})",
        ))
    if getattr(chunk, "scene_id", None) != scene_id:
        errors.append(_field_error(
            "evidence_ref.scene_id",
            f"scene {scene_id!r} does not match chunk {chunk_id!r}",
        ))

    chunk_start, chunk_end = chunk.char_offset[0], chunk.char_offset[1]
    if start < chunk_start or end > chunk_end:
        errors.append(_field_error(
            "evidence_ref.char_offset",
            f"[{start},{end}) exceeds chunk [{chunk_start},{chunk_end})",
        ))
        return errors

    if normalized_text is None:
        errors.append(_field_error(
            "evidence_ref",
            "normalized_text must be supplied to recompute excerpt_hash",
        ))
        return errors

    expected_hash = compute_excerpt_hash(
        normalized_text, [start, end], chunker_version=chunker_version
    )
    if expected_hash != excerpt_hash:
        errors.append(_field_error(
            "evidence_ref.excerpt_hash",
            f"hash mismatch: expected {expected_hash[:12]}…, got {excerpt_hash[:12]}…",
        ))

    return errors


def validate_evidence_refs(
    refs: list,
    *,
    chunks: list,
    fingerprint: str,
    normalizer_version: str,
    chunker_version: str = "v1",
    normalized_text: str | None = None,
) -> list[str]:
    """Validate every reference; return all errors with index annotations."""
    all_errors: list[str] = []
    for index, ref in enumerate(refs):
        ref_errors = validate_evidence_ref(
            ref,
            chunks=chunks,
            fingerprint=fingerprint,
            normalizer_version=normalizer_version,
            chunker_version=chunker_version,
            normalized_text=normalized_text,
        )
        for err in ref_errors:
            all_errors.append(f"evidence_refs[{index}].{err}")
    return all_errors


def recompute_ledger_hashes(
    ledger: dict,
    *,
    chunks: list,
    normalizer_version: str,
    chunker_version: str = "v1",
) -> dict[str, dict]:
    """For each ledger entry, recompute the excerpt_hash from its chunk + offset.

    Returns a dict keyed by ``entry_id`` with ``{"ok": bool, "error": str|None}``.
    The function does NOT mutate the ledger. It is the caller's job to decide
    whether to roll forward the recomputed hash into a private ledger field.
    """
    out: dict[str, dict] = {}
    chunk_index = {getattr(c, "chunk_id", None): c for c in chunks}
    for entry in ledger.get("entries", []):
        eid = entry.get("entry_id")
        if not eid:
            continue
        cid = entry.get("chunk_id")
        if cid not in chunk_index:
            out[eid] = {"ok": False, "error": f"chunk_id {cid!r} not found"}
            continue
        offset = entry.get("char_offset", [0, 0])
        if not isinstance(offset, list) or len(offset) != 2:
            out[eid] = {"ok": False, "error": "char_offset must be a [start,end] pair"}
            continue
        # The ledger carries the excerpt body in ``excerpt``. We hash that
        # body together with the chunker_version, mirroring the validator's
        # recipe. This keeps stage C fully self-consistent without reaching
        # back into the (potentially large) normalized_text.
        excerpt = entry.get("excerpt", "")
        if not isinstance(excerpt, str):
            out[eid] = {"ok": False, "error": "excerpt must be a string"}
            continue
        expected = hashlib.sha256(
            chunker_version.encode("utf-8") + b"\x00" + excerpt.encode("utf-8")
        ).hexdigest()
        stored = entry.get("excerpt_hash") or expected
        if stored != expected:
            out[eid] = {
                "ok": False,
                "error": f"excerpt hash mismatch: expected {expected[:12]}… got {stored[:12]}…",
            }
        else:
            out[eid] = {"ok": True, "error": None, "recomputed_excerpt_hash": expected}
    return out


__all__ = [
    "compute_excerpt_hash",
    "validate_evidence_ref",
    "validate_evidence_refs",
    "recompute_ledger_hashes",
]