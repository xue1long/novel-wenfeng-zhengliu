"""Stage B Task 3: stable chunker.

Spec anchor: §4.2 '稳定分块器'.

The chunker is a pure function over normalized text. Two calls with the
same (text, chunker_version) MUST produce identical chunk_id / char_offset /
window_hash / boundary_confidence. Bumping chunker_version MUST change them.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from chunker import chunk_text, CHUNKER_VERSION  # noqa: E402


def _flat(chunks) -> list[dict]:
    return [
        {
            "chunk_id": c.chunk_id,
            "chapter_id": c.chapter_id,
            "scene_id": c.scene_id,
            "char_offset": list(c.char_offset),
            "window_hash": c.window_hash,
            "boundary_confidence": c.boundary_confidence,
        }
        for c in chunks
    ]


class ChunkerHappyPathTests(unittest.TestCase):
    def test_single_chapter_single_window(self):
        text = "第一段。\n第二段。\n第三段。"
        chunks = chunk_text(text, chunker_version=CHUNKER_VERSION)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].chapter_id, "C000")
        self.assertEqual(chunks[0].scene_id, "SC0001")
        self.assertEqual(chunks[0].boundary_confidence, "high")
        self.assertEqual(chunks[0].char_offset[0], 0)
        self.assertGreater(chunks[0].char_offset[1], 0)

    def test_markdown_heading_splits_chapter(self):
        text = "# 第一章\n正文1。\n# 第二章\n正文2。"
        chunks = chunk_text(text, chunker_version=CHUNKER_VERSION)
        chapters = {c.chapter_id for c in chunks}
        self.assertIn("C001", chapters)
        self.assertIn("C002", chapters)

    def test_chapter_pattern_chinese(self):
        text = "第一章 开端\n正文。\n第二章 发展\n正文。"
        chunks = chunk_text(text, chunker_version=CHUNKER_VERSION)
        chapters = {c.chapter_id for c in chunks}
        self.assertIn("C001", chapters)
        self.assertIn("C002", chapters)

    def test_chapter_pattern_english(self):
        text = "Chapter 1\nBody. \nChapter 2\nBody."
        chunks = chunk_text(text, chunker_version=CHUNKER_VERSION)
        chapters = {c.chapter_id for c in chunks}
        self.assertIn("C001", chapters)
        self.assertIn("C002", chapters)


class ChunkerNoMidSentenceCutTests(unittest.TestCase):
    def test_no_split_mid_sentence_when_under_limit(self):
        # Two sentences totaling ~10 codepoints; well under 5000.
        text = "句一。句二。"
        chunks = chunk_text(text, chunker_version=CHUNKER_VERSION)
        self.assertEqual(len(chunks), 1)
        chunk_text_ = chunks[0].text  # in-memory only; see chunker docstring
        self.assertEqual(chunk_text_, text)

    def test_split_at_sentence_boundary_over_limit(self):
        # Build a > 5000-codepoint text composed of short sentences separated by
        # full-width periods and a single ASCII space (the chunker's sentence
        # boundary regex requires whitespace after the terminator).
        sentence = "这是一句用于测试的文本，长度可控。 "  # ~16 codepoints
        text = "# 第一章\n" + sentence * 500  # ~8000 codepoints
        chunks = chunk_text(text, chunker_version=CHUNKER_VERSION)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            for c in chunk.text:
                self.assertNotEqual(c, "\uFFFD")
            # Every window ends with a sentence terminator OR boundary_confidence=low.
            last_char = chunk.text.rstrip()[-1]
            if chunk.boundary_confidence != "low":
                self.assertIn(last_char, "。！？!?….")


class ChunkerStabilityTests(unittest.TestCase):
    def test_idempotent_with_same_version(self):
        text = "# 第一章\n内容。\n# 第二章\n更多内容。" * 10
        a = _flat(chunk_text(text, chunker_version=CHUNKER_VERSION))
        b = _flat(chunk_text(text, chunker_version=CHUNKER_VERSION))
        self.assertEqual(a, b)

    def test_chunker_version_change_alters_chunks(self):
        text = "# 第一章\n内容。"
        v1 = _flat(chunk_text(text, chunker_version="v1"))
        v2 = _flat(chunk_text(text, chunker_version="v2"))
        self.assertNotEqual(v1, v2)

    def test_chunk_ids_unique_within_document(self):
        text = "# 第一章\n内容。\n# 第二章\n内容。\n# 第三章\n内容。"
        chunks = chunk_text(text, chunker_version=CHUNKER_VERSION)
        ids = [c.chunk_id for c in chunks]
        self.assertEqual(len(ids), len(set(ids)))


class ChunkerLongChapterTests(unittest.TestCase):
    def test_long_chapter_splits_at_sentence_boundary(self):
        sentence = "这是用于压测的长句。 "  # ~10 codepoints
        text = "# 第一章\n" + (sentence * 600)  # ~6000 codepoints
        chunks = chunk_text(text, chunker_version=CHUNKER_VERSION)
        self.assertGreaterEqual(len(chunks), 2)
        chapter_ids = {c.chapter_id for c in chunks}
        self.assertEqual(chapter_ids, {"C001"})

    def test_long_chapter_low_confidence_when_no_terminator(self):
        # A single "word" longer than 5000 codepoints with no punctuation at all.
        text = "第一章\n" + ("x" * 5500)
        chunks = chunk_text(text, chunker_version=CHUNKER_VERSION)
        # We must produce at least one window whose boundary_confidence is "low"
        # because there is no sentence terminator.
        self.assertTrue(any(c.boundary_confidence == "low" for c in chunks))


if __name__ == "__main__":
    unittest.main()