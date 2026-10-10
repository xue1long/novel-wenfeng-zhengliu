"""Stage C Task 3a tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from review_prompts import (  # noqa: E402
    REVIEW_PROMPT_VERSION,
    REVIEW_RUBRIC,
    build_review_prompt,
)


class ReviewPromptSmokeTests(unittest.TestCase):
    def test_prompt_version_constant(self):
        self.assertEqual(REVIEW_PROMPT_VERSION, "wenfeng-review@0.1.0")

    def test_rubric_has_three_statuses(self):
        self.assertEqual(set(REVIEW_RUBRIC.keys()), {"supported", "limited", "unsupported"})

    def test_build_review_prompt_is_deterministic(self):
        candidate = {"mechanism_id": "M01", "rule": "Apply technique."}
        evidence = [{"chunk_id": "c1"}]
        counter = [{"chunk_id": "c2", "note": "skip"}]
        a = build_review_prompt(candidate, evidence, counter)
        b = build_review_prompt(candidate, evidence, counter)
        self.assertEqual(a, b)
        self.assertIn("supported", a)
        self.assertIn("limited", a)
        self.assertIn("unsupported", a)


if __name__ == "__main__":
    unittest.main()