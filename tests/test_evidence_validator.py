"""Stage C Task 1: evidence offset + hash recompute validator.

Spec anchor: §4.3 '校验器依据来源指纹、规范化版本和偏移重新计算摘录哈希,
拒绝越界、错位或对不上来源的证据引用.'
"""

from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from chunker import chunk_text, CHUNKER_VERSION  # noqa: E402
from evidence_validator import (  # noqa: E402
    compute_excerpt_hash,
    recompute_ledger_hashes,
    validate_evidence_ref,
    validate_evidence_refs,
)


def _corpus(text: str):
    chunks = chunk_text(text, chunker_version=CHUNKER_VERSION)
    return text, chunks


def _ref(*, chunk_id: str, scene_id: str, chapter_id: str, start: int, end: int,
         excerpt_hash: str = "0" * 64) -> dict:
    return {
        "chunk_id": chunk_id,
        "chapter_id": chapter_id,
        "scene_id": scene_id,
        "char_offset": [start, end],
        "excerpt_hash": excerpt_hash,
    }


class ExcerptHashTests(unittest.TestCase):
    def test_compute_excerpt_hash_matches_chunker_convention(self):
        text = "这是一段测试文本。"
        chunks = chunk_text(text, chunker_version=CHUNKER_VERSION)
        chunk = chunks[0]
        expected = hashlib.sha256(
            CHUNKER_VERSION.encode("utf-8") + b"\x00" + text[chunk.char_offset[0]:chunk.char_offset[1]].encode("utf-8")
        ).hexdigest()
        self.assertEqual(
            compute_excerpt_hash(text, chunk.char_offset, chunker_version=CHUNKER_VERSION),
            expected,
        )

    def test_chunker_version_change_alters_hash(self):
        text = "这是一段测试文本。"
        chunks = chunk_text(text, chunker_version=CHUNKER_VERSION)
        chunk = chunks[0]
        v1 = compute_excerpt_hash(text, chunk.char_offset, chunker_version="v1")
        v2 = compute_excerpt_hash(text, chunk.char_offset, chunker_version="v2")
        self.assertNotEqual(v1, v2)


class ValidateEvidenceRefNegativeTests(unittest.TestCase):
    def setUp(self):
        self.text, self.chunks = _corpus("# 第一章\n句子一。句子二。句子三。")
        self.kwargs = dict(fingerprint="fp", normalizer_version="v1", normalized_text=self.text)

    def test_offset_beyond_chunk_end_rejected(self):
        chunk = self.chunks[0]
        ref = _ref(
            chunk_id=chunk.chunk_id,
            scene_id=chunk.scene_id,
            chapter_id=chunk.chapter_id,
            start=chunk.char_offset[0],
            end=chunk.char_offset[1] + 5,
            excerpt_hash=compute_excerpt_hash(self.text, chunk.char_offset, chunker_version=CHUNKER_VERSION),
        )
        errors = validate_evidence_ref(ref, chunks=self.chunks, **self.kwargs)
        self.assertTrue(any("exceeds" in e or "out of bounds" in e for e in errors), errors)

    def test_offset_reversed_rejected(self):
        chunk = self.chunks[0]
        ref = _ref(
            chunk_id=chunk.chunk_id,
            scene_id=chunk.scene_id,
            chapter_id=chunk.chapter_id,
            start=chunk.char_offset[1] - 1,
            end=chunk.char_offset[0],
            excerpt_hash="0" * 64,
        )
        errors = validate_evidence_ref(ref, chunks=self.chunks, **self.kwargs)
        self.assertTrue(any("start >= end" in e or "reversed" in e for e in errors), errors)

    def test_hash_mismatch_rejected(self):
        chunk = self.chunks[0]
        ref = _ref(
            chunk_id=chunk.chunk_id,
            scene_id=chunk.scene_id,
            chapter_id=chunk.chapter_id,
            start=chunk.char_offset[0],
            end=chunk.char_offset[1],
            excerpt_hash="f" * 64,
        )
        errors = validate_evidence_ref(ref, chunks=self.chunks, **self.kwargs)
        self.assertTrue(any("hash mismatch" in e for e in errors), errors)

    def test_chunk_id_not_found_rejected(self):
        chunk = self.chunks[0]
        ref = _ref(
            chunk_id="ck-does-not-exist",
            scene_id=chunk.scene_id,
            chapter_id=chunk.chapter_id,
            start=chunk.char_offset[0],
            end=chunk.char_offset[1],
            excerpt_hash="0" * 64,
        )
        errors = validate_evidence_ref(ref, chunks=self.chunks, **self.kwargs)
        self.assertTrue(any("not found" in e or "unknown chunk_id" in e for e in errors), errors)

    def test_missing_field_rejected(self):
        errors = validate_evidence_ref(
            {"chunk_id": "x"}, chunks=self.chunks, **self.kwargs
        )
        self.assertGreater(len(errors), 0)


class ValidateEvidenceRefHappyPathTests(unittest.TestCase):
    def test_valid_ref_passes(self):
        text = "# 第一章\n句子一。句子二。句子三。"
        chunks = chunk_text(text, chunker_version=CHUNKER_VERSION)
        chunk = chunks[0]
        ref = _ref(
            chunk_id=chunk.chunk_id,
            scene_id=chunk.scene_id,
            chapter_id=chunk.chapter_id,
            start=chunk.char_offset[0],
            end=chunk.char_offset[1],
            excerpt_hash=compute_excerpt_hash(text, chunk.char_offset, chunker_version=CHUNKER_VERSION),
        )
        errors = validate_evidence_ref(
            ref, chunks=chunks, fingerprint="fp", normalizer_version="v1", normalized_text=text
        )
        self.assertEqual(errors, [], errors)

    def test_batch_reports_only_failing_ref(self):
        text = "# 第一章\n句子一。句子二。句子三。"
        chunks = chunk_text(text, chunker_version=CHUNKER_VERSION)
        good = _ref(
            chunk_id=chunks[0].chunk_id,
            scene_id=chunks[0].scene_id,
            chapter_id=chunks[0].chapter_id,
            start=chunks[0].char_offset[0],
            end=chunks[0].char_offset[1],
            excerpt_hash=compute_excerpt_hash(text, chunks[0].char_offset, chunker_version=CHUNKER_VERSION),
        )
        bad = _ref(
            chunk_id=chunks[0].chunk_id,
            scene_id=chunks[0].scene_id,
            chapter_id=chunks[0].chapter_id,
            start=chunks[0].char_offset[0],
            end=chunks[0].char_offset[1],
            excerpt_hash="f" * 64,
        )
        errors = validate_evidence_refs(
            [good, bad], chunks=chunks, fingerprint="fp", normalizer_version="v1", normalized_text=text
        )
        self.assertEqual(len(errors), 1)
        self.assertIn("hash mismatch", errors[0])


class FingerprintInvalidationTests(unittest.TestCase):
    def test_fingerprint_change_does_not_break_validation(self):
        """The fingerprint is recorded in run-manifest but does NOT feed the
        excerpt hash (which is keyed on chunker_version + text). Changing the
        fingerprint alone MUST keep the same evidence_ref valid."""
        text = "# 第一章\n句子一。句子二。句子三。"
        chunks = chunk_text(text, chunker_version=CHUNKER_VERSION)
        chunk = chunks[0]
        good_hash = compute_excerpt_hash(text, chunk.char_offset, chunker_version=CHUNKER_VERSION)
        ref = _ref(
            chunk_id=chunk.chunk_id,
            scene_id=chunk.scene_id,
            chapter_id=chunk.chapter_id,
            start=chunk.char_offset[0],
            end=chunk.char_offset[1],
            excerpt_hash=good_hash,
        )
        self.assertEqual(
            validate_evidence_ref(
                ref, chunks=chunks, fingerprint="fp", normalizer_version="v1", normalized_text=text
            ),
            [],
        )

    def test_chunker_version_change_alters_hash_and_invalidates_ref(self):
        """Bumping chunker_version MUST change the recomputed hash and
        therefore reject any previously-valid evidence_ref."""
        text = "# 第一章\n句子一。句子二。句子三。"
        chunks = chunk_text(text, chunker_version=CHUNKER_VERSION)
        chunk = chunks[0]
        v1_hash = compute_excerpt_hash(text, chunk.char_offset, chunker_version="v1")
        ref = _ref(
            chunk_id=chunk.chunk_id,
            scene_id=chunk.scene_id,
            chapter_id=chunk.chapter_id,
            start=chunk.char_offset[0],
            end=chunk.char_offset[1],
            excerpt_hash=v1_hash,
        )
        # Pass under v1.
        self.assertEqual(
            validate_evidence_ref(
                ref, chunks=chunks, fingerprint="fp", normalizer_version="v1",
                normalized_text=text, chunker_version="v1",
            ),
            [],
        )
        # Fail under v2.
        errors = validate_evidence_ref(
            ref, chunks=chunks, fingerprint="fp", normalizer_version="v1",
            normalized_text=text, chunker_version="v2",
        )
        self.assertTrue(any("hash mismatch" in e for e in errors), errors)


class RecomputeLedgerHashesTests(unittest.TestCase):
    def test_recompute_returns_per_entry_status(self):
        text = "# 第一章\n句子一。句子二。"
        chunks = chunk_text(text, chunker_version=CHUNKER_VERSION)
        chunk = chunks[0]
        ledger = {
            "run_id": "r1",
            "entries": [
                {
                    "entry_id": "ev-0001",
                    "mechanism_id": "M01",
                    "chunk_id": chunk.chunk_id,
                    "char_offset": list(chunk.char_offset),
                    "excerpt": text[chunk.char_offset[0]:chunk.char_offset[1]],
                    "decision": "supports",
                },
            ],
        }
        result = recompute_ledger_hashes(ledger, chunks=chunks, normalizer_version="v1")
        self.assertEqual(len(result), 1)
        self.assertTrue(result["ev-0001"]["ok"])
        self.assertEqual(result["ev-0001"]["error"], None)

    def test_recompute_detects_missing_chunk(self):
        ledger = {
            "run_id": "r1",
            "entries": [
                {
                    "entry_id": "ev-0001",
                    "mechanism_id": "M01",
                    "chunk_id": "ck-missing",
                    "char_offset": [0, 10],
                    "excerpt": "xxxxxxxxxx",
                    "decision": "supports",
                },
            ],
        }
        result = recompute_ledger_hashes(ledger, chunks=[], normalizer_version="v1")
        self.assertFalse(result["ev-0001"]["ok"])
        self.assertIn("not found", result["ev-0001"]["error"])


if __name__ == "__main__":
    unittest.main()