"""Stage B Task 1: path containment + symlink escape checks.

Spec anchor: §4.1 '私有运行目录' / §6 阶段 B 验收'路径逃逸阻断'.

The helpers here MUST be pure stdlib so that no model code is ever tempted
to relax them.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from path_safety import (  # noqa: E402
    PathEscapeError,
    PathExistsError,
    assert_no_symlink_escape,
    assert_within_run_root,
    safe_mkdir,
)


class PathSafetyNegativeTests(unittest.TestCase):
    def test_target_outside_run_root_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "run"
            run_root.mkdir()
            target = run_root / ".." / "evil"
            with self.assertRaises(PathEscapeError):
                assert_within_run_root(run_root, target)

    def test_symlink_under_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "run"
            run_root.mkdir()
            outside = Path(tmp) / "outside.txt"
            outside.write_text("data", encoding="utf-8")
            link = run_root / "link"
            try:
                link.symlink_to(outside)
            except OSError as exc:
                self.skipTest(f"symlink unsupported on this platform: {exc}")
            with self.assertRaises(PathEscapeError):
                assert_no_symlink_escape(link)

    def test_existing_target_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "run"
            run_root.mkdir()
            target = run_root / "subdir"
            target.mkdir()
            with self.assertRaises(PathExistsError):
                safe_mkdir(target)

    def test_target_containing_nul_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "run"
            run_root.mkdir()
            target = run_root / "bad\u0000name"
            with self.assertRaises(PathEscapeError):
                assert_within_run_root(run_root, target)

    def test_unresolvable_target_rejected(self):
        # A non-existent target on a symlinked parent chain that resolves away.
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "run"
            run_root.mkdir()
            outside_parent = Path(tmp) / "outside"
            outside_parent.mkdir()
            try:
                (run_root / "link").symlink_to(outside_parent)
            except OSError as exc:
                self.skipTest(f"symlink unsupported: {exc}")
            target = run_root / "link" / "ghost"
            with self.assertRaises(PathEscapeError):
                assert_within_run_root(run_root, target)


class PathSafetyHappyPathTests(unittest.TestCase):
    def test_target_under_run_root_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "run"
            run_root.mkdir()
            target = run_root / "subdir"
            assert_within_run_root(run_root, target)

    def test_deeply_nested_target_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "run"
            run_root.mkdir()
            target = run_root / "a" / "b" / "c" / "d"
            assert_within_run_root(run_root, target)

    def test_run_root_itself_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "run"
            run_root.mkdir()
            assert_within_run_root(run_root, run_root)

    def test_safe_mkdir_creates_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "run"
            run_root.mkdir()
            target = run_root / "fresh"
            safe_mkdir(target)
            self.assertTrue(target.is_dir())


class PathSafetyCrossPlatformNoteTests(unittest.TestCase):
    """On Windows the temp dir is on the same drive as the run root by
    construction. On POSIX we additionally assert the same-root containment
    using ``os.path.commonpath`` so the helper's intent is pinned."""

    def test_run_root_under_temp_uses_no_parent_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "run"
            run_root.mkdir()
            # The run root is inside the temp dir; resolve both and assert
            # containment directly using stdlib only.
            common = os.path.commonpath([str(run_root.resolve()), str(Path(tmp).resolve())])
            self.assertEqual(common, str(Path(tmp).resolve()))


if __name__ == "__main__":
    unittest.main()