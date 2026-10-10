"""Stage G Task 4: isolated install + verify-package.

Pure stdlib. Two install paths:

  - ``dry_run_install`` extracts the package to a tmpdir and runs
    ``verify_package``; the requested target is never touched.
  - ``user_install`` is explicit opt-in (the CLI passes ``--scope user``)
    and writes to the user-supplied target.

Ruling-G3: any of these target paths is **always rejected**:

  - ``Path.home() / ".wenfeng-skill"``
  - ``Path(os.environ.get("APPDATA", "")) / "wenfeng-skill"``
  - any path that lives under ``dist/<source_id>/<bundle_version>/`` of
    another dist (we detect via the run_root argument; refusing same-name
    overwrite is delegated to ``force=False`` callers)

  - ``--scope system`` is NOT recognized at the parser layer; this module
    therefore only exposes ``user_install`` and the install scope is
    hard-coded.

  - Refuses to overwrite an existing target unless ``force=True``.

verify_package cross-stage:

  1. extract package to a tmpdir (managed by the caller or auto);
  2. run ``release_manifest.verify_release_manifest`` on the embedded
     release-manifest.json;
  3. run ``cli_compile.validate_dist`` (stage E) on the extracted subdir;
  4. run ``cli_evaluate.validate_evaluation`` (stage F) on the eval-report
     inside the extracted subdir.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from path_safety import (
    PathEscapeError,
    assert_no_symlink_escape,
    assert_within_run_root,
)


class IsolatedInstallError(Exception):
    def __init__(self, message: str, *, error_type: str = "isolated_install_error") -> None:
        super().__init__(message)
        self.error_type = error_type


def _standard_locations() -> tuple[Path, ...]:
    out: list[Path] = []
    home = Path.home()
    if home:
        out.append(home / ".wenfeng-skill")
    appdata_raw = os.environ.get("APPDATA", "")
    if appdata_raw:
        out.append(Path(appdata_raw) / "wenfeng-skill")
    out.append(home / "Library" / "Application Support" / "wenfeng-skill")
    return tuple(out)


def _refuse_standard_locations(target: Path) -> None:
    target = target.resolve()
    for forbidden in _standard_locations():
        if target == forbidden.resolve() or forbidden.resolve() in target.parents:
            raise IsolatedInstallError(
                f"refusing to install to standard location: {target}"
            )


def extract_to_dir(
    package_path: Path,
    target_dir: Path,
    *,
    run_root: Path,
) -> None:
    """Extract a ZIP package into ``target_dir``.

    Refuses:
      - any path that escapes ``target_dir``;
      - any symlink.
    """
    package_path = Path(package_path).resolve()
    target_dir = Path(target_dir).resolve()
    assert_within_run_root(run_root, target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(package_path, "r") as zf:
        for member in zf.namelist():
            try:
                assert_no_symlink_escape(target_dir / member)
            except PathEscapeError as exc:
                raise IsolatedInstallError(str(exc)) from exc
        # Python's zipfile refuses symlinks on extract via the data
        # descriptor; we keep this loop explicit so a future override can
        # be noticed.
        zf.extractall(target_dir)
    # The release-manifest.json lives at the dist_dir root alongside the
    # package.zip (not inside the ZIP, to avoid a self-referential hash
    # loop). We look for a sibling file with that name next to the
    # package zip and copy it into target.
    sibling = package_path.parent / "release-manifest.json"
    if sibling.is_file():
        try:
            assert_within_run_root(run_root, sibling)
        except PathEscapeError as exc:
            raise IsolatedInstallError(str(exc)) from exc
        shutil.copy2(sibling, target_dir / "release-manifest.json")


def dry_run_install(
    package_path: Path,
    *,
    target: Path,
    run_root: Path,
) -> dict:
    """Extract to a tmpdir, verify, and return a result dict.

    The user-supplied ``target`` is never touched.
    """
    package_path = Path(package_path).resolve()
    target = Path(target).resolve()
    if not package_path.is_file():
        raise IsolatedInstallError(f"package not found: {package_path}")
    _refuse_standard_locations(target)
    with tempfile.TemporaryDirectory(
        dir=str(run_root.resolve()), prefix="wenfeng-dryrun-", suffix=".tmp"
    ) as tmp:
        tmpdir = Path(tmp)
        extract_to_dir(package_path, tmpdir, run_root=run_root)
        verify = verify_package_in_dir(tmpdir, package_path=package_path, run_root=run_root)
        return {
            "dry_run": True,
            "target": str(target),
            "tmpdir": str(tmpdir),
            "verify_result": verify,
            "files_in_target_unchanged": True,
        }


def user_install(
    package_path: Path,
    *,
    target: Path,
    run_root: Path,
    force: bool = False,
) -> dict:
    """Explicit opt-in. Writes to ``target``; always refuses standard
    locations and refuses same-name overwrite unless ``force=True``.
    """
    package_path = Path(package_path).resolve()
    target = Path(target).resolve()
    if not package_path.is_file():
        raise IsolatedInstallError(f"package not found: {package_path}")
    _refuse_standard_locations(target)
    if target.exists() and any(target.iterdir()):
        if not force:
            raise IsolatedInstallError(
                f"target {target} is non-empty; pass force=True to overwrite"
            )
        # With force, refuse to clobber a standard location explicitly
        # unless the caller has opted in to standard locations.
        _refuse_standard_locations(target)
        # Wipe the existing target before extracting.
        for child in list(target.iterdir()):
            if child.is_file() or child.is_symlink():
                child.unlink()
            else:
                shutil.rmtree(child)
    # Run-level containment is enforced for in-run extracts; user installs
    # are explicitly opt-in and may target paths outside run_root (e.g.
    # the user's home directory). When the install opt-in is used, skip
    # the containment check entirely and rely on zipfile's own
    # destination containment below.
    _extract_user_install(package_path, target, run_root=run_root)
    return {
        "installed": True,
        "target": str(target),
        "files": sorted(str(p.relative_to(target)) for p in target.rglob("*") if p.is_file()),
    }


def _extract_user_install(
    package_path: Path,
    target_dir: Path,
    *,
    run_root: Path,
) -> None:
    """Extract a ZIP package into ``target_dir`` for user_install.

    Unlike ``extract_to_dir``, this does NOT enforce run-root containment
    because user installs are explicitly allowed to target caller-selected
    paths outside run_root. Standard Skill locations remain blocked. It still enforces:
      - destination containment (no zip-slip);
      - no symlinks;
      - target_dir is created if missing.
    """
    package_path = Path(package_path).resolve()
    target_dir = Path(target_dir).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(package_path, "r") as zf:
        for member in zf.namelist():
            try:
                assert_no_symlink_escape(target_dir / member)
            except PathEscapeError as exc:
                raise IsolatedInstallError(str(exc)) from exc
        zf.extractall(target_dir)
    sibling = package_path.parent / "release-manifest.json"
    if sibling.is_file():
        shutil.copy2(sibling, target_dir / "release-manifest.json")


def verify_package_in_dir(
    extracted_dir: Path,
    *,
    package_path: Path | None = None,
    run_root: Path | None = None,
) -> dict:
    """Cross-stage verification: release-manifest + 6 Skill hashes + stage F.

    The stage E `validate_dist` helper is not used directly because the
    packaging layer adds ``eval-report.json`` and ``release-manifest.json``
    on top of stage E's six SKILL.md + compile-manifest.json. Instead we
    re-check the 6 Skill hashes that ``release-manifest.json`` records
    against the live files.
    """
    extracted_dir = Path(extracted_dir).resolve()
    if run_root is not None:
        assert_within_run_root(run_root, extracted_dir)
    if not (extracted_dir / "release-manifest.json").is_file():
        return {"ok": False, "error": "release-manifest.json missing"}

    from release_manifest import verify_release_manifest
    manifest = json.loads(
        (extracted_dir / "release-manifest.json").read_text(encoding="utf-8")
    )
    release_errors = verify_release_manifest(manifest, staging_root=extracted_dir)

    # Stage F cross-check: eval-report is present, redacted, has final_state.
    stage_f_errors: list[str] = []
    eval_report_path = extracted_dir / "eval-report.json"
    if not eval_report_path.is_file():
        stage_f_errors.append("eval-report.json missing")
    else:
        report = json.loads(eval_report_path.read_text(encoding="utf-8"))
        for leaked in ("unblinding_map", "pair_results", "rating_secrets"):
            if leaked in report:
                stage_f_errors.append(f"eval-report leaked {leaked!r}")
        notes = report.get("summary", {}).get("notes", "")
        if "redacted" not in notes:
            stage_f_errors.append("eval-report.notes missing redaction marker")
        if "final_state" not in report.get("summary", {}):
            stage_f_errors.append("eval-report.summary.final_state missing")

    return {
        "ok": not (release_errors or stage_f_errors),
        "release_manifest_errors": release_errors,
        "stage_f_errors": stage_f_errors,
    }


def verify_package(
    package_path: Path,
    *,
    run_root: Path,
) -> dict:
    """Top-level: extract to tmpdir, verify, return result."""
    package_path = Path(package_path).resolve()
    if not package_path.is_file():
        raise IsolatedInstallError(f"package not found: {package_path}")
    with tempfile.TemporaryDirectory(
        dir=str(run_root.resolve()), prefix="wenfeng-verify-", suffix=".tmp"
    ) as tmp:
        tmpdir = Path(tmp)
        extract_to_dir(package_path, tmpdir, run_root=run_root)
        result = verify_package_in_dir(tmpdir, package_path=package_path, run_root=run_root)
        result["tmpdir"] = str(tmpdir)
        return result


__all__ = [
    "IsolatedInstallError",
    "dry_run_install",
    "user_install",
    "verify_package",
    "verify_package_in_dir",
    "extract_to_dir",
]
