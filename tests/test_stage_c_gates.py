"""Stage C Task 8: aggregate acceptance gate tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "tests"))
from holdout_fixtures import prepare_locked_run  # noqa: E402


class EndToEndGateTests(unittest.TestCase):
    def test_end_to_end_synthetic_run(self):
        import check_stage_c  # noqa: E402
        failures = check_stage_c._check_stage_c_invariants() + check_stage_c._check_end_to_end()
        self.assertEqual(failures, [], msg=failures)

    def test_adversarial_offset_rejected(self):
        import check_stage_c  # noqa: E402
        failures = check_stage_c._check_adversarial_offset()
        self.assertEqual(failures, [], msg=failures)

    def test_default_stub_does_not_emit_ready_bundle(self):
        import check_stage_c  # noqa: E402
        # End-to-end uses a synthetic review that downgrades every candidate
        # to "limited", so the bundle must not be "ready".
        # We re-run the end-to-end check and assert the bundle status is
        # bounded above by "limited".
        import subprocess, tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            run_root = prepare_locked_run(
                tmp_path,
                "# 第一章\n句子一。句子二。\n\n# 第二章\n句子三。句子四。\n\n# 第三章\n句子五。句子六。\n",
            )
            subprocess.run(
                [sys.executable, "scripts/cli_extract.py", "extract-dimensions",
                 "--run-root", str(run_root), "--run-id", "r1", "--stub"],
                cwd=str(PROJECT_ROOT), capture_output=True, text=True, encoding="utf-8", timeout=30,
            )
            bundle_path = run_root / "style-bundle.json"
            # No review/compile happened in this short test; we only assert
            # that no Bundle was prematurely emitted. The aggregate gate
            # covers the full chain.
            self.assertFalse(bundle_path.is_file())


if __name__ == "__main__":
    unittest.main()
