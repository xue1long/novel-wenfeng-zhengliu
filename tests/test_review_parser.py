"""Stage C Task 3b tests."""

from __future__ import annotations

import inspect
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from review_parser import (  # noqa: E402
    ReviewParseError,
    apply_review_to_candidate,
    parse_review_output,
)


class ParseReviewOutputNegativeTests(unittest.TestCase):
    def test_free_text_rejected(self):
        with self.assertRaises(ReviewParseError):
            parse_review_output("I think this rule is fine.")

    def test_unknown_status_rejected(self):
        with self.assertRaises(ReviewParseError):
            parse_review_output('{"review_status": "great", "reasons": ["x"]}')

    def test_empty_reasons_rejected(self):
        with self.assertRaises(ReviewParseError):
            parse_review_output('{"review_status": "supported", "reasons": []}')

    def test_invalid_json_rejected(self):
        with self.assertRaises(ReviewParseError):
            parse_review_output("{not json}")


class ParseReviewOutputHappyPathTests(unittest.TestCase):
    def test_supported(self):
        out = parse_review_output('{"review_status": "supported", "reasons": ["r1", "r2"]}')
        self.assertEqual(out["review_status"], "supported")
        self.assertEqual(out["reasons"], ["r1", "r2"])

    def test_limited(self):
        out = parse_review_output('{"review_status": "limited", "reasons": ["only local"]}')
        self.assertEqual(out["review_status"], "limited")

    def test_unsupported(self):
        out = parse_review_output('{"review_status": "unsupported", "reasons": ["no evidence"]}')
        self.assertEqual(out["review_status"], "unsupported")


class ApplyReviewToCandidateTests(unittest.TestCase):
    def test_merge(self):
        candidate = {"mechanism_id": "M01", "review_status": "pending"}
        out = apply_review_to_candidate(
            candidate, {"review_status": "supported", "reasons": ["r"]}
        )
        self.assertEqual(out["review_status"], "supported")
        self.assertEqual(out["review_reasons"], ["r"])
        # Original not mutated.
        self.assertEqual(candidate["review_status"], "pending")


class ZeroUserInterventionGuardTests(unittest.TestCase):
    def test_parser_source_does_not_call_input_or_prompt(self):
        # Ruling-C6: no interactive prompts in the call chain.
        for path in [
            PROJECT_ROOT / "scripts" / "review_parser.py",
            PROJECT_ROOT / "scripts" / "review_prompts.py",
        ]:
            source = path.read_text(encoding="utf-8")
            self.assertNotIn("input(", source)
            self.assertNotIn("builtins.input", source)
            self.assertNotIn("getpass.", source)


if __name__ == "__main__":
    unittest.main()