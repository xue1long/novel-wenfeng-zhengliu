"""Stage B Task 4a: sampling coverage matrix.

Spec anchor: §4.2 '抽样覆盖'.

The sampler takes a list of chunk records and assigns each one to a
(scene_class, position) bucket. The matrix is 7 scene classes x 3 positions =
21 target cells. Stage B fixes the scene_class list; extending it requires a
new chunker_version-like bump (Ruling-3).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from chunker import chunk_text  # noqa: E402
from sampling import (  # noqa: E402
    SCENE_CLASSES,
    POSITIONS,
    build_coverage_matrix,
)


class CoverageMatrixShapeTests(unittest.TestCase):
    def test_scene_classes_locked(self):
        self.assertEqual(
            SCENE_CLASSES,
            (
                "opening",
                "character_intro",
                "daily",
                "dialogue",
                "conflict_climax",
                "reveal",
                "chapter_end",
            ),
        )

    def test_positions_locked(self):
        self.assertEqual(POSITIONS, ("front", "middle", "end"))

    def test_matrix_has_all_cells(self):
        text = "第一章\n" + ("这是一段正文。" * 50)
        chunks = chunk_text(text, chunker_version="v1")
        matrix = build_coverage_matrix(chunks, seed=1)
        for klass in SCENE_CLASSES:
            for pos in POSITIONS:
                self.assertIn(klass, matrix.cells)
                self.assertIn(pos, matrix.cells[klass])


class CoverageMatrixDistributionTests(unittest.TestCase):
    def _synthetic_chunks(self, n: int):
        return [
            type("FakeChunk", (), {"chunk_id": f"ck-{i:04d}", "text": f"text {i}", "scene_classes": ()})()
            for i in range(n)
        ]

    def test_front_middle_end_each_have_at_least_one_when_n_large(self):
        chunks = self._synthetic_chunks(60)
        matrix = build_coverage_matrix(chunks, seed=42)
        for klass in SCENE_CLASSES:
            for pos in POSITIONS:
                entry = matrix.cells[klass][pos]
                self.assertTrue(
                    entry["covered"] or entry["chunk_id"] is None,
                    f"cell {klass}/{pos} should be covered or null",
                )

    def test_uncovered_chunks_marked(self):
        chunks = self._synthetic_chunks(2)  # too few to cover all 21 cells
        matrix = build_coverage_matrix(chunks, seed=1)
        uncovered = matrix.uncovered()
        self.assertGreater(len(uncovered), 0)

    def test_same_seed_yields_same_matrix(self):
        chunks = self._synthetic_chunks(30)
        a = build_coverage_matrix(chunks, seed=99)
        b = build_coverage_matrix(chunks, seed=99)
        self.assertEqual(a.cells, b.cells)

    def test_unlabeled_chunks_never_claim_scene_class_coverage(self):
        matrix = build_coverage_matrix(self._synthetic_chunks(60), seed=1)
        self.assertEqual(matrix.uncovered(), [f"{klass}/{pos}" for klass in SCENE_CLASSES for pos in POSITIONS])

    def test_only_matching_scene_class_is_covered(self):
        chunks = self._synthetic_chunks(30)
        chunks[0].scene_classes = ("opening",)
        chunks[10].scene_classes = ("daily",)
        chunks[20].scene_classes = ("chapter_end",)
        matrix = build_coverage_matrix(chunks, seed=1)
        covered = {
            klass
            for klass in SCENE_CLASSES
            if any(entry["covered"] for entry in matrix.cells[klass].values())
        }
        self.assertEqual(covered, {"opening", "daily", "chapter_end"})

    def test_no_chunk_id_repeats_across_cells(self):
        chunks = self._synthetic_chunks(40)
        matrix = build_coverage_matrix(chunks, seed=7)
        seen: dict[str, str] = {}
        for klass in SCENE_CLASSES:
            for pos in POSITIONS:
                cid = matrix.cells[klass][pos]["chunk_id"]
                if cid is None:
                    continue
                self.assertNotIn(cid, seen, f"{cid} reused across cells; existing={seen.get(cid)} new={klass}/{pos}")
                seen[cid] = f"{klass}/{pos}"


if __name__ == "__main__":
    unittest.main()
