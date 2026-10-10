"""Stage E Task 5: deterministic six-skill compiler.

Pure stdlib. Composes Stage D's projector with Stage E's preflight and
literal-scan, and writes a Stage A ``compile-manifest.json``.

Ruling-E3: failure paths leave the staging directory in place but DO NOT
write ``compile-manifest.json``. Downstream tooling therefore cannot
identify the staging as a valid version.

Ruling-E2: ``{generated_at}`` and any time-based placeholder renders empty;
the compiler MUST NOT call ``datetime.now`` / ``time.time`` /
``os.urandom``. Manifest fields that name tool versions are explicitly
passed in by callers.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from concurrency_lock import LockBusy, acquire
from literal_scan import FrozenReference, literal_preflight_scan
from path_safety import assert_within_run_root
from preflight import preflight_skill, preflight_staging_directory
from skill_projector import project_skill


SIX_STAGES: tuple[str, ...] = (
    "write_entry",
    "scene_design",
    "character_beats",
    "prose_draft",
    "style_check",
    "revision",
)


class CompilerError(Exception):
    def __init__(self, message: str, *, error_type: str = "compiler_error") -> None:
        super().__init__(message)
        self.error_type = error_type


class ExistingStagingRootError(CompilerError):
    def __init__(self, message: str) -> None:
        super().__init__(message, error_type="existing_staging_root")


class PreflightError(CompilerError):
    pass


@dataclass
class CompileResult:
    manifest: dict
    staging_root: Path
    declared_files: dict[str, str]  # {relative_path: sha256}


def _utf8_lf_bytes(text: str) -> bytes:
    """Encode text as UTF-8 with LF line endings (spec §4.7)."""
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def _stage_id_mechanisms(bundle: dict, stage_id: str) -> list[str]:
    return sorted({
        m["mechanism_id"]
        for m in (bundle.get("mechanisms") or [])
        if m.get("stage_bindings") and stage_id in m["stage_bindings"]
        and m.get("mechanism_id")
    })


def _atomic_rename(src: Path, dst: Path) -> None:
    """Cross-platform atomic rename."""
    src.rename(dst)


def compile_six_skills(
    bundle: dict,
    *,
    templates_root: Path,
    staging_root: Path,
    lock_root: Path,
    lock_key: str = "wenfeng.compile",
    contract_version: str = "0.1.0",
    compiler_version: str = "0.1.0",
    schema_version: str = "0.2.0",
    template_version: str = "0.1.0",
    reference_corpus_for_literal_scan: str = "",
    long_substrings_for_literal_scan: Iterable[str] | None = None,
    min_continuous_match: int = 32,
) -> CompileResult:
    """Compile six Skills deterministically into ``staging_root``.

    Returns a populated ``CompileResult`` on success. On failure raises
    ``CompilerError`` after cleaning up the staging directory but never
    deleting it (Ruling-E3).
    """
    if not bundle or not isinstance(bundle, dict):
        raise CompilerError("bundle must be a non-empty JSON object")
    if "evidence_status" not in bundle:
        raise CompilerError("bundle missing 'evidence_status' field")

    staging_root = Path(staging_root).resolve()
    run_root = Path(lock_root).resolve()

    assert_within_run_root(run_root, staging_root)

    if staging_root.exists():
        if any(staging_root.iterdir()):
            raise ExistingStagingRootError(
                f"staging_root {staging_root} already exists and is non-empty"
            )
        # Empty dir is acceptable; fall through.

    handle = acquire(lock_root, lock_key, timeout_seconds=0.0)
    try:
        # Build into a sibling tempdir then atomic-rename on success.
        with tempfile.TemporaryDirectory(
            dir=run_root, prefix="compile-", suffix=".tmp"
        ) as tmp_str:
            tmp_root = Path(tmp_str)
            declared: dict[str, str] = {}
            body_by_stage: dict[str, str] = {}
            for stage_id in SIX_STAGES:
                mechanism_subset = _stage_id_mechanisms(bundle, stage_id)
                template_path = templates_root / f"{stage_id}.md"
                if not template_path.is_file():
                    raise CompilerError(
                        f"template missing for {stage_id}: {template_path}"
                    )
                projected = project_skill(
                    stage_id,
                    template_path,
                    mechanism_subset=mechanism_subset,
                    contract_version=contract_version,
                    bundle_id=bundle.get("bundle_id", bundle.get("source_id", "")),
                    manifest_version=schema_version,
                )
                body = projected.body
                # Static preflight on body.
                errors = preflight_skill(stage_id, body)
                if errors:
                    raise PreflightError(
                        f"preflight failed for {stage_id}: " + "; ".join(errors)
                    )
                # Literal scan (optional).
                if reference_corpus_for_literal_scan:
                    from literal_scan import freeze_reference_corpus
                    frozen = freeze_reference_corpus(
                        reference_corpus_for_literal_scan,
                        min_continuous_match=min_continuous_match,
                    )
                    lit_errors = literal_preflight_scan(
                        body, frozen,
                        long_substrings=list(long_substrings_for_literal_scan or []),
                    )
                    if lit_errors:
                        raise PreflightError(
                            f"literal scan failed for {stage_id}: " + "; ".join(lit_errors)
                        )
                # Write the Skill body to the temp staging.
                skill_dir = tmp_root / stage_id
                skill_dir.mkdir(parents=True, exist_ok=True)
                skill_md = skill_dir / "SKILL.md"
                skill_bytes = _utf8_lf_bytes(body)
                skill_md.write_bytes(skill_bytes)
                body_by_stage[stage_id] = body

            # Compute skill_hashes (sorted by stage_id).
            skill_hashes: dict[str, str] = {}
            for stage_id in SIX_STAGES:
                skill_md = tmp_root / stage_id / "SKILL.md"
                rel = skill_md.relative_to(tmp_root).as_posix()
                digest = hashlib.sha256(skill_md.read_bytes()).hexdigest()
                skill_hashes[stage_id] = digest
                declared[rel] = digest

            # Write compile-manifest.json into the temp staging.
            manifest = {
                "manifest_version": schema_version,
                "compiler_version": compiler_version,
                "schema_version": schema_version,
                "template_version": template_version,
                "source_id": bundle["source_id"],
                "bundle_id": bundle.get("bundle_id", bundle.get("source_id", "")),
                "skill_hashes": skill_hashes,
                "staging_path": "private-ledger://compile/" + staging_root.name,
            }
            manifest_bytes = _utf8_lf_bytes(json.dumps(manifest, ensure_ascii=False, indent=2))
            (tmp_root / "compile-manifest.json").write_bytes(manifest_bytes)
            declared["compile-manifest.json"] = hashlib.sha256(manifest_bytes).hexdigest()

            # Staging-directory preflight.
            errors = preflight_staging_directory(
                tmp_root, declared_files=declared, run_root=run_root
            )
            if errors:
                raise PreflightError("staging preflight failed: " + "; ".join(errors))

            # Move temp staging into the final staging_root. We delete the
            # empty staging_root first if it exists (empty dir case).
            if staging_root.exists():
                staging_root.rmdir()
            _atomic_rename(tmp_root, staging_root)
            return CompileResult(
                manifest=manifest,
                staging_root=staging_root,
                declared_files=declared,
            )
    finally:
        handle.release()


def validate_dist(
    staging_root: Path,
    *,
    run_root: Path,
    reference_corpus_for_literal_scan: str = "",
    long_substrings_for_literal_scan: Iterable[str] | None = None,
    min_continuous_match: int = 32,
) -> list[str]:
    """Validate a frozen staging against its declared ``compile-manifest.json``.

    Returns a list of error messages. Empty list = pass.
    """
    errors: list[str] = []
    manifest_path = staging_root / "compile-manifest.json"
    if not manifest_path.is_file():
        return [f"compile-manifest.json missing at {manifest_path}"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    declared_hashes = manifest.get("skill_hashes") or {}
    if sorted(declared_hashes.keys()) != sorted(SIX_STAGES):
        errors.append(
            f"manifest skill_hashes keys {sorted(declared_hashes.keys())} != {list(SIX_STAGES)}"
        )
    declared_paths = {}
    for stage_id in SIX_STAGES:
        skill_md = staging_root / stage_id / "SKILL.md"
        if not skill_md.is_file():
            errors.append(f"Skill file missing: {stage_id}/SKILL.md")
            continue
        actual_hash = hashlib.sha256(skill_md.read_bytes()).hexdigest()
        if actual_hash != declared_hashes.get(stage_id):
            errors.append(
                f"{stage_id}/SKILL.md hash mismatch: "
                f"declared {declared_hashes.get(stage_id, '')[:12]}… "
                f"actual {actual_hash[:12]}…"
            )
        declared_paths[f"{stage_id}/SKILL.md"] = actual_hash

    actual_manifest_hash = hashlib.sha256(
        _utf8_lf_bytes(
            json.dumps(manifest, ensure_ascii=False, indent=2)
        )
    ).hexdigest()

    declared_paths["compile-manifest.json"] = actual_manifest_hash
    errors.extend(
        preflight_staging_directory(
            staging_root,
            declared_files=declared_paths,
            run_root=run_root,
        )
    )

    # Per-Skill preflight.
    if reference_corpus_for_literal_scan:
        from literal_scan import freeze_reference_corpus
        frozen = freeze_reference_corpus(
            reference_corpus_for_literal_scan,
            min_continuous_match=min_continuous_match,
        )
    else:
        frozen = None

    for stage_id in SIX_STAGES:
        skill_md = staging_root / stage_id / "SKILL.md"
        if not skill_md.is_file():
            continue
        body = skill_md.read_text(encoding="utf-8")
        errors.extend(preflight_skill(stage_id, body))
        if frozen is not None:
            lit_errors = literal_preflight_scan(
                body, frozen,
                long_substrings=list(long_substrings_for_literal_scan or []),
            )
            errors.extend(lit_errors)
    return errors


__all__ = [
    "SIX_STAGES",
    "CompilerError",
    "ExistingStagingRootError",
    "PreflightError",
    "CompileResult",
    "compile_six_skills",
    "validate_dist",
]
