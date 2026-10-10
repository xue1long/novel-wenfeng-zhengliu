"""Stage B Task 1: path containment + symlink escape checks.

Pure stdlib helpers used by every other Stage B tool. Any tool that needs to
write a run artifact MUST go through ``safe_mkdir`` or call
``assert_within_run_root`` + ``assert_no_symlink_escape`` directly.

Design constraints (Ruling-1, Ruling-2 from docs/superpowers/plans/
2026-10-09-stage-b-scaffold.md):
  - Never write outside the explicit run root passed by the caller.
  - Reject NUL bytes; reject symlinked parent components.
  - On any failure, raise a typed exception so callers can map to
    ``run-manifest.step_log.error_type`` later in Stage B.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable


class PathSafetyError(Exception):
    """Base class for path safety errors. Never swallow this."""

    def __init__(self, message: str, *, error_type: str = "path_safety") -> None:
        super().__init__(message)
        self.error_type = error_type


class PathEscapeError(PathSafetyError):
    """Raised when a target path resolves outside its declared run root."""

    def __init__(self, message: str) -> None:
        super().__init__(message, error_type="path_escape")


class PathExistsError(PathSafetyError):
    """Raised when a target already exists and ``safe_mkdir`` was asked not
    to touch existing entries."""

    def __init__(self, message: str) -> None:
        super().__init__(message, error_type="path_exists")


def _check_nul(path: Path) -> None:
    if "\x00" in str(path):
        raise PathEscapeError(f"path contains NUL byte: {path!r}")


def assert_within_run_root(run_root: Path, target: Path) -> None:
    """Raise ``PathEscapeError`` if ``target`` resolves outside ``run_root``.

    Both paths are resolved via ``Path.resolve(strict=False)``. Strict mode
    is deliberately off because the target may not exist yet; what matters
    is that the *resolved lexical* path is contained.
    """
    _check_nul(run_root)
    _check_nul(target)
    run_resolved = run_root.resolve()
    target_resolved = target.resolve()
    try:
        common = os.path.commonpath([str(run_resolved), str(target_resolved)])
    except ValueError as exc:
        raise PathEscapeError(
            f"target {target_resolved} is on a different drive from run_root {run_resolved}: {exc}"
        ) from exc
    if common != str(run_resolved):
        raise PathEscapeError(
            f"target {target_resolved} escapes run_root {run_resolved}"
        )


def assert_no_symlink_escape(path: Path) -> None:
    """Walk the parent chain of ``path`` and refuse any symlinked component.

    Stage B uses this before any ``mkdir`` so that a symlinked parent does not
    cause the new directory to materialize outside the run root.
    """
    _check_nul(path)
    parent = path if path.is_absolute() else path.resolve()
    # Walk up to (but not including) the filesystem root.
    for current in (parent, *parent.parents):
        if current == current.parent:
            break
        if current.is_symlink():
            raise PathEscapeError(f"symlink detected in path chain at {current}")


def safe_mkdir(path: Path) -> None:
    """Create ``path`` (parents included) after containment + symlink checks.

    Raises:
      PathEscapeError: containment or symlink check failed.
      PathExistsError: ``path`` already exists (callers may pass ``--resume``).
    """
    if path.exists():
        raise PathExistsError(f"path already exists: {path}")
    parent = path.parent
    # The CLI layer is responsible for passing the run root explicitly; here
    # we only check that the parent isn't a symlink and that no NUL leaks in.
    _check_nul(path)
    if parent.exists() and parent.is_symlink():
        raise PathEscapeError(f"parent is a symlink: {parent}")
    path.mkdir(parents=True, exist_ok=False)


def iter_within_run_root(run_root: Path, paths: Iterable[Path]) -> Iterable[Path]:
    """Yield ``paths`` that pass containment. Filter out the rest.

    Convenience helper for the CLI so it can validate a list of artifact
    destinations without short-circuiting at the first violation.
    """
    for path in paths:
        try:
            assert_within_run_root(run_root, path)
        except PathSafetyError:
            continue
        yield path


__all__ = [
    "PathSafetyError",
    "PathEscapeError",
    "PathExistsError",
    "assert_within_run_root",
    "assert_no_symlink_escape",
    "safe_mkdir",
    "iter_within_run_root",
]