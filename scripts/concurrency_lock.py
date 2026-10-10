"""Stage E Task 1: cross-process file lock.

Pure stdlib. Uses :mod:`msvcrt.locking` on Windows and :func:`fcntl.flock`
on POSIX. The lock file is ``<lock_root>/<key>.lock``.

A second acquire on the same key (whether from a different process or from
the same process) raises :class:`LockBusy`. ``timeout_seconds=0`` means
non-blocking; a positive timeout polls briefly. Ruling-E7 says we must
reject recursive acquires from the same process; we implement that by
tracking open handles in-process on a ``ThreadLocal``.
"""

from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path
from typing import Optional


class LockError(Exception):
    def __init__(self, message: str, *, error_type: str = "lock_error") -> None:
        super().__init__(message)
        self.error_type = error_type


class LockBusy(LockError):
    def __init__(self, message: str) -> None:
        super().__init__(message, error_type="lock_busy")


class LockUnsupported(LockError):
    def __init__(self, message: str) -> None:
        super().__init__(message, error_type="lock_unsupported")


_THREAD_LOCAL = threading.local()
_OPEN_HANDLES: dict[str, "LockHandle"] = {}


def _safe_lock(fd: int) -> None:
    if sys.platform == "win32":
        import msvcrt  # noqa: WPS433  # type: ignore
        # Length-prefixed region; lock the whole file.
        size = max(1, os.fstat(fd).st_size or 1)
        try:
            msvcrt.locking(fd, msvcrt.LK_LOCK, size)
        except OSError as exc:  # pragma: no cover  - platform specific
            raise LockBusy(str(exc)) from exc
    else:
        import fcntl  # noqa: WPS433  # type: ignore
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if exc.errno in (os.errno.EWOULDBLOCK, os.errno.EAGAIN):
                raise LockBusy(str(exc)) from exc
            raise


def _safe_unlock(fd: int) -> None:
    if sys.platform == "win32":
        import msvcrt  # noqa: WPS433  # type: ignore
        size = max(1, os.fstat(fd).st_size or 1)
        try:
            msvcrt.locking(fd, msvcrt.LK_UNLCK, size)
        except OSError:
            pass
    else:
        import fcntl  # noqa: WPS433  # type: ignore
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        except OSError:
            pass


class LockHandle:
    """A handle representing one acquired lock."""

    def __init__(self, path: Path, fd: int, key: str) -> None:
        self.path = path
        self.fd = fd
        self.key = key
        self._released = False

    def release(self) -> None:
        if self._released:
            return
        self._released = True
        try:
            _safe_unlock(self.fd)
        finally:
            try:
                os.close(self.fd)
            except OSError:
                pass
            _OPEN_HANDLES.pop(self.key, None)


def acquire(
    lock_root: Path,
    key: str,
    *,
    timeout_seconds: float = 0.0,
    poll_interval_seconds: float = 0.05,
) -> LockHandle:
    """Acquire the file lock at ``<lock_root>/<key>.lock``.

    Raises :class:`LockBusy` if the lock is held elsewhere or by the same
    process. A non-zero ``timeout_seconds`` retries with ``poll_interval_seconds``
    until the deadline. Windows short-poll is approximated by close-then-reopen.
    """
    if not key:
        raise LockError("lock key must be non-empty")
    if key in _OPEN_HANDLES:
        raise LockBusy(f"lock {key!r} already held in this process")
    lock_root.mkdir(parents=True, exist_ok=True)
    path = lock_root / f"{key}.lock"
    deadline = time.monotonic() + max(0.0, timeout_seconds)
    while True:
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_RDWR, 0o644)
        except OSError as exc:  # pragma: no cover - filesystem failure
            raise LockError(f"cannot open lock file {path}: {exc}") from exc
        try:
            _safe_lock(fd)
        except LockBusy:
            os.close(fd)
            if time.monotonic() >= deadline:
                raise LockBusy(f"lock {key!r} busy (timeout)")
            time.sleep(poll_interval_seconds)
            continue
        handle = LockHandle(path, fd, key)
        _OPEN_HANDLES[key] = handle
        return handle


__all__ = [
    "LockError",
    "LockBusy",
    "LockUnsupported",
    "LockHandle",
    "acquire",
]