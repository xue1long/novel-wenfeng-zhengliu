"""Stage E Task 3: static preflight checks.

Pure stdlib. Validates a projected Skill's body and a staging directory:

  - body must be UTF-8 round-trip-clean;
  - body must NOT carry remote URLs (``http://``, ``https://``), script-like
    constructs (``<script``, onerror=), or local paths that would point at
    other parts of the project (``templates/``, ``scripts/``, ``docs/``,
    ``schemas/``);
  - the staging directory's top-level subdirectories must use exactly the
    six stage_ids;
  - the staging directory must contain exactly the declared files (manifest
    contents vs filesystem contents);
  - any symlink that escapes ``--staging-root`` is rejected (delegates to
    stage B ``path_safety``).
"""

from __future__ import annotations

import re
from pathlib import Path

from path_safety import PathEscapeError, assert_no_symlink_escape, assert_within_run_root


SIX_STAGE_IDS: tuple[str, ...] = (
    "write_entry",
    "scene_design",
    "character_beats",
    "prose_draft",
    "style_check",
    "revision",
)


_FRONT_MATTER_DELIMITER = "---"
_REQUIRED_FRONTMATTER_KEYS: tuple[str, ...] = (
    "stage_id", "contract_version", "trigger_examples", "required_inputs",
    "primary_output", "missing_input_behavior", "stop_conditions", "not_allowed",
)


_REMOTE_URL_RE = re.compile(r"https?://", re.IGNORECASE)
_SCRIPT_TAG_RE = re.compile(r"<script\b", re.IGNORECASE)
_JS_HANDLER_RE = re.compile(r"\bon[a-z]+\s*=", re.IGNORECASE)
_PROJECT_PATH_RE = re.compile(
    r"\b(templates|scripts|docs|schemas|vendor)/", re.IGNORECASE
)


def _validate_body(body: str, *, location: str) -> list[str]:
    errors: list[str] = []
    try:
        body.encode("utf-8").decode("utf-8")
    except UnicodeError as exc:
        errors.append(f"{location}: not valid UTF-8 round-trip: {exc}")
        return errors

    # The body may carry the full ``---\n...---body...`` document OR a
    # post-frontmatter markdown fragment (Skill projected body used by the
    # compiler). Detect both shapes.
    if body.lstrip().startswith(_FRONT_MATTER_DELIMITER):
        # Full document. Verify the frontmatter keys.
        fm_end = body.find("\n---", 3)
        if fm_end == -1:
            errors.append(f"{location}: missing closing frontmatter delimiter '---'")
            return errors
        fm_text = body[3:fm_end]
        for key in _REQUIRED_FRONTMATTER_KEYS:
            if not re.search(rf"(?m)^{re.escape(key)}\s*:", fm_text):
                errors.append(f"{location}: frontmatter missing key {key!r}")
        body_part = body[fm_end + 4:]
    else:
        # Markdown fragment only. frontmatter integrity is the
        # ``skill_template.parse_template`` layer's job, not ours.
        body_part = body

    if _REMOTE_URL_RE.search(body_part):
        errors.append(f"{location}: body contains remote URL")
    if _SCRIPT_TAG_RE.search(body_part):
        errors.append(f"{location}: body contains <script> tag")
    if _JS_HANDLER_RE.search(body_part):
        errors.append(f"{location}: body contains JS-style on...= handler")
    if _PROJECT_PATH_RE.search(body_part):
        errors.append(f"{location}: body references project-internal path (templates/, scripts/, docs/, schemas/)")
    leftover = re.findall(r"\{([a-z_]+)\}", body_part)
    if leftover:
        errors.append(f"{location}: body still contains placeholders {set(leftover)!r}")
    return errors


def preflight_skill(
    stage_id: str,
    body: str,
    *,
    location: str | None = None,
) -> list[str]:
    """Validate a single projected Skill body."""
    loc = location or stage_id
    errors: list[str] = []
    errors.extend(_validate_body(body, location=loc))
    return errors


def preflight_staging_directory(
    staging_root: Path,
    *,
    declared_files: dict[str, str],
    run_root: Path,
) -> list[str]:
    """Validate that ``staging_root`` contains exactly the declared files.

    ``declared_files`` is ``{relative_path: sha256_hex}``. The filesystem
    walk must match it exactly; any extra or missing file is an error.
    ``run_root`` is the parent of ``staging_root`` and must contain the
    staging directory by containment (delegates to ``path_safety``).
    """
    errors: list[str] = []
    try:
        assert_within_run_root(run_root, staging_root)
    except PathEscapeError as exc:
        errors.append(f"staging_root escapes run_root: {exc}")
        return errors
    try:
        assert_no_symlink_escape(staging_root)
    except PathEscapeError as exc:
        errors.append(f"staging_root has symlink escape: {exc}")

    if not staging_root.is_dir():
        errors.append(f"staging_root does not exist: {staging_root}")
        return errors

    actual: set[str] = set()
    for path in sorted(staging_root.rglob("*")):
        if path.is_dir():
            continue
        rel = path.relative_to(staging_root).as_posix()
        actual.add(rel)
        # Path containment per file.
        try:
            assert_within_run_root(staging_root, path)
        except PathEscapeError as exc:
            errors.append(f"{rel}: escapes staging_root: {exc}")

    declared = set(declared_files.keys())
    if actual != declared:
        missing = declared - actual
        extras = actual - declared
        for rel in sorted(missing):
            errors.append(f"declared file missing: {rel}")
        for rel in sorted(extras):
            errors.append(f"undeclared file present: {rel}")
    return errors


__all__ = [
    "SIX_STAGE_IDS",
    "preflight_skill",
    "preflight_staging_directory",
]