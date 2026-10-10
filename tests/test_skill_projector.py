"""Stage E Task 2 tests."""

from __future__ import annotations

import re
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from skill_projector import (  # noqa: E402
    PLACEHOLDER_RE,
    project_skill,
)
from skill_template import parse_template  # noqa: E402


SIX_STAGES = (
    "write_entry", "scene_design", "character_beats",
    "prose_draft", "style_check", "revision",
)


def _write_template(tmp: Path, name: str, body: str) -> Path:
    path = tmp / name
    path.write_text(body, encoding="utf-8")
    return path


_TEMPLATE_BODY = (
    "---\n"
    "name: {stage_id}\n"
    "description: d\n"
    "stage_id: {stage_id}\n"
    "contract_version: {contract_version}\n"
    "trigger_examples: {positive: [a], negative: [b]}\n"
    "required_inputs: [x]\n"
    "primary_output: o\n"
    "missing_input_behavior: block-and-explain\n"
    "stop_conditions: [a]\n"
    "not_allowed: [a]\n"
    "---\n"
    "# {stage_id}\n\n"
    "## 触发条件\n"
    "适用 bundle {bundle_id}；使用 {mechanism_ids}；manifest {manifest_version}\n\n"
    "## 必读输入\nx\n"
    "## 主要输出\n"
    "build at {generated_at}\n"
    "## 缺失输入行为\nx\n"
    "## 停止条件\nx\n"
    "## 不做事项\nx\n"
)


class NegativeTests(unittest.TestCase):
    def test_unknown_stage_id_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_template(Path(tmp), "scene_design.md",
                                   _TEMPLATE_BODY.replace("{stage_id}", "scene_design"))
            with self.assertRaises(ValueError):
                project_skill("character_beats", path)

    def test_undeclared_placeholder_rejected(self):
        bad_body = _TEMPLATE_BODY.replace("{stage_id}", "scene_design")
        # Inject a placeholder that is not in the valid set.
        bad_body = bad_body.replace("{generated_at}", "{generated_at}{xyz}")
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_template(Path(tmp), "scene_design.md", bad_body)
            with self.assertRaises(ValueError):
                project_skill("scene_design", path)

    def test_generated_at_renders_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_template(Path(tmp), "scene_design.md",
                                   _TEMPLATE_BODY.replace("{stage_id}", "scene_design"))
            proj = project_skill(
                "scene_design", path,
                contract_version="0.1.0",
                bundle_id="bundle-x",
                manifest_version="0.1.0",
            )
            # No literal "{generated_at}" anywhere in the projected body.
            self.assertNotIn("{generated_at}", proj.body)


class HappyPathTests(unittest.TestCase):
    def test_each_stage_projects_cleanly(self):
        for stage_id in SIX_STAGES:
            with tempfile.TemporaryDirectory() as tmp:
                body = _TEMPLATE_BODY.replace("{stage_id}", stage_id)
                path = _write_template(Path(tmp), f"{stage_id}.md", body)
                proj = project_skill(
                    stage_id, path,
                    mechanism_subset=["M01", "M03", "M02"],
                    bundle_id="bundle-test",
                )
                self.assertEqual(proj.stage_id, stage_id)
                self.assertEqual(proj.file_name, "SKILL.md")
                # Mechanism ids appear sorted.
                self.assertIn("M01, M02, M03", proj.body)
                # Bundle id is substituted.
                self.assertIn("bundle-test", proj.body)
                # No placeholder leaked through.
                for match in PLACEHOLDER_RE.finditer(proj.body):
                    self.fail(f"placeholder leaked: {{{match.group(1)}}}")

    def test_determinism(self):
        body = _TEMPLATE_BODY.replace("{stage_id}", "scene_design")
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_template(Path(tmp), "scene_design.md", body)
            args = dict(
                mechanism_subset=["M10", "M20"],
                contract_version="0.1.0",
                bundle_id="bundle-x",
                manifest_version="0.1.0",
            )
            a = project_skill("scene_design", path, **args)
            b = project_skill("scene_design", path, **args)
            self.assertEqual(a.body, b.body)


class RealTemplatesTests(unittest.TestCase):
    def test_real_six_templates_have_no_placeholders(self):
        """Stage E ships templates without placeholders; projection should be
        a near-identity pass-through. We assert that the projected body equals
        the original body exactly so this remains deterministic."""
        templates = PROJECT_ROOT / "templates" / "stages"
        for stage_id in SIX_STAGES:
            path = templates / f"{stage_id}.md"
            parsed = parse_template(path)
            proj = project_skill(stage_id, path)
            self.assertEqual(proj.body, parsed.body)


if __name__ == "__main__":
    unittest.main()