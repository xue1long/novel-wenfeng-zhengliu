"""Stage B Task 8a: prepare-source CLI."""

from __future__ import annotations

import json
import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _run(args: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "scripts/cli.py", *args],
        cwd=str(cwd or PROJECT_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )


class PrepareSourceTests(unittest.TestCase):
    def test_prepare_writes_manifests(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "novel.txt"
            src.write_text("# 第一章\n这是正文。\n# 第二章\n更多正文。", encoding="utf-8")
            run_root = Path(tmp) / "run"
            result = _run(["prepare-source", "--source", str(src), "--run-root", str(run_root)])
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            self.assertTrue((run_root / "source-manifest.json").is_file())
            self.assertTrue((run_root / "chunk-manifest.json").is_file())
            source_manifest = json.loads((run_root / "source-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(len(source_manifest["source_id"]), 12)
            self.assertNotEqual(source_manifest["source_id"], source_manifest["source_fingerprint"][:12])
            self.assertEqual(source_manifest["raw_sha256"], hashlib.sha256(src.read_bytes()).hexdigest())
            chunk_manifest = json.loads((run_root / "chunk-manifest.json").read_text(encoding="utf-8"))
            self.assertGreater(len(chunk_manifest["chunks"]), 0)

    def test_missing_source_returns_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "run"
            result = _run(["prepare-source", "--source", str(Path(tmp) / "missing.txt"), "--run-root", str(run_root)])
            self.assertEqual(result.returncode, 2)

    def test_nonexistent_parent_returns_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "novel.txt"
            src.write_text("正文", encoding="utf-8")
            run_root = Path(tmp) / "no-such-parent" / "run"
            result = _run(["prepare-source", "--source", str(src), "--run-root", str(run_root)])
            self.assertEqual(result.returncode, 2)

    def test_crlf_and_bom_normalized(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "novel.txt"
            payload = "\ufeff正文\r\n下一段\r\n".encode("utf-8")
            src.write_bytes(payload)
            run_root = Path(tmp) / "run"
            result = _run(["prepare-source", "--source", str(src), "--run-root", str(run_root)])
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            chunk_manifest = json.loads((run_root / "chunk-manifest.json").read_text(encoding="utf-8"))
            # Normalized chunks should not contain BOM or \r in their hashes.
            for chunk in chunk_manifest["chunks"]:
                self.assertNotIn("\r", chunk["window_hash"])  # SHA-256 of normalized text
                self.assertNotIn("\ufeff", chunk["window_hash"])
