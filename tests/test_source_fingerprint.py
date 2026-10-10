"""Stage B Task 2: source fingerprint + normalizer.

Spec anchor: §4.1 '来源文件指纹、文件格式、编码、规范化/解析器版本'.

The fingerprint is the SHA-256 of the normalized UTF-8 text. Two runs over
the same source + same parser_version MUST produce the same hex digest.
Changing the parser_version MUST change the digest (that is the only thing
that keeps the chunk manifest + holdout set rebuild honest downstream).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from source_fingerprint import (  # noqa: E402
    fingerprint_bytes,
    fingerprint_text,
    normalize,
    PARSER_VERSION,
)


class NormalizeTests(unittest.TestCase):
    def test_bom_stripped(self):
        text = "\ufeffhello"
        normalized = normalize(text)
        self.assertFalse(normalized.startswith("\ufeff"))
        self.assertEqual(normalized, "hello")

    def test_crlf_to_lf(self):
        text = "line1\r\nline2\r\nline3"
        normalized = normalize(text)
        self.assertEqual(normalized, "line1\nline2\nline3")

    def test_trailing_whitespace_ignored(self):
        text = "hello   \n"
        normalized = normalize(text)
        # rstrip applies per line; the trailing newline is preserved because
        # that is what stage A's chunker relies on for stable offsets.
        self.assertEqual(normalized, "hello\n")

    def test_zero_width_chars_stripped(self):
        text = "ab\u200bcd\u200ce\u200df"
        normalized = normalize(text)
        self.assertEqual(normalized, "abcdef")

    def test_punctuation_and_emoji_preserved(self):
        text = "你好，世界！🌍"
        normalized = normalize(text)
        self.assertEqual(normalized, "你好，世界！🌍")


class FingerprintTests(unittest.TestCase):
    def test_ascii_stable_hex(self):
        self.assertEqual(len(fingerprint_text("abc")), 64)
        # Two consecutive runs of identical input must produce identical hex.
        self.assertEqual(fingerprint_text("abc"), fingerprint_text("abc"))

    def test_cjk_emoji_stable(self):
        self.assertEqual(
            fingerprint_text("你好，世界！🌍"),
            fingerprint_text("你好，世界！🌍"),
        )

    def test_bom_only_difference_ignored(self):
        self.assertEqual(fingerprint_text("\ufeffhello"), fingerprint_text("hello"))

    def test_crlf_ignored(self):
        self.assertEqual(fingerprint_text("a\r\nb"), fingerprint_text("a\nb"))


class FingerprintVersionTests(unittest.TestCase):
    def test_normalizer_version_change_alters_digest(self):
        text = "hello, world!"
        # A different normalizer version string itself is *part of the input
        # context* for the fingerprint pipeline; we hash the (version, text)
        # pair so callers can rely on the rule from §4.2: '来源指纹或规范化
        # /分块器版本变化后，chunk manifest、抽样图和留出集必须重建.'
        v1 = fingerprint_text(text, normalizer_version="v1")
        v1b = fingerprint_text(text, normalizer_version="v1")
        v2 = fingerprint_text(text, normalizer_version="v2")
        self.assertEqual(v1, v1b)
        self.assertNotEqual(v1, v2)

    def test_bytes_fingerprint_independent_of_text_normalizer(self):
        self.assertEqual(len(fingerprint_bytes(b"abc")), 64)
        self.assertNotEqual(fingerprint_bytes(b"abc"), fingerprint_bytes(b"abd"))

    def test_parser_version_constant(self):
        self.assertTrue(PARSER_VERSION.startswith("wenfeng-"))


if __name__ == "__main__":
    unittest.main()