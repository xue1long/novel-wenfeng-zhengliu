"""Stage D Task 5 tests."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from skill_template import parse_template  # noqa: E402
from template_contract_checker import (  # noqa: E402
    assert_no_template_circular_dep,
    check_all_templates,
    check_template_matches_contract,
)


TEMPLATES_ROOT = PROJECT_ROOT / "templates" / "stages"


class NegativeTests(unittest.TestCase):
    def test_required_inputs_mismatch_rejected(self):
        for path in TEMPLATES_ROOT.glob("*.md"):
            parsed = parse_template(path)
            stage_id = parsed.frontmatter["stage_id"]
            if stage_id == "write_entry":
                # write_entry is the chain head; it is allowed to declare
                # additional entry-level inputs that exist *before* the
                # stage-context. The contract checker skips that check for it.
                continue
            # Mutate to break alignment.
            parsed.frontmatter["required_inputs"] = ["definitely-not-a-key"]
            errors = check_template_matches_contract(parsed)
            self.assertTrue(any("differs from contract" in e for e in errors), (stage_id, errors))

    def test_missing_section_rejected(self):
        for path in TEMPLATES_ROOT.glob("*.md"):
            text = path.read_text(encoding="utf-8")
            # Drop one required section header.
            mutated = text.replace("## 必读输入\n", "")
            with tempfile.TemporaryDirectory() as tmp:
                bad_path = Path(tmp) / path.name
                bad_path.write_text(mutated, encoding="utf-8")
                try:
                    parsed = parse_template(bad_path)
                except Exception:
                    # The skill_template layer already rejects missing sections.
                    continue
                errors = check_template_matches_contract(parsed)
                self.assertTrue(any("missing required body sections" in e for e in errors), errors)

    def test_circular_dep_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            bad_path = tmp_path / "scene_design.md"
            bad_path.write_text(
                "see templates/stages/write_entry.md",
                encoding="utf-8",
            )
            errors = assert_no_template_circular_dep(tmp_path)
            self.assertTrue(any("references another template" in e for e in errors), errors)


class PositiveTests(unittest.TestCase):
    def test_all_six_templates_match_contract(self):
        results = check_all_templates(TEMPLATES_ROOT)
        self.assertEqual(set(results.keys()), {
            "write_entry", "scene_design", "character_beats",
            "prose_draft", "style_check", "revision",
        })
        for stage_id, errors in results.items():
            self.assertEqual(errors, [], f"{stage_id}: {errors}")


class ConstraintMentionTests(unittest.TestCase):
    def test_constraints_are_present_in_body(self):
        results = check_all_templates(TEMPLATES_ROOT)
        for stage_id, errors in results.items():
            constraint_errors = [e for e in errors if "constraint" in e]
            self.assertEqual(constraint_errors, [], f"{stage_id}: {constraint_errors}")


if __name__ == "__main__":
    unittest.main()