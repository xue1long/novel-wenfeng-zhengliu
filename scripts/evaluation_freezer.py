"""Stage F Task 5: evaluation freezer + redacted report writer.

Pure stdlib. Writes ``eval-suite.json`` / ``eval-cases.json`` /
``eval-report.json`` under a Stage E ``staging_root`` (read-only; we do not
modify any Skill body).

``eval-suite.json`` shape (Stage A schema):
  - ``suite_version``, ``policy_version``, ``model``, ``prompt_version``,
    ``tool_version``, ``case_version``, ``generation_params``, ``budget``,
    ``entries`` (one per case with model_id, prompt_version, generation
    params, budget, input/output hash, completion status).

``eval-cases.json`` shape:
  - ``case_version``, ``trigger_cases`` (must_trigger / must_not_trigger /
    boundary), ``output_cases`` (kind enum), ``end_to_end_pairs``
    (each with brief / scenario_class / scores).

``eval-report.json`` shape:
  - ``report_version``, ``bundle_id``, ``gate_results``, ``summary``,
    ``frozen_hashes``.

Each writer validates against Stage A's schema. ``write_eval_report``
accepts a ``redacted=True`` flag and uses ``end_to_end_eval.redact_eval_report``
to strip private fields before writing.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from end_to_end_eval import freeze_evaluation_artifacts, redact_eval_report

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "vendor"))

from json_schema_validate import validate as _schema_validate  # noqa: E402


class FreezerError(Exception):
    def __init__(self, message: str, *, error_type: str = "freezer_error") -> None:
        super().__init__(message)
        self.error_type = error_type


def _load_schema(name: str) -> dict:
    return json.loads(
        (PROJECT_ROOT / "schemas" / name).read_text(encoding="utf-8")
    )


def _validate(instance: dict, schema: dict, *, where: str) -> None:
    errors = _schema_validate(instance, schema)
    if errors:
        joined = "; ".join(errors[:3])
        raise FreezerError(f"{where}: schema validation failed: {joined}")


def write_eval_suite(staging_root: Path, suite: dict) -> Path:
    _validate(suite, _load_schema("eval-suite.schema.json"), where="eval-suite")
    path = staging_root / "eval-suite.json"
    path.write_text(
        json.dumps(suite, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def write_eval_cases(staging_root: Path, cases: dict) -> Path:
    _validate(cases, _load_schema("eval-cases.schema.json"), where="eval-cases")
    path = staging_root / "eval-cases.json"
    path.write_text(
        json.dumps(cases, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def write_eval_report(
    staging_root: Path,
    report: dict,
    *,
    source_id: str = "",
    bundle_id: str = "",
    redacted: bool = True,
) -> Path:
    if redacted:
        if not source_id or not bundle_id:
            raise FreezerError(
                "redacted=True requires source_id and bundle_id"
            )
        report = redact_eval_report(
            report, source_id=source_id, bundle_id=bundle_id
        )
    _validate(report, _load_schema("eval-report.schema.json"), where="eval-report")
    path = staging_root / "eval-report.json"
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def freeze_all_artifacts(
    staging_root: Path,
    *,
    eval_generation_text: dict[str, str],
    report: dict,
) -> dict[str, str]:
    """Compute frozen hashes and persist them to a sidecar.

    Stage A's ``eval-report.schema.json`` does NOT allow additional
    top-level properties (Ruling-F2: do not modify stage A schemas). We
    therefore write ``frozen_hashes`` to ``staging_root/eval-report.frozen-hashes.json``
    so the on-disk report stays schema-valid.
    """
    hashes = freeze_evaluation_artifacts(
        staging_root=staging_root,
        eval_generation_text=eval_generation_text,
        report=report,
    )
    sidecar = staging_root / "eval-report.frozen-hashes.json"
    sidecar.write_text(
        json.dumps(hashes, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return hashes


__all__ = [
    "FreezerError",
    "write_eval_suite",
    "write_eval_cases",
    "write_eval_report",
    "freeze_all_artifacts",
]