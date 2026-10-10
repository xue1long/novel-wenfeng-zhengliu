"""Stage G Task 1: final source-content scan.

Pure stdlib. Runs the same literal-scan used in stage E (Ruling-E4) over
the six Skill bodies and the eval-report inside a stage E/F staging.
Returns a coverage report and a per-skill scan result. Coverage below
``policy.coverage_target`` is a hard failure (spec §6 G acceptance bullet
"预算不足时可续跑，未覆盖不能标 ready").

The reference corpus is supplied by the caller; the script never reads
``source_id``-keyed source texts from disk directly (spec §4.3: source
texts live outside the project, only references are kept).
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from literal_scan import (
    _DEFAULT_MIN_CONTINUOUS_MATCH,
    _DEFAULT_SHINGLE_SIZE,
    freeze_reference_corpus,
    literal_preflight_scan,
)


# Targets we scan inside the staging root. Order is fixed so coverage
# scanning is deterministic.
SCAN_TARGETS: tuple[tuple[str, str], ...] = (
    ("write_entry", "write_entry/SKILL.md"),
    ("scene_design", "scene_design/SKILL.md"),
    ("character_beats", "character_beats/SKILL.md"),
    ("prose_draft", "prose_draft/SKILL.md"),
    ("style_check", "style_check/SKILL.md"),
    ("revision", "revision/SKILL.md"),
    ("eval-report", "eval-report.json"),
)


@dataclass
class SourceScanPolicy:
    policy_version: str
    shingle_size: int = _DEFAULT_SHINGLE_SIZE
    min_continuous_match: int = _DEFAULT_MIN_CONTINUOUS_MATCH
    total_budget_codepoints: int = 1_000_000
    coverage_target: float = 1.0  # default: no partial-coverage pass.

    def __post_init__(self) -> None:
        if not (0.0 <= self.coverage_target <= 1.0):
            raise SourceScanError(
                f"coverage_target must be in [0, 1], got {self.coverage_target}"
            )
        if self.total_budget_codepoints <= 0:
            raise SourceScanError("total_budget_codepoints must be > 0")

    @classmethod
    def default(cls) -> "SourceScanPolicy":
        return cls(policy_version="0.1.0")

    def to_dict(self) -> dict:
        return {
            "policy_version": self.policy_version,
            "shingle_size": self.shingle_size,
            "min_continuous_match": self.min_continuous_match,
            "total_budget_codepoints": self.total_budget_codepoints,
            "coverage_target": self.coverage_target,
        }


@dataclass
class SourceScanError(Exception):
    def __init__(self, message: str, *, error_type: str = "source_scan_error") -> None:
        super().__init__(message)
        self.error_type = error_type


def _stage_subdir_bytes(staging_root: Path) -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    for label, rel in SCAN_TARGETS:
        path = staging_root / rel
        if path.is_file():
            out[label] = path.read_bytes()
    return out


def final_source_scan(
    staging_root: Path,
    policy: SourceScanPolicy,
    *,
    reference_corpus: str = "",
    long_substrings: Iterable[str] | None = None,
) -> dict:
    """Run literal scan over the staging subdir and report coverage.

    Returns a dict with shape::

        {
          "policy_version": "...",
          "scanned_at_marker": "",
          "total_targets": 7,
          "covered_targets": 6,
          "coverage_ratio": 0.857,
          "coverage_target": 1.0,
          "skill_scan_results": {...},
          "report_scan_result": {...},
          "hashes": {...},
        }
    """
    if policy.shingle_size <= 0:
        raise SourceScanError("shingle_size must be > 0")
    if not (0.0 <= policy.coverage_target <= 1.0):
        raise SourceScanError("coverage_target must be in [0, 1]")
    contents = _stage_subdir_bytes(staging_root)
    if not contents:
        raise SourceScanError(f"staging_root {staging_root} contains no SKILL.md or eval-report")

    frozen = freeze_reference_corpus(
        reference_corpus,
        shingle_size=policy.shingle_size,
        min_continuous_match=policy.min_continuous_match,
    )
    coverage_codepoints = 0
    total_codepoints = 0
    skill_scan_results: dict[str, dict] = {}
    hashes: dict[str, str] = {}
    for label, rel in SCAN_TARGETS:
        path = staging_root / rel
        if not path.is_file():
            skill_scan_results[label] = {
                "path": rel, "status": "missing", "errors": [f"file missing: {rel}"],
            }
            continue
        text = contents[label].decode("utf-8", errors="replace")
        total_codepoints += len(text)
        if coverage_codepoints + len(text) <= policy.total_budget_codepoints:
            errors = literal_preflight_scan(
                text, frozen,
                long_substrings=list(long_substrings or []),
            )
            coverage_codepoints += len(text)
        else:
            errors = []
            skill_scan_results[label] = {
                "path": rel,
                "status": "out_of_budget",
                "errors": [
                    f"remaining budget {policy.total_budget_codepoints - coverage_codepoints} "
                    f"< target size {len(text)}; total_budget_codepoints exhausted"
                ],
            }
            hashes[label] = hashlib.sha256(contents[label]).hexdigest()
            continue
        skill_scan_results[label] = {
            "path": rel, "status": "scanned", "errors": errors,
        }
        hashes[label] = hashlib.sha256(contents[label]).hexdigest()

    coverage_ratio = coverage_codepoints / total_codepoints if total_codepoints else 0.0
    covered_targets = sum(
        1 for label, _ in SCAN_TARGETS
        if skill_scan_results.get(label, {}).get("status") == "scanned"
    )
    return {
        "policy": policy.to_dict(),
        "scanned_at_marker": "",  # Ruling-E2: no timestamp leak.
        "total_targets": len(SCAN_TARGETS),
        "covered_targets": covered_targets,
        "coverage_codepoints": coverage_codepoints,
        "total_codepoints": total_codepoints,
        "coverage_ratio": coverage_ratio,
        "coverage_target": policy.coverage_target,
        "skill_scan_results": skill_scan_results,
        "hashes": hashes,
    }


def evaluate_scan_coverage(scan: dict) -> list[str]:
    errors: list[str] = []
    coverage_ratio = scan.get("coverage_ratio", 0.0)
    coverage_target = scan.get("coverage_target", 1.0)
    if coverage_ratio < coverage_target:
        errors.append(
            f"coverage ratio {coverage_ratio:.3f} < target {coverage_target:.3f}"
        )
    for label, result in scan.get("skill_scan_results", {}).items():
        for err in result.get("errors", []):
            errors.append(f"{label}: {err}")
    return errors


def write_scan_report(scan: dict, target_dir: Path) -> Path:
    """Write the scan report as a stable, schema-free JSON sidecar."""
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / "source-scan-report.json"
    path.write_text(
        json.dumps(scan, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


__all__ = [
    "SCAN_TARGETS",
    "SourceScanPolicy",
    "SourceScanError",
    "final_source_scan",
    "evaluate_scan_coverage",
    "write_scan_report",
]