"""Stage B Task 4b: holdout manifest lock.

The lock is a SHA-256 over a stable serialization of:
  - the chunk list (ids + offsets + window_hashes)
  - the coverage matrix seed + chunker_version
  - the chunker_version + normalizer_version
  - the source fingerprint

If any of those change, ``verify_holdout_lock`` returns False and downstream
extraction MUST refuse to run.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from sampling import CoverageMatrix


HOLDOUT_VERSION = "2"


def _lock_payload(
    chunks,
    matrix,
    *,
    fingerprint: str,
    normalizer_version: str,
    chunker_version: str,
    seed: int,
    holdout_chunk_ids: list[str],
) -> bytes:
    chunk_summaries = [
        {
            "chunk_id": c.chunk_id,
            "chapter_id": getattr(c, "chapter_id", ""),
            "scene_id": getattr(c, "scene_id", ""),
            "scene_classes": list(getattr(c, "scene_classes", ())),
            "char_offset": list(c.char_offset),
            "window_hash": c.window_hash,
        }
        for c in chunks
    ]
    payload = {
        "chunker_version": chunker_version,
        "normalizer_version": normalizer_version,
        "holdout_seed": seed,
        "fingerprint": fingerprint,
        "sampling_matrix": matrix.as_dict(),
        "chunks": chunk_summaries,
        "holdout_chunk_ids": holdout_chunk_ids,
    }
    return json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")


def lock_holdout(
    env: dict,
    *,
    holdout_fraction: float,
    seed: int,
    fingerprint: str,
    normalizer_version: str,
    chunker_version: str,
) -> dict[str, Any]:
    if not 0 < holdout_fraction < 1:
        raise ValueError("holdout_fraction must be greater than 0 and less than 1")
    chunks = env["chunks"]
    if not chunks:
        raise ValueError("chunks must not be empty")
    matrix = env["matrix"]
    scene_ids = list(dict.fromkeys(c.scene_id for c in chunks))
    third = max(1, len(scene_ids) // 3)
    middle_scene_ids = scene_ids[third : max(third, len(scene_ids) - third)] or scene_ids
    target = max(1, min(len(middle_scene_ids), int(len(middle_scene_ids) * holdout_fraction)))

    # Deterministic selection by seed.
    salted = hashlib.sha256(
        json.dumps(
            {
                "seed": seed,
                "chunker_version": chunker_version,
                "normalizer_version": normalizer_version,
                "fingerprint": fingerprint,
            },
            sort_keys=True,
        ).encode("utf-8")
    ).digest()
    picked: list[str] = []
    pool = list(middle_scene_ids)
    pool.sort()
    offset = salted[0]
    selected_scenes: set[str] = set()
    for _ in range(target):
        if not pool:
            break
        offset = (offset + salted[1]) % len(pool)
        selected_scenes.add(pool.pop(offset))
    picked = [c.chunk_id for c in chunks if c.scene_id in selected_scenes]

    lock_hash = hashlib.sha256(
        _lock_payload(
            chunks,
            matrix,
            fingerprint=fingerprint,
            normalizer_version=normalizer_version,
            chunker_version=chunker_version,
            seed=seed,
            holdout_chunk_ids=picked,
        )
    ).hexdigest()

    return {
        "holdout_version": HOLDOUT_VERSION,
        "seed": seed,
        "fingerprint": fingerprint,
        "normalizer_version": normalizer_version,
        "chunker_version": chunker_version,
        "holdout_chunk_ids": picked,
        "holdout_lock_hash": lock_hash,
    }


def verify_holdout_lock(env: dict, manifest: dict) -> bool:
    try:
        if manifest.get("holdout_version") != HOLDOUT_VERSION:
            return False
        chunk_ids = {c.chunk_id for c in env["chunks"]}
        holdout_ids = manifest["holdout_chunk_ids"]
        if (
            not isinstance(holdout_ids, list)
            or not holdout_ids
            or len(holdout_ids) != len(set(holdout_ids))
            or not set(holdout_ids).issubset(chunk_ids)
        ):
            return False
        expected = manifest["holdout_lock_hash"]
        actual = hashlib.sha256(
            _lock_payload(
                env["chunks"],
                env["matrix"],
                fingerprint=manifest["fingerprint"],
                normalizer_version=manifest["normalizer_version"],
                chunker_version=manifest["chunker_version"],
                seed=manifest["seed"],
                holdout_chunk_ids=holdout_ids,
            )
        ).hexdigest()
        return expected == actual
    except (KeyError, TypeError, ValueError):
        return False


def read_locked_holdout(run_root: Path) -> dict[str, Any]:
    """Load and verify a persisted holdout against this run's current inputs."""
    run_root = Path(run_root)
    required = {
        "run-config.json": run_root / "run-config.json",
        "chunk-manifest.json": run_root / "chunk-manifest.json",
        "coverage-matrix.json": run_root / "coverage-matrix.json",
        "holdout.json": run_root / "holdout.json",
    }
    missing = [name for name, path in required.items() if not path.is_file()]
    if missing:
        raise ValueError(f"holdout lock inputs missing: {', '.join(missing)}")

    config = json.loads(required["run-config.json"].read_text(encoding="utf-8"))
    chunk_manifest = json.loads(required["chunk-manifest.json"].read_text(encoding="utf-8"))
    matrix_data = json.loads(required["coverage-matrix.json"].read_text(encoding="utf-8"))
    manifest = json.loads(required["holdout.json"].read_text(encoding="utf-8"))
    chunks = [
        SimpleNamespace(
            chunk_id=item["chunk_id"],
            chapter_id=item.get("chapter_id", ""),
            scene_id=item.get("scene_id", ""),
            scene_classes=tuple(item.get("scene_classes", [])),
            char_offset=item["char_offset"],
            window_hash=item["window_hash"],
        )
        for item in chunk_manifest.get("chunks", [])
    ]
    matrix = CoverageMatrix.from_dict(matrix_data)
    fingerprint = config.get("source_fingerprint", "")
    normalizer_version = config.get("normalizer_version", "v1")
    chunker_version = chunk_manifest.get("parser_version", "")
    if (
        not fingerprint
        or manifest.get("fingerprint") != fingerprint
        or manifest.get("normalizer_version") != normalizer_version
        or manifest.get("chunker_version") != chunker_version
        or matrix.chunker_version != chunker_version
    ):
        raise ValueError("holdout lock does not match the current source or versions")
    env = {"chunks": chunks, "matrix": matrix}
    if not verify_holdout_lock(env, manifest):
        raise ValueError("holdout lock hash is invalid or its chunk IDs are stale")
    return manifest


__all__ = ["HOLDOUT_VERSION", "lock_holdout", "verify_holdout_lock", "read_locked_holdout"]
