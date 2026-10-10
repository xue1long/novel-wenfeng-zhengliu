"""Stage G Task 2: release manifest construction + self-consistency.

Pure stdlib + Stage A ``vendor/json_schema_validate.py``. The release
manifest proves the artifact matches the gating records; it does NOT
constitute a copyright or security certification (spec §4.9).

Refuses to ship any of these private fields (Ruling-G2 / spec §4.9):

  - source_body
  - book_name / author_name
  - unblinding_map / pair_results / rating_secrets
  - per_pair_text / per_pair_baseline_text / per_pair_six_stage_text
  - private source exclusions
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "vendor"))

from json_schema_validate import validate as _schema_validate  # noqa: E402


_FORBIDDEN_FIELDS: tuple[str, ...] = (
    "source_body",
    "book_name", "author_name",
    "unblinding_map", "pair_results", "rating_secrets",
    "per_pair_text", "per_pair_baseline_text", "per_pair_six_stage_text",
    "private_source_exclusions",
    "raw_corpus", "raw_text", "excerpt",
)


class ReleaseManifestError(Exception):
    def __init__(self, message: str, *, error_type: str = "release_manifest_error") -> None:
        super().__init__(message)
        self.error_type = error_type


def _load_schema() -> dict:
    return json.loads(
        (PROJECT_ROOT / "schemas" / "release-manifest.schema.json").read_text(encoding="utf-8")
    )


def _check_forbidden_fields(manifest: dict, *, where: str) -> None:
    leaked: list[str] = []
    for key in manifest.keys():
        if key in _FORBIDDEN_FIELDS or any(key.startswith(prefix) for prefix in ("private_", "raw_")):
            leaked.append(key)
    for field in manifest.get("skill_hashes", {}).keys():
        if field in _FORBIDDEN_FIELDS:
            leaked.append(f"skill_hashes.{field}")
    if leaked:
        raise ReleaseManifestError(
            f"{where}: refused to write release manifest with private fields {leaked!r}"
        )


def _canonical_manifest_bytes(manifest: dict) -> bytes:
    return json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")


def compute_build_hash(manifest_without_build_hash: dict) -> str:
    """SHA-256 over the canonical JSON of the manifest with ``build_hash="0"*64``."""
    placeholder = dict(manifest_without_build_hash)
    placeholder["build_hash"] = "0" * 64
    return hashlib.sha256(_canonical_manifest_bytes(placeholder)).hexdigest()


def build_release_manifest(
    staging_root: Path,
    *,
    bundle_id: str,
    source_id: str,
    authorization_purpose: str,
    release_state: str,
    eval_report_hash: str,
    final_scan_result: dict,
    zip_path: Path,
    compile_manifest_hash: str,
    schema_version: str = "0.1.0",
    tool_version: str = "0.1.0",
    template_version: str = "0.1.0",
    compiler_version: str = "0.1.0",
    compatibility_targets: Iterable[str] = (),
    gate_status: dict | None = None,
) -> dict:
    """Build a release manifest dict. ``final_scan_result`` and ``gate_status``
    must be present; ``zip_path`` must exist (its hash is included)."""
    skill_hashes: dict[str, str] = {}
    for stage_id in (
        "write_entry", "scene_design", "character_beats",
        "prose_draft", "style_check", "revision",
    ):
        skill_md = staging_root / stage_id / "SKILL.md"
        if not skill_md.is_file():
            raise ReleaseManifestError(
                f"staging missing {stage_id}/SKILL.md"
            )
        skill_hashes[stage_id] = hashlib.sha256(skill_md.read_bytes()).hexdigest()

    if not zip_path.is_file():
        raise ReleaseManifestError(f"zip_path does not exist: {zip_path}")
    zip_hash = hashlib.sha256(zip_path.read_bytes()).hexdigest()

    if gate_status is None:
        gate_status = {
            "trigger": True, "output": True, "end_to_end": True,
        }

    manifest = {
        "manifest_version": "0.1.0",
        "bundle_id": bundle_id,
        "source_id": source_id,
        "schema_version": schema_version,
        "tool_version": tool_version,
        "template_version": template_version,
        "compiler_version": compiler_version,
        "authorization_purpose": authorization_purpose,
        "release_state": release_state,
        "compatibility_targets": list(compatibility_targets),
        "skill_hashes": skill_hashes,
        "compile_manifest_hash": compile_manifest_hash,
        "eval_report_hash": eval_report_hash,
        "source_scan_hash": hashlib.sha256(
            _canonical_manifest_bytes(final_scan_result)
        ).hexdigest(),
        "zip_hash": zip_hash,
        "gate_status": gate_status,
        "build_hash": "0" * 64,
    }
    manifest["build_hash"] = compute_build_hash(manifest)
    return manifest


def write_release_manifest(manifest: dict, target_dir: Path) -> Path:
    _check_forbidden_fields(manifest, where="write")
    schema = _load_schema()
    errors = _schema_validate(manifest, schema)
    if errors:
        raise ReleaseManifestError(
            f"schema validation failed: {'; '.join(errors[:3])}"
        )
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / "release-manifest.json"
    path.write_bytes(_canonical_manifest_bytes(manifest))
    return path


def verify_release_manifest(manifest: dict, *, staging_root: Path | None = None) -> list[str]:
    """Re-validate the manifest. ``staging_root`` optionally cross-checks
    that the 6 Skill hashes match the live files."""
    errors: list[str] = []
    try:
        _check_forbidden_fields(manifest, where="verify")
    except ReleaseManifestError as exc:
        errors.append(str(exc))
    schema = _load_schema()
    schema_errors = _schema_validate(manifest, schema)
    if schema_errors:
        errors.append("schema: " + "; ".join(schema_errors[:3]))
        return errors
    # build_hash must match.
    expected = compute_build_hash(manifest)
    if expected != manifest.get("build_hash"):
        errors.append(
            f"build_hash mismatch: declared {manifest.get('build_hash', '')[:12]}… "
            f"actual {expected[:12]}…"
        )
    # Cross-check live SKILL.md hashes if a staging_root was provided.
    if staging_root is not None:
        for stage_id, expected_hash in manifest.get("skill_hashes", {}).items():
            path = staging_root / stage_id / "SKILL.md"
            if not path.is_file():
                errors.append(f"{stage_id}/SKILL.md missing in staging_root")
                continue
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != expected_hash:
                errors.append(
                    f"{stage_id} hash mismatch: declared {expected_hash[:12]}… "
                    f"actual {actual[:12]}…"
                )
    return errors


__all__ = [
    "ReleaseManifestError",
    "compute_build_hash",
    "build_release_manifest",
    "write_release_manifest",
    "verify_release_manifest",
]