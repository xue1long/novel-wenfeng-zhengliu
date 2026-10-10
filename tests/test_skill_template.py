"""Stage D Task 1: six Skill templates + frontmatter parser.

Each Skill template lives at ``templates/stages/<stage_id>.md`` and has:
  - YAML frontmatter with required keys.
  - Markdown body with six required H2 sections.

The parser in ``scripts/skill_template.py`` is stdlib-only (no PyYAML) and
must validate the keys, the stage_id enum, and the body sections.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from skill_template import (  # noqa: E402
    REQUIRED_BODY_SECTIONS,
    REQUIRED_FRONTMATTER_FIELDS,
    SIX_STAGE_IDS,
    TemplateParseError,
    list_stage_templates,
    parse_template,
)


TEMPLATES_ROOT = PROJECT_ROOT / "templates" / "stages"


class TemplateHappyPathTests(unittest.TestCase):
    def test_all_six_templates_parse(self):
        templates = list_stage_templates(TEMPLATES_ROOT)
        self.assertEqual(len(templates), 6, templates)
        for path in templates:
            parsed = parse_template(path)
            self.assertIn(parsed.frontmatter["stage_id"], SIX_STAGE_IDS)
            self.assertEqual(parsed.frontmatter["name"], parsed.frontmatter["stage_id"])

    def test_stage_ids_are_unique(self):
        templates = list_stage_templates(TEMPLATES_ROOT)
        ids = [parse_template(p).frontmatter["stage_id"] for p in templates]
        self.assertEqual(set(ids), set(SIX_STAGE_IDS))
        self.assertEqual(len(ids), len(set(ids)), "duplicate stage_ids")


class TemplateNegativeTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._tmp_path = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _write(self, body: str) -> Path:
        path = self._tmp_path / "bad.md"
        path.write_text(body, encoding="utf-8")
        return path

    def test_missing_frontmatter_rejected(self):
        path = self._write("# Body\n## 触发条件\nx\n")
        with self.assertRaises(TemplateParseError):
            parse_template(path)

    def test_missing_required_field_rejected(self):
        body = (
            "---\n"
            "name: write_entry\n"
            "description: missing stage_id\n"
            "contract_version: 0.1.0\n"
            "trigger_examples: {positive: [a], negative: [b]}\n"
            "required_inputs: [x]\n"
            "primary_output: o\n"
            "missing_input_behavior: block-and-explain\n"
            "stop_conditions: [a]\n"
            "not_allowed: [a]\n"
            "---\n"
            "## 触发条件\nx\n## 必读输入\nx\n## 主要输出\nx\n"
            "## 缺失输入行为\nx\n## 停止条件\nx\n## 不做事项\nx\n"
        )
        bad_path = self._write(body)
        with self.assertRaises(TemplateParseError):
            parse_template(bad_path)

    def test_stage_id_out_of_enum_rejected(self):
        body = (
            "---\n"
            "name: bogus\n"
            "stage_id: epilogue_polish\n"
            "description: d\n"
            "contract_version: 0.1.0\n"
            "trigger_examples: {positive: [a], negative: [b]}\n"
            "required_inputs: [x]\n"
            "primary_output: o\n"
            "missing_input_behavior: block-and-explain\n"
            "stop_conditions: [a]\n"
            "not_allowed: [a]\n"
            "---\n"
            "## 触发条件\nx\n## 必读输入\nx\n## 主要输出\nx\n"
            "## 缺失输入行为\nx\n## 停止条件\nx\n## 不做事项\nx\n"
        )
        bad_path = self._write(body)
        with self.assertRaises(TemplateParseError):
            parse_template(bad_path)

    def test_trigger_examples_must_have_positive_and_negative(self):
        body = (
            "---\n"
            "name: write_entry\n"
            "stage_id: write_entry\n"
            "description: d\n"
            "contract_version: 0.1.0\n"
            "trigger_examples:\n  positive: [a]\n"
            "required_inputs: [x]\n"
            "primary_output: o\n"
            "missing_input_behavior: block-and-explain\n"
            "stop_conditions: [a]\n"
            "not_allowed: [a]\n"
            "---\n"
            "## 触发条件\nx\n## 必读输入\nx\n## 主要输出\nx\n"
            "## 缺失输入行为\nx\n## 停止条件\nx\n## 不做事项\nx\n"
        )
        bad_path = self._write(body)
        with self.assertRaises(TemplateParseError):
            parse_template(bad_path)

    def test_missing_body_section_rejected(self):
        # Drop "必读输入" from the body.
        body = (
            "---\n"
            "name: write_entry\n"
            "stage_id: write_entry\n"
            "description: d\n"
            "contract_version: 0.1.0\n"
            "trigger_examples: {positive: [a], negative: [b]}\n"
            "required_inputs: [x]\n"
            "primary_output: o\n"
            "missing_input_behavior: block-and-explain\n"
            "stop_conditions: [a]\n"
            "not_allowed: [a]\n"
            "---\n"
            "## 触发条件\nx\n## 主要输出\nx\n"
            "## 缺失输入行为\nx\n## 停止条件\nx\n## 不做事项\nx\n"
        )
        bad_path = self._write(body)
        with self.assertRaises(TemplateParseError):
            parse_template(bad_path)


class TemplateSelfContainmentTests(unittest.TestCase):
    def test_no_template_references_another_template_path(self):
        templates = list_stage_templates(TEMPLATES_ROOT)
        for path in templates:
            body = path.read_text(encoding="utf-8")
            self.assertNotIn("templates/stages/", body, msg=path.name)


class TemplateContractAnchorsTests(unittest.TestCase):
    def test_required_frontmatter_fields_documented(self):
        self.assertEqual(
            REQUIRED_FRONTMATTER_FIELDS,
            (
                "name", "description", "stage_id", "contract_version",
                "trigger_examples", "required_inputs", "primary_output",
                "missing_input_behavior", "stop_conditions", "not_allowed",
            ),
        )

    def test_required_body_sections_documented(self):
        self.assertEqual(
            REQUIRED_BODY_SECTIONS,
            (
                "触发条件", "必读输入", "主要输出",
                "缺失输入行为", "停止条件", "不做事项",
            ),
        )


if __name__ == "__main__":
    unittest.main()