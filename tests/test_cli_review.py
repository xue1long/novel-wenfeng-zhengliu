"""Stage C Task 7b: review-dimensions CLI."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "tests"))
from holdout_fixtures import prepare_locked_run  # noqa: E402


def _bootstrap(tmp: Path) -> Path:
    init_root = prepare_locked_run(
        tmp,
        "# 第一章\n句子一。\n\n# 第二章\n句子二。\n\n# 第三章\n句子三。\n",
    )
    subprocess.run(
        [sys.executable, "scripts/cli_extract.py", "extract-dimensions",
         "--run-root", str(init_root), "--run-id", "r1",
         "--stub", "--stub-profile", "all_supported"],
        cwd=str(PROJECT_ROOT), capture_output=True, text=True, timeout=30,
    )
    return init_root


class ReviewDimensionsTests(unittest.TestCase):
    def test_merges_legal_review_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            init_root = _bootstrap(Path(tmp))
            # Build a per-dimension verdict file.
            verdict = {}
            for path in sorted((init_root / "candidates").glob("*.json")):
                payload = json.loads(path.read_text(encoding="utf-8"))
                dimension = payload["dimension"]
                verdicts = []
                for cand in payload["candidates"]:
                    verdicts.append({
                        "mechanism_id": cand["mechanism_id"],
                        "review_status": "supported",
                        "reasons": [f"model says yes to {cand['mechanism_id']}"],
                    })
                verdict[dimension] = verdicts
            review_file = Path(tmp) / "reviews.json"
            review_file.write_text(json.dumps(verdict, ensure_ascii=False), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, "scripts/cli_extract.py", "review-dimensions",
                 "--run-root", str(init_root), "--review-file", str(review_file)],
                cwd=str(PROJECT_ROOT), capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            # Re-read a candidate, confirm review_status merged.
            for path in (init_root / "candidates").glob("*.json"):
                payload = json.loads(path.read_text(encoding="utf-8"))
                for cand in payload["candidates"]:
                    self.assertEqual(cand["review_status"], "supported")
                    self.assertIn("review_reasons", cand)

    def test_missing_review_status_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            init_root = _bootstrap(Path(tmp))
            # Build a verdict that targets the real dimension + a real mechanism_id
            # but has no ``review_status`` field, which ``parse_review_output``
            # must reject.
            payload = json.loads(
                (init_root / "candidates" / "narrative_voice.json").read_text(encoding="utf-8")
            )
            verdict = {
                "narrative_voice": [
                    {"mechanism_id": payload["candidates"][0]["mechanism_id"], "reasons": ["no status"]}
                ]
            }
            review_file = Path(tmp) / "reviews.json"
            review_file.write_text(json.dumps(verdict), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, "scripts/cli_extract.py", "review-dimensions",
                 "--run-root", str(init_root), "--review-file", str(review_file)],
                cwd=str(PROJECT_ROOT), capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0)
            summary = json.loads((init_root / "review-summary.json").read_text(encoding="utf-8"))
            self.assertTrue(any("error" in e for e in summary), summary)

    def test_free_text_review_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            init_root = _bootstrap(Path(tmp))
            review_file = Path(tmp) / "reviews.json"
            review_file.write_text("a string that is not JSON", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, "scripts/cli_extract.py", "review-dimensions",
                 "--run-root", str(init_root), "--review-file", str(review_file)],
                cwd=str(PROJECT_ROOT), capture_output=True, text=True, timeout=30,
            )
            self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
