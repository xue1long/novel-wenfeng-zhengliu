"""Stage C Task 6: per-dimension extraction journal.

Wraps ``scripts/run_journal.RunJournal`` with the Stage C guarantees:

  - ``record_dimension_start`` refuses to run if the holdout set is not
    locked.
  - ``record_dimension_checkpoint`` is idempotent on ``(dimension, status)``.
  - Retry count is capped at 3 (spec §4.3 step 5).
  - ``record_dimension_failure`` preserves successful dimensions and only
    flips the failing dimension to a non-success status.
  - ``resume_pending_dimensions`` returns dimensions whose last checkpoint
    was not ``succeeded``.
"""

from __future__ import annotations

import json
from pathlib import Path

from run_journal import (
    HoldoutNotLockedError,
    RunJournal,
    StepRetryExhausted,
    _read_manifest,
)
from holdout import read_locked_holdout


_DIMENSION_KEY_PREFIX = "extract-"
_MAX_RETRY = 3


class ExtractionJournal:
    """Thin facade over RunJournal that speaks the stage C dimension vocabulary."""

    def __init__(
        self,
        run_root: Path,
        run_id: str,
        *,
        source_fingerprint: str,
        model_id: str = "synthetic-model",
    ) -> None:
        self.run_root = run_root
        self.run_id = run_id
        self._journal = RunJournal(
            run_root,
            run_id,
            source_fingerprint=source_fingerprint,
            model_id=model_id,
        )

    def ensure_holdout_locked(self) -> None:
        try:
            read_locked_holdout(self.run_root)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise HoldoutNotLockedError(
                f"a valid holdout lock is required before extracting: {exc}"
            ) from exc

    def record_dimension_start(self, dimension: str) -> None:
        self.ensure_holdout_locked()
        step_id = f"{_DIMENSION_KEY_PREFIX}{dimension}"
        self._journal.record_step(
            step_id,
            input_hash="0" * 64,
            prompt_template_version=f"{dimension}@0.1.0",
            model_id="pending",
            output_path=f"private-ledger://{self.run_id}/candidates/{dimension}.json",
            output_hash="0" * 64,
            status="pending",
            retry_count=0,
            error_type="",
        )

    def record_dimension_checkpoint(
        self,
        dimension: str,
        *,
        candidates_path: str,
        candidates_hash: str,
        status: str,
        retry_count: int,
    ) -> None:
        if retry_count > _MAX_RETRY:
            raise StepRetryExhausted(
                f"retry_count {retry_count} exceeds max {_MAX_RETRY} for dimension {dimension!r}"
            )
        step_id = f"{_DIMENSION_KEY_PREFIX}{dimension}"
        self._journal.record_step(
            step_id,
            input_hash="0" * 64,
            prompt_template_version=f"{dimension}@0.1.0",
            model_id="local",
            output_path=candidates_path,
            output_hash=candidates_hash,
            status=status,
            retry_count=retry_count,
            error_type="",
        )

    def record_dimension_failure(
        self,
        dimension: str,
        *,
        error_type: str,
        error_detail: str,
    ) -> None:
        step_id = f"{_DIMENSION_KEY_PREFIX}{dimension}"
        self._journal.record_step(
            step_id,
            input_hash="0" * 64,
            prompt_template_version=f"{dimension}@0.1.0",
            model_id="local",
            output_path=f"private-ledger://{self.run_id}/candidates/{dimension}.json",
            output_hash="0" * 64,
            status="failed",
            retry_count=0,
            error_type=error_type,
        )
        # Keep error_detail in a sidecar so we do not break run-manifest
        # schema's additionalProperties rule.
        sidecar_path = self.run_root / "extraction-failures.json"
        if sidecar_path.is_file():
            data = json.loads(sidecar_path.read_text(encoding="utf-8"))
        else:
            data = {}
        data[dimension] = {"error_type": error_type, "error_detail": error_detail}
        sidecar_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def resume_pending_dimensions(self, *, all_dimensions: list[str]) -> list[str]:
        """Return the dimensions whose last checkpoint was not ``succeeded``."""
        manifest = self._journal.load()
        last_status: dict[str, str] = {}
        for entry in manifest.get("step_log", []):
            sid = entry.get("step_id", "")
            if not sid.startswith(_DIMENSION_KEY_PREFIX):
                continue
            dimension = sid[len(_DIMENSION_KEY_PREFIX):]
            last_status[dimension] = entry.get("status", "pending")
        pending = [d for d in all_dimensions if last_status.get(d, "pending") != "succeeded"]
        return pending

    def set_status(self, status: str) -> None:
        self._journal.set_status(status)


__all__ = [
    "ExtractionJournal",
    "HoldoutNotLockedError",
    "StepRetryExhausted",
]
