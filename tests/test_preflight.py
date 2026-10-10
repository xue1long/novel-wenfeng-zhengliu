"""Stage E Task 3 tests."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from preflight import (  # noqa: E402
    preflight_skill,
    preflight_staging_directory,
)


def _good_body(stage_id: str = "scene_design") -> str:
    return (
        "---\n"
        f"name: {stage_id}\n"
        "description: d\n"
        f"stage_id: {stage_id}\n"
        "contract_version: 0.1.0\n"
        "trigger_examples: {positive: [a], negative: [b]}\n"
        "required_inputs: [x]\n"
        "primary_output: o\n"
        "missing_input_behavior: block-and-explain\n"
        "stop_conditions: [a]\n"
        "not_allowed: [a]\n"
        "---\n"
        f"# {stage_id}\n"
        "## 触发条件\nx\n## 必读输入\nx\n## 主要输出\nx\n"
        "## 缺失输入行为\nx\n## 停止条件\nx\n## 不做事项\nx\n"
    )


class SkillPreflightNegativeTests(unittest.TestCase):
    def test_missing_frontmatter_field_rejected(self):
        body = _good_body()
        body = body.replace("contract_version: 0.1.0\n", "")
        errors = preflight_skill("scene_design", body)
        self.assertTrue(any("contract_version" in e for e in errors), errors)

    def test_remote_url_rejected(self):
        body = _good_body()
        body += "\n更多内容 https://example.com/leak\n"
        errors = preflight_skill("scene_design", body)
        self.assertTrue(any("remote URL" in e for e in errors), errors)

    def test_script_tag_rejected(self):
        body = _good_body() + "\n<script>alert(1)</script>\n"
        errors = preflight_skill("scene_design", body)
        self.assertTrue(any("<script>" in e for e in errors), errors)

    def test_project_path_rejected(self):
        body = _good_body() + "\n更多内容 templates/stages/secret.md\n"
        errors = preflight_skill("scene_design", body)
        self.assertTrue(any("templates/" in e or "project-internal" in e for e in errors), errors)


class SkillPreflightHappyPathTests(unittest.TestCase):
    def test_clean_body_passes(self):
        errors = preflight_skill("scene_design", _good_body())
        self.assertEqual(errors, [], errors)


class StagingDirectoryTests(unittest.TestCase):
    def test_matching_declared_files_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "run"
            staging = run_root / "staging"
            staging.mkdir(parents=True)
            (staging / "scene_design").mkdir()
            (staging / "scene_design" / "SKILL.md").write_text(_good_body(), encoding="utf-8")
            (staging / "compile-manifest.json").write_text('{"ok": true}', encoding="utf-8")
            errors = preflight_staging_directory(
                staging,
                declared_files={
                    "scene_design/SKILL.md": "deadbeef",
                    "compile-manifest.json": "feedbeef",
                },
                run_root=run_root,
            )
            self.assertEqual(errors, [], errors)

    def test_undeclared_file_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "run"
            staging = run_root / "staging"
            staging.mkdir(parents=True)
            (staging / "extra.txt").write_text("hi", encoding="utf-8")
            errors = preflight_staging_directory(
                staging,
                declared_files={},
                run_root=run_root,
            )
            self.assertTrue(any("undeclared" in e for e in errors), errors)

    def test_missing_declared_file_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "run"
            staging = run_root / "staging"
            staging.mkdir(parents=True)
            errors = preflight_staging_directory(
                staging,
                declared_files={"scene_design/SKILL.md": "deadbeef"},
                run_root=run_root,
            )
            self.assertTrue(any("missing" in e for e in errors), errors)

    def test_staging_outside_run_root_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "run"
            other = Path(tmp) / "evil"
            other.mkdir()
            errors = preflight_staging_directory(
                other,
                declared_files={},
                run_root=run_root,
            )
            self.assertTrue(any("escapes run_root" in e for e in errors), errors)


class PlaceholderLeakTests(unittest.TestCase):
    def test_leaked_placeholder_rejected(self):
        body = _good_body() + "\nplaceholder {mechanism_ids} here\n"
        errors = preflight_skill("scene_design", body)
        self.assertTrue(any("placeholders" in e or "placeholder" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()