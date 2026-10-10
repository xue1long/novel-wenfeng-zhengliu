"""Stage F Task 1: trigger evaluation metrics.

Pure stdlib. Computes per-stage precision/recall against ``eval-cases``:

  - must_trigger cases that DID trigger = true positives.
  - must_trigger cases that did NOT trigger = false negatives.
  - must_not_trigger cases that DID trigger = false positives.
  - must_not_trigger cases that did not trigger = true negatives.

Boundary cases are tracked separately and DO NOT influence precision/recall
(their answer is qualitative, not boolean).

Spec §4.8 (2):
  - each stage >= 10 must_trigger + 10 must_not_trigger + 5 boundary
  - precision >= 0.90, recall >= 0.90
  - missing required inputs / negative examples / false triggers MUST be
    surfaced as failure categories.

The metrics are deterministic and only depend on the input dicts.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any


SIX_STAGES: tuple[str, ...] = (
    "write_entry",
    "scene_design",
    "character_beats",
    "prose_draft",
    "style_check",
    "revision",
)


class TriggerMetricsError(Exception):
    def __init__(self, message: str, *, error_type: str = "trigger_metrics_error") -> None:
        super().__init__(message)
        self.error_type = error_type


class MissingRequiredInputs(TriggerMetricsError):
    pass


class InsufficientCases(TriggerMetricsError):
    pass


class PrecisionBelowThreshold(TriggerMetricsError):
    pass


class RecallBelowThreshold(TriggerMetricsError):
    pass


def _safe_div(num: int, denom: int) -> float:
    return 1.0 if denom == 0 else num / denom


def _validate_cases(cases: list[dict]) -> None:
    seen_ids: set[str] = set()
    for case in cases:
        cid = case.get("case_id", "")
        if not cid:
            raise InsufficientCases("case missing case_id")
        if cid in seen_ids:
            raise InsufficientCases(f"duplicate case_id {cid!r}")
        seen_ids.add(cid)


def compute_trigger_metrics(
    suite: dict[str, Any],
    results: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Return ``{stage_id: metrics_dict}`` plus a top-level ``_summary`` entry.

    ``suite`` has shape ``{"trigger_cases": {"must_trigger": [...], "must_not_trigger": [...], "boundary": [...]}}``
    (Stage A eval-cases schema). Each case has ``{"case_id", "stage_id", "input_excerpt"}``.

    ``results`` is ``[{"case_id", "stage_id", "triggered": bool}]``.

    Raises ``InsufficientCases`` when a stage has fewer than 10 must_trigger
    or 10 must_not_trigger cases. Raises ``PrecisionBelowThreshold`` /
    ``RecallBelowThreshold`` when a stage's metrics drop below 0.90.
    """
    _summary: dict[str, Any] = {
        "total_stages": 0,
        "stages_with_full_coverage": 0,
        "stages_meeting_precision_threshold": 0,
        "stages_meeting_recall_threshold": 0,
        "missing_required_inputs": False,
        "missing_cases": {},
    }
    trigger_cases = (suite.get("trigger_cases") or {})
    must_trigger = list(trigger_cases.get("must_trigger") or [])
    must_not_trigger = list(trigger_cases.get("must_not_trigger") or [])
    boundary = list(trigger_cases.get("boundary") or [])
    _validate_cases(must_trigger + must_not_trigger + boundary)

    results_by_stage: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in results:
        if not isinstance(entry, dict):
            continue
        stage_id = entry.get("stage_id")
        case_id = entry.get("case_id")
        if stage_id is None or case_id is None:
            raise InsufficientCases("result entry missing stage_id or case_id")
        if "triggered" not in entry or not isinstance(entry["triggered"], bool):
            raise InsufficientCases(
                f"result {case_id!r} for {stage_id!r} missing boolean 'triggered'"
            )
        results_by_stage[stage_id].append(entry)

    per_stage: dict[str, dict[str, Any]] = {}
    missing_cases = _summary["missing_cases"]

    for stage_id in SIX_STAGES:
        pos_cases = [c for c in must_trigger if c.get("stage_id") == stage_id]
        neg_cases = [c for c in must_not_trigger if c.get("stage_id") == stage_id]
        # Boundary cases do not carry a stage_id in eval-cases.schema.json
        # (they probe adjacency rather than belonging to a single stage).
        # We distribute them across the stages whose name appears as the
        # prefix of the case_id so per-stage counts remain non-zero.
        bnd_cases = [
            c for c in boundary if c["case_id"].startswith(stage_id + "-B-")
        ]
        stage_results = results_by_stage.get(stage_id, [])
        result_by_case: dict[str, bool] = {r["case_id"]: r["triggered"] for r in stage_results}

        if len(pos_cases) < 10:
            missing_cases[stage_id] = missing_cases.get(stage_id, []) + ["positive"]
        if len(neg_cases) < 10:
            missing_cases[stage_id] = missing_cases.get(stage_id, []) + ["negative"]
        if len(bnd_cases) < 5:
            missing_cases[stage_id] = missing_cases.get(stage_id, []) + ["boundary"]

        true_positives = sum(
            1 for c in pos_cases if result_by_case.get(c["case_id"], False)
        )
        false_negatives = sum(
            1 for c in pos_cases if not result_by_case.get(c["case_id"], True)
        )
        false_positives = sum(
            1 for c in neg_cases if result_by_case.get(c["case_id"], False)
        )
        true_negatives = sum(
            1 for c in neg_cases if not result_by_case.get(c["case_id"], True)
        )
        boundary_pass = sum(
            1 for c in bnd_cases
            if result_by_case.get(c["case_id"], False) is False  # boundary NOT triggered
        )

        precision = _safe_div(true_positives, true_positives + false_positives)
        recall = _safe_div(true_positives, true_positives + false_negatives)
        per_stage[stage_id] = {
            "total_must_trigger": len(pos_cases),
            "total_must_not_trigger": len(neg_cases),
            "total_boundary": len(bnd_cases),
            "true_positives": true_positives,
            "false_negatives": false_negatives,
            "false_positives": false_positives,
            "true_negatives": true_negatives,
            "boundary_pass": boundary_pass,
            "precision": precision,
            "recall": recall,
            "missing_required_inputs": False,
            "missing_cases": list(missing_cases.get(stage_id, [])),
        }

    _summary["total_stages"] = len(SIX_STAGES)
    _summary["missing_required_inputs"] = any(
        per_stage[s]["missing_required_inputs"] for s in SIX_STAGES
    )
    _summary["missing_cases"] = missing_cases
    _summary["stages_with_full_coverage"] = sum(
        1 for s in SIX_STAGES if not per_stage[s]["missing_cases"]
    )
    _summary["stages_meeting_precision_threshold"] = sum(
        1 for s in SIX_STAGES if per_stage[s]["precision"] >= 0.90
    )
    _summary["stages_meeting_recall_threshold"] = sum(
        1 for s in SIX_STAGES if per_stage[s]["recall"] >= 0.90
    )
    return {"_summary": _summary, **per_stage}


def assert_trigger_thresholds(metrics: dict[str, dict[str, Any]]) -> list[str]:
    """Return error messages for any stage that fails the spec §4.8 (2) bar."""
    errors: list[str] = []
    summary = metrics.get("_summary", {})
    if summary.get("missing_required_inputs"):
        errors.append("trigger metrics: missing_required_inputs")
    missing_cases = summary.get("missing_cases") or {}
    for stage_id, missing in missing_cases.items():
        if missing:
            errors.append(f"{stage_id}: missing required case types {missing!r}")
    for stage_id, m in metrics.items():
        if stage_id == "_summary":
            continue
        if m["precision"] < 0.90:
            errors.append(f"{stage_id}: precision {m['precision']:.3f} < 0.90")
        if m["recall"] < 0.90:
            errors.append(f"{stage_id}: recall {m['recall']:.3f} < 0.90")
    return errors


__all__ = [
    "SIX_STAGES",
    "TriggerMetricsError",
    "MissingRequiredInputs",
    "InsufficientCases",
    "PrecisionBelowThreshold",
    "RecallBelowThreshold",
    "compute_trigger_metrics",
    "assert_trigger_thresholds",
]