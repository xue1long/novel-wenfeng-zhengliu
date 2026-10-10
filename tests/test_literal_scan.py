"""Stage E Task 4 tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from literal_scan import (  # noqa: E402
    freeze_reference_corpus,
    literal_preflight_scan,
)


class ExactShingleHitTests(unittest.TestCase):
    def test_exact_shingle_hit_detected(self):
        reference = "这是一段用于测试的来源正文，长度足够让 shingle 命中。"
        text = (
            "我们故意把上面这段塞进 Skill：这是一段用于测试的来源正文，长度足够让 shingle 命中。"
            "后面继续写 Skill 内容。"
        )
        frozen = freeze_reference_corpus(reference, shingle_size=12)
        errors = literal_preflight_scan(text, frozen)
        self.assertTrue(any("exact shingle hit" in e for e in errors), errors)

    def test_no_shingle_hit_when_text_differs(self):
        reference = "这是一段用于测试的来源正文。"
        text = "这是另一段完全不同的 Skill 内容，没有任何重叠。"
        frozen = freeze_reference_corpus(reference, shingle_size=12)
        errors = literal_preflight_scan(text, frozen)
        self.assertEqual(errors, [], errors)


class LongContinuousMatchTests(unittest.TestCase):
    def test_long_continuous_match_detected(self):
        # The reference is long enough that exact shingles also fire. We
        # confirm the long-match gate is among the reported errors, which
        # is what the production pipeline cares about.
        reference = "这是一段长达 40 个字符的来源正文用于长段连续匹配测试。"
        text = (
            "Skill 内容："
            + reference
            + " 然后继续写。"
        )
        # min_continuous_match = 20 (smaller than default 32 so the 25-codepoint
        # reference embeds passes the long-match gate as a clean unit test).
        frozen = freeze_reference_corpus(reference, min_continuous_match=20)
        errors = literal_preflight_scan(text, frozen, long_substrings=[reference])
        self.assertTrue(any("long continuous match" in e for e in errors), errors)

    def test_long_match_without_long_substring_arg(self):
        # When the caller does not supply ``long_substrings``, the scan
        # still flags exact-shingle hits as before.
        reference = "这是一段长达 40 个字符的来源正文用于长段连续匹配测试。"
        text = "Skill 内容：" + reference + " 然后继续写。"
        frozen = freeze_reference_corpus(reference, min_continuous_match=20)
        errors = literal_preflight_scan(text, frozen)
        self.assertTrue(any("exact shingle hit" in e for e in errors), errors)

    def test_short_substring_ignored(self):
        # Reference has only 5 codepoints (well below both shingle_size=12
        # and min_continuous_match=32). Even an exact embed passes both
        # gates; the long-match check needs ``long_substrings`` to be
        # supplied explicitly, which we leave empty here.
        reference = "短。"
        text = "Skill 中嵌入：短。继续。"
        frozen = freeze_reference_corpus(reference, min_continuous_match=32)
        errors = literal_preflight_scan(text, frozen, long_substrings=[])
        self.assertEqual(errors, [], errors)

    def test_empty_text_passes(self):
        reference = "任意一段内容"
        frozen = freeze_reference_corpus(reference)
        errors = literal_preflight_scan("", frozen)
        self.assertEqual(errors, [], errors)


class UnicodeHandlingTests(unittest.TestCase):
    def test_emoji_codepoint_alignment(self):
        # Emoji are 1 codepoint each in Python. Shingle over emoji text.
        reference = "🌍🌍🌍🌍🌍🌍🌍🌍🌍🌍🌍🌍这是关于 emoji 的来源参考段落。"
        text = "Skill 中混入：🌍🌍🌍🌍🌍🌍🌍🌍🌍🌍🌍🌍这是关于 emoji 的来源参考段落。继续。"
        frozen = freeze_reference_corpus(reference, shingle_size=12)
        errors = literal_preflight_scan(text, frozen)
        self.assertTrue(any("exact shingle hit" in e for e in errors), errors)


class CleanTextTests(unittest.TestCase):
    def test_clean_skill_text_passes(self):
        # A Skill that talks about sources abstractly but does not quote them.
        reference = "这是一段长 40 个字符的真实来源正文用于匹配测试。"
        text = (
            "# scene_design\n\n"
            "## 触发条件\n"
            "本 Skill 用于设计场景，不引入来源剧情或人物。\n\n"
            "## 必读输入\nuser_brief 与 constraints\n\n"
            "## 主要输出\nscene_plan\n\n"
            "## 缺失输入行为\nblock-and-explain\n\n"
            "## 停止条件\n来源剧情元素出现\n\n"
            "## 不做事项\n不引用来源正文\n"
        )
        frozen = freeze_reference_corpus(reference)
        errors = literal_preflight_scan(text, frozen, long_substrings=[])
        self.assertEqual(errors, [], errors)


class FreezeReferenceTests(unittest.TestCase):
    def test_freeze_validates_shingle_size(self):
        with self.assertRaises(ValueError):
            freeze_reference_corpus("hi", shingle_size=0)


if __name__ == "__main__":
    unittest.main()