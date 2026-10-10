"""Stage B Task 4a: coverage matrix.

Spec anchor: §4.2 '抽样覆盖'.

The matrix has 7 scene classes x 3 positions = 21 cells. Each cell is
either covered by a chunk_id or marked uncovered. The output is a JSON-
serializable ``CoverageMatrix`` so Stage B-T8 CLI can persist it under the
run root.

Ruling-3: extending SCENE_CLASSES or POSITIONS requires a chunker_version-
style bump (the matrix constants live here, but consumers must treat them as
frozen within a single Stage B run).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any


SCENE_CLASSES: tuple[str, ...] = (
    "opening",
    "character_intro",
    "daily",
    "dialogue",
    "conflict_climax",
    "reveal",
    "chapter_end",
)

POSITIONS: tuple[str, ...] = ("front", "middle", "end")


@dataclass
class CoverageMatrix:
    seed: int
    chunker_version: str
    cells: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict)
    uncovered_positions: list[str] = field(default_factory=list)

    def uncovered(self) -> list[str]:
        return list(self.uncovered_positions)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "2",
            "seed": self.seed,
            "chunker_version": self.chunker_version,
            "cells": self.cells,
            "uncovered_positions": self.uncovered_positions,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CoverageMatrix":
        if data.get("schema_version") != "2":
            raise ValueError("unsupported coverage matrix schema_version")
        return cls(
            seed=int(data["seed"]),
            chunker_version=str(data["chunker_version"]),
            cells=dict(data["cells"]),
            uncovered_positions=list(data.get("uncovered_positions", [])),
        )


def _classify_position(index: int, total: int) -> str:
    if total <= 1:
        return "front"
    third = max(1, total // 3)
    if index < third:
        return "front"
    if index >= total - third:
        return "end"
    return "middle"


def _pick_for_cell(chunks, klass: str, position: str, used: set[str], seed: int) -> str | None:
    eligible: list = []
    for index, chunk in enumerate(chunks):
        cid = getattr(chunk, "chunk_id", None)
        if not cid or cid in used:
            continue
        if _classify_position(index, len(chunks)) != position:
            continue
        if klass not in getattr(chunk, "scene_classes", ()):
            continue
        eligible.append(cid)
    if not eligible:
        return None
    # Deterministic pick keyed by (klass, position, seed).
    eligible.sort()
    digest = hashlib.sha256(f"{seed}:{klass}:{position}".encode("utf-8")).digest()
    return eligible[digest[0] % len(eligible)]


def build_coverage_matrix(chunks, *, seed: int, chunker_version: str = "v1") -> CoverageMatrix:
    matrix = CoverageMatrix(seed=seed, chunker_version=chunker_version)
    used: set[str] = set()
    for klass in SCENE_CLASSES:
        matrix.cells[klass] = {}
        for pos in POSITIONS:
            chosen = _pick_for_cell(chunks, klass, pos, used, seed)
            if chosen is None:
                matrix.cells[klass][pos] = {"chunk_id": None, "covered": False}
                matrix.uncovered_positions.append(f"{klass}/{pos}")
            else:
                used.add(chosen)
                matrix.cells[klass][pos] = {"chunk_id": chosen, "covered": True}
    return matrix


__all__ = [
    "SCENE_CLASSES",
    "POSITIONS",
    "CoverageMatrix",
    "build_coverage_matrix",
]
