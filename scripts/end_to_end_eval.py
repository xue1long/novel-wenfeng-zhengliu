"""Stage F Task 3: end-to-end blind evaluation framework.

Pure stdlib. Wraps the Stage A ``effect_gate.evaluate_effect_gate`` (spec §4.8
effect gates) and adds:

  - ``PairResult`` records the per-pair scores;
  - ``redact_eval_report`` strips private keys (``unblinding_map``,
    ``per_pair_unblinding_map``, ``pair_results`` raw text, ``rating_secrets``)
    and keeps the redacted aggregate summary + frozen hashes;
  - ``freeze_evaluation_artifacts`` hashes each Skill body and each case's
    generation text so the report can be cross-referenced later.

Spec §4.8 (4):
  - >= 6 pairs, >= 3 scenario classes;
  - same model version + generation params + total token budget for both
    sides of each pair;
  - baselines do NOT see the bundle or source text;
  - redacted mechanism rubric + writing constraints are what the raters
    see;
  - N=6 supports engineering release ONLY, not statistical claims.

Ruling-F6 keeps the threshold meanings honest in user-facing output.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from effect_gate import evaluate_effect_gate as _evaluate_effect_gate


SIX_STAGES: tuple[str, ...] = (
    "write_entry",
    "scene_design",
    "character_beats",
    "prose_draft",
    "style_check",
    "revision",
)


@dataclass
class PairResult:
    pair_id: str
    scenario_class: str
    baseline_score: float
    six_stage_score: float
    quality_baseline: float
    quality_six_stage: float
    disagreement_per_dimension: dict[str, float] = field(default_factory=dict)

    @property
    def style_fit_delta(self) -> float:
        return self.six_stage_score - self.baseline_score

    @property
    def quality_delta(self) -> float:
        return self.quality_six_stage - self.quality_baseline


# Private-field names that must NOT leave the unredacted eval-report.
_PRIVATE_REPORT_FIELDS = (
    "unblinding_map",
    "per_pair_unblinding_map",
    "pair_results",
    "rating_secrets",
    "per_pair_text",
    "per_pair_baseline_text",
    "per_pair_six_stage_text",
)


class RedactionError(Exception):
    def __init__(self, message: str, *, error_type: str = "redaction_error") -> None:
        super().__init__(message)
        self.error_type = error_type


def evaluate_effect_gate(
    pairs: list[PairResult],
    *,
    disagreement_per_dimension: dict[str, float] | None = None,
) -> dict:
    """Wrap stage A's effect gate over a list of ``PairResult``.

    The wrapper converts each ``PairResult`` into the flat dict shape the
    stage A gate expects.
    """
    payload = {
        "pairs": [
            {
                "style_fit_baseline": p.baseline_score,
                "style_fit_six_stage": p.six_stage_score,
                "quality_baseline": p.quality_baseline,
                "quality_six_stage": p.quality_six_stage,
            }
            for p in pairs
        ],
        "disagreement_per_dimension": disagreement_per_dimension or {},
    }
    return _evaluate_effect_gate(payload)


def redact_eval_report(report: dict, *, source_id: str, bundle_id: str) -> dict:
    """Strip private fields from a report; keep only the aggregate + hashes.

    Private fields (unblinding map, per-pair raw text, rating secrets, ...)
    are silently removed. The redaction metadata is appended to
    ``summary.notes`` (the only writable string field in the Stage A
    schema). Returns a NEW dict so the original is untouched.
    """
    if not isinstance(report, dict):
        raise RedactionError("report must be a JSON object")
    removed: list[str] = []
    public: dict = {}
    for key, value in report.items():
        if key in _PRIVATE_REPORT_FIELDS:
            removed.append(key)
        else:
            public[key] = value
    summary = public.setdefault("summary", {})
    if not isinstance(summary, dict):
        raise RedactionError("report.summary must be a JSON object")
    marker = (
        f"[redacted={source_id}/{bundle_id};"
        f"removed={','.join(removed)};"
        "timestamp=none]"
    )
    existing = summary.get("notes") or ""
    summary["notes"] = f"{existing}\n{marker}".strip() if existing else marker
    return public


def freeze_evaluation_artifacts(
    *,
    staging_root: Path,
    eval_generation_text: dict[str, str],
    report: dict,
) -> dict[str, str]:
    """Compute SHA-256 over each Skill body in staging + each eval case text.

    ``eval_generation_text`` maps ``{case_id: generated_text}``. The report
    is included whole so downstream tools can re-verify; in production we
    redact first. Returns a flat ``{relative_path_or_case_id: hex}`` map.

    The freezer sidecar (when present) is excluded so re-runs are
    idempotent.
    """
    out: dict[str, str] = {}
    excluded = {"eval-report.frozen-hashes.json"}
    for path in sorted(staging_root.rglob("*")):
        if path.is_file():
            rel = path.relative_to(staging_root).as_posix()
            if rel in excluded:
                continue
            out[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    for case_id in sorted(eval_generation_text.keys()):
        text = eval_generation_text[case_id]
        out[f"case:{case_id}"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
    report_bytes = json.dumps(report, ensure_ascii=False, sort_keys=True).encode("utf-8")
    out["report"] = hashlib.sha256(report_bytes).hexdigest()
    return out


__all__ = [
    "SIX_STAGES",
    "PairResult",
    "RedactionError",
    "evaluate_effect_gate",
    "redact_eval_report",
    "freeze_evaluation_artifacts",
]