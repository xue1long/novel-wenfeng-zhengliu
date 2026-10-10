"""Stage E Task 1 tests."""

from __future__ import annotations

import sys
import tempfile
import threading
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from concurrency_lock import (  # noqa: E402
    LockBusy,
    LockHandle,
    acquire,
)


class LockAcquireReleaseTests(unittest.TestCase):
    def test_lock_root_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "locks"
            handle = acquire(root, "key1")
            self.assertIsInstance(handle, LockHandle)
            self.assertTrue((root / "key1.lock").is_file())
            handle.release()

    def test_release_then_reacquire(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "locks"
            handle = acquire(root, "key2")
            handle.release()
            handle2 = acquire(root, "key2")
            self.assertIsInstance(handle2, LockHandle)
            handle2.release()

    def test_release_unheld_lock_does_not_raise(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "locks"
            handle = acquire(root, "key3")
            handle.release()
            # Second release is a no-op.
            handle.release()


class LockBusyTests(unittest.TestCase):
    def test_same_process_double_acquire_raises_busy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "locks"
            handle = acquire(root, "key4")
            try:
                with self.assertRaises(LockBusy):
                    acquire(root, "key4")
            finally:
                handle.release()

    def test_timeout_returns_busy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "locks"
            handle = acquire(root, "key5")
            try:
                with self.assertRaises(LockBusy):
                    acquire(root, "key5", timeout_seconds=0.05)
            finally:
                handle.release()


class ConcurrentAcquireTests(unittest.TestCase):
    def test_two_threads_one_succeeds(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "locks"
            results: list[str] = []
            started = threading.Event()
            proceed = threading.Event()
            holder: list = []

            def worker() -> None:
                try:
                    handle = acquire(root, "key6", timeout_seconds=0.5)
                except LockBusy:
                    results.append("busy")
                    return
                holder.append(handle)
                results.append("ok")
                started.set()
                # Hold the lock long enough that the second worker is sure
                # to see ``LockBusy`` regardless of scheduling.
                proceed.wait(timeout=2.0)

            t1 = threading.Thread(target=worker)
            t2 = threading.Thread(target=worker)
            t1.start()
            started.wait(timeout=2.0)
            t2.start()
            t1.join()
            t2.join()
            proceed.set()
            # Release before the tempdir cleanup runs.
            for handle in holder:
                handle.release()
            self.assertEqual(sorted(results), ["busy", "ok"], results)


class EmptyKeyTests(unittest.TestCase):
    def test_empty_key_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(Exception):
                acquire(Path(tmp), "")


if __name__ == "__main__":
    unittest.main()