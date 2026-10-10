"""Stage B Task 4b: holdout manifest lock.

Spec anchor: §4.2 '预锁留出'.

The holdout set MUST be locked before any extraction step runs. Locking
freezes a SHA-256 hash over (chunk_manifest, sampling_matrix, seed,
chunker_version) so any later change invalidates the lock and forces a
re-lock.
"""

from __future__ import annotations

import sys
import unittest
from types import SimpleNamespace
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from chunker import chunk_text  # noqa: E402
from holdout import lock_holdout, verify_holdout_lock  # noqa: E402
from sampling import build_coverage_matrix  # noqa: E402


def _manifest() -> dict:
    # Use enough sentences to produce > 9 chunks so the middle band is non-empty.
    text = "# 第一章\n" + ("这是一段正文。\n\n这是另一段。" * 20)
    chunks = chunk_text(text, chunker_version="v1")
    matrix = build_coverage_matrix(chunks, seed=1)
    return {"chunks": chunks, "matrix": matrix}


class HoldoutLockTests(unittest.TestCase):
    def test_holdout_lives_in_middle_band(self):
        env = _manifest()
        manifest = lock_holdout(env, holdout_fraction=0.20, seed=1, fingerprint="fp", normalizer_version="v1", chunker_version="v1")
        chunk_index = {c.chunk_id: i for i, c in enumerate(env["chunks"])}
        total = len(env["chunks"])
        third = max(1, total // 3)
        self.assertGreater(total, 2 * third, "manifest needs enough chunks for a non-empty middle band")
        for chunk_id in manifest["holdout_chunk_ids"]:
            idx = chunk_index[chunk_id]
            self.assertGreaterEqual(idx, third, f"{chunk_id} is in front band")
            self.assertLess(idx, total - third, f"{chunk_id} is in end band")

    def test_holdout_fraction_close_to_20_percent(self):
        env = _manifest()
        manifest = lock_holdout(env, holdout_fraction=0.20, seed=1, fingerprint="fp", normalizer_version="v1", chunker_version="v1")
        size = len(manifest["holdout_chunk_ids"])
        total = len(env["chunks"])
        # At least one chunk; <= 20% + 1 slack.
        self.assertGreaterEqual(size, 1)
        self.assertLessEqual(size, max(1, int(total * 0.20) + 1))

    def test_lock_hash_stable(self):
        env = _manifest()
        a = lock_holdout(env, holdout_fraction=0.20, seed=1, fingerprint="fp", normalizer_version="v1", chunker_version="v1")
        b = lock_holdout(env, holdout_fraction=0.20, seed=1, fingerprint="fp", normalizer_version="v1", chunker_version="v1")
        self.assertEqual(a["holdout_lock_hash"], b["holdout_lock_hash"])

    def test_lock_hash_changes_with_chunker_version(self):
        env = _manifest()
        a = lock_holdout(env, holdout_fraction=0.20, seed=1, fingerprint="fp", normalizer_version="v1", chunker_version="v1")
        b = lock_holdout(env, holdout_fraction=0.20, seed=1, fingerprint="fp", normalizer_version="v1", chunker_version="v2")
        self.assertNotEqual(a["holdout_lock_hash"], b["holdout_lock_hash"])

    def test_verify_passes_for_unmodified_inputs(self):
        env = _manifest()
        manifest = lock_holdout(env, holdout_fraction=0.20, seed=1, fingerprint="fp", normalizer_version="v1", chunker_version="v1")
        self.assertTrue(verify_holdout_lock(env, manifest))

    def test_verify_fails_when_chunk_set_changes(self):
        env = _manifest()
        manifest = lock_holdout(env, holdout_fraction=0.20, seed=1, fingerprint="fp", normalizer_version="v1", chunker_version="v1")
        # Mutate the chunk set; verify must fail.
        env["chunks"] = env["chunks"][:-1]
        self.assertFalse(verify_holdout_lock(env, manifest))

    def test_holdout_keeps_every_chunk_from_a_scene_together(self):
        chunks = [SimpleNamespace(
            chunk_id=f"SC{scene:03d}-{window:03d}",
            chapter_id="C001",
            scene_id=f"SC{scene:03d}",
            char_offset=[(scene * 2 + window) * 10, (scene * 2 + window + 1) * 10],
            window_hash=f"{scene * 2 + window:064x}",
            scene_classes=(),
        ) for scene in range(9) for window in range(2)]
        env = {"chunks": chunks, "matrix": build_coverage_matrix(chunks, seed=1)}
        manifest = lock_holdout(
            env, holdout_fraction=0.5, seed=1, fingerprint="fp",
            normalizer_version="v1", chunker_version="v1",
        )
        held_out = set(manifest["holdout_chunk_ids"])
        held_scenes = {chunk.scene_id for chunk in chunks if chunk.chunk_id in held_out}
        for chunk in chunks:
            self.assertEqual(chunk.chunk_id in held_out, chunk.scene_id in held_scenes)

    def test_empty_chunks_rejected(self):
        with self.assertRaisesRegex(ValueError, "chunks must not be empty"):
            lock_holdout(
                {"chunks": [], "matrix": build_coverage_matrix([], seed=1)},
                holdout_fraction=0.2, seed=1, fingerprint="fp",
                normalizer_version="v1", chunker_version="v1",
            )


if __name__ == "__main__":
    unittest.main()
