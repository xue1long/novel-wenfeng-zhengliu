"""Stage G Task 1 tests."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from final_source_scan import (  # noqa: E402
    SourceScanError,
    SourceScanPolicy,
    evaluate_scan_coverage,
    final_source_scan,
    write_scan_report,
)


def _make_staging(staging: Path, *, with_report: bool = True) -> None:
    staging.mkdir(parents=True, exist_ok=True)
    for stage_id in (
        "write_entry", "scene_design", "character_beats",
        "prose_draft", "style_check", "revision",
    ):
        (staging / stage_id).mkdir(exist_ok=True)
        (staging / stage_id / "SKILL.md").write_text(
            f"# {stage_id}\n\n本 Skill 用于设计阶段输出，不引入来源剧情或人物。\n",
            encoding="utf-8",
        )
    if with_report:
        (staging / "eval-report.json").write_text(json.dumps({
            "report_version": "0.1.0",
            "bundle_id": "bundle-x-v0_1_0",
            "gate_results": {
                "trigger": {"precision": 1.0, "recall": 1.0, "passed": True},
                "output": {"mechanical_pass_rate": 1.0, "passed": True},
                "end_to_end": {"verdict": "pass", "winning_pairs": 6,
                                "style_fit_median": 4.5, "pairing_median_delta": 1.5,
                                "quality_median_delta": 0.0, "undetermined_dimensions": [],
                                "passed": True},
            },
            "summary": {"final_state": "ready", "notes": ""},
        }), encoding="utf-8")


class HappyPathTests(unittest.TestCase):
    def test_clean_staging_passes_with_default_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            staging = Path(tmp) / "staging"
            _make_staging(staging)
            scan = final_source_scan(staging, SourceScanPolicy.default())
            self.assertEqual(scan["coverage_ratio"], 1.0)
            self.assertEqual(scan["covered_targets"], 7)
            errors = evaluate_scan_coverage(scan)
            self.assertEqual(errors, [], errors)

    def test_partial_coverage_passes_when_target_below_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            staging = Path(tmp) / "staging"
            _make_staging(staging)
            # Budget 50 codepoints: only the first SKILL.md (47 chars) fits
            # under the budget. coverage_ratio ~= 0.066 so a target of
            # 0.05 is comfortably satisfied.
            policy = SourceScanPolicy(policy_version="0.1.0", total_budget_codepoints=50,
                                      coverage_target=0.05)
            scan = final_source_scan(staging, policy)
            self.assertEqual(scan["policy"]["total_budget_codepoints"], 50)
            self.assertLess(scan["coverage_ratio"], 1.0)
            errors = evaluate_scan_coverage(scan)
            for err in errors:
                if "coverage" in err:
                    self.fail(f"coverage check failed unexpectedly: {errors}")

    def test_determinism_same_input_same_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            staging = Path(tmp) / "staging"
            _make_staging(staging)
            scan1 = final_source_scan(staging, SourceScanPolicy.default())
            scan2 = final_source_scan(staging, SourceScanPolicy.default())
            self.assertEqual(scan1["hashes"], scan2["hashes"])
            self.assertEqual(scan1["scanned_at_marker"], "")


class NegativeTests(unittest.TestCase):
    def test_coverage_below_target_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            staging = Path(tmp) / "staging"
            _make_staging(staging)
            policy = SourceScanPolicy(policy_version="0.1.0", total_budget_codepoints=10,
                                      coverage_target=1.0)
            scan = final_source_scan(staging, policy)
            errors = evaluate_scan_coverage(scan)
            self.assertTrue(any("coverage" in e for e in errors), errors)

    def test_shingle_size_zero_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            staging = Path(tmp) / "staging"
            _make_staging(staging)
            with self.assertRaises(SourceScanError):
                final_source_scan(staging, SourceScanPolicy(policy_version="0.1.0", shingle_size=0))

    def test_coverage_target_out_of_range_rejected(self):
        with self.assertRaises(SourceScanError):
            SourceScanPolicy(policy_version="0.1.0", coverage_target=1.5)

    def test_missing_skill_md_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            staging = Path(tmp) / "staging"
            _make_staging(staging, with_report=False)
            # Remove one SKILL.md.
            (staging / "scene_design" / "SKILL.md").unlink()
            scan = final_source_scan(staging, SourceScanPolicy.default())
            errors = evaluate_scan_coverage(scan)
            self.assertTrue(any("missing" in e for e in errors), errors)

    def test_exact_shingle_hit_blocks_scan(self):
        with tempfile.TemporaryDirectory() as tmp:
            staging = Path(tmp) / "staging"
            _make_staging(staging)
            # Inject a verbatim copy of the reference into a SKILL.md.
            reference = "这是一段长达 40 个字符的来源正文用于字面预检端到端测试。"
            (staging / "prose_draft" / "SKILL.md").write_text(
                f"# prose_draft\n\n## 来源副本\n{reference}\n",
                encoding="utf-8",
            )
            scan = final_source_scan(
                staging, SourceScanPolicy.default(),
                reference_corpus=reference,
                long_substrings=[reference],
            )
            errors = evaluate_scan_coverage(scan)
            self.assertTrue(any("prose_draft" in e for e in errors), errors)


class ReportWriterTests(unittest.TestCase):
    def test_write_scan_report_creates_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            staging = Path(tmp) / "staging"
            _make_staging(staging)
            scan = final_source_scan(staging, SourceScanPolicy.default())
            target = Path(tmp) / "out"
            path = write_scan_report(scan, target)
            self.assertTrue(path.is_file())
            self.assertEqual(path.name, "source-scan-report.json")


if __name__ == "__main__":
    unittest.main()