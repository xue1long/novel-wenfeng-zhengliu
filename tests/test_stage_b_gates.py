"""Stage B Task 9: aggregate acceptance gate tests.

The companion ``scripts/check_stage_b.py`` is the command-line entry point.
This test pins the same invariants from inside the unittest runner so that
``python -m unittest discover`` is sufficient to satisfy stage B.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _run_cli(args: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "scripts/cli.py", *args],
        cwd=str(cwd or PROJECT_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )


class EndToEndSyntheticRunTests(unittest.TestCase):
    def test_full_pipeline_walks_through(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            src = tmp_path / "novel.txt"
            payload = "\ufeff第一章 开始\r\n这是测试正文。\r\n第二章 续\r\n更多。\r\n".encode("utf-8")
            src.write_bytes(payload)
            auth = tmp_path / "auth.json"
            auth.write_text(json.dumps({
                "scope": {"model_processing": "local_only", "derivative_use": "private_only"},
                "evidence_basis": "user_declaration",
            }), encoding="utf-8")

            prepare_root = tmp_path / "run"
            r = _run_cli(["prepare-source", "--source", str(src), "--run-root", str(prepare_root)])
            self.assertEqual(r.returncode, 0, msg=r.stdout + r.stderr)
            chunk_manifest = json.loads((prepare_root / "chunk-manifest.json").read_text(encoding="utf-8"))
            self.assertGreater(len(chunk_manifest["chunks"]), 0)

            init_root = tmp_path / "init-run"
            r = _run_cli([
                "init-run", "--run-root", str(init_root),
                "--run-id", "r1", "--authorization", str(auth),
                "--requested-model-id", "local",
                "--requested-purpose", "private_only",
            ])
            self.assertEqual(r.returncode, 0, msg=r.stdout + r.stderr)
            self.assertTrue((init_root / "run-manifest.json").is_file())

            # Resume idempotency end-to-end.
            for _ in range(2):
                r = _run_cli([
                    "resume-run", "--run-root", str(init_root),
                    "--run-id", "r1", "--step-id", "prepare-source",
                    "--retry-count", "0",
                ])
                self.assertEqual(r.returncode, 0, msg=r.stdout + r.stderr)
            manifest = json.loads((init_root / "run-manifest.json").read_text(encoding="utf-8"))
            prepare_steps = [s for s in manifest["step_log"] if s["step_id"] == "prepare-source"]
            self.assertEqual(len(prepare_steps), 1)


class CheckStageBEntrypointTests(unittest.TestCase):
    def test_check_stage_b_main_returns_zero(self):
        # The aggregate gate subprocess would itself spawn another unittest
        # runner; that's prone to recursive timeouts on Windows. Instead we
        # import the module and call its end-to-end + invariant checks
        # directly; upstream stages have their own gates.
        sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
        import check_stage_b  # noqa: E402
        failures: list[str] = []
        failures.extend(check_stage_b._check_stage_b_invariants())
        failures.extend(check_stage_b._check_end_to_end())
        self.assertEqual(failures, [], msg=failures)


if __name__ == "__main__":
    unittest.main()
