"""Stage B Task 6: run journal + idempotent step records.

Writes the canonical ``run-manifest.json`` at the run root and updates it
on every ``record_step`` call. The schema is the Stage A
``run-manifest.schema.json``; the helper here only handles the Stage-B
guarantees: idempotency per ``step_id`` and a hard ``retry_count`` cap of 3.

The journal will not record any ``extract-*`` step until the holdout has
been locked (spec §4.2: '在提取前封存场景 ID 与来源定位').
"""

from __future__ import annotations

import json
import re
import secrets
from pathlib import Path

from state_machine import STATES
from holdout import read_locked_holdout


class RunJournalError(Exception):
    error_type = "run_journal"

    def __init__(self, message: str) -> None:
        super().__init__(message)


class HoldoutNotLockedError(RunJournalError):
    error_type = "holdout_not_locked"


class StepRetryExhausted(RunJournalError):
    error_type = "step_retry_exhausted"


_MAX_RETRY = 3
_POLICY_PATH = Path(__file__).resolve().parents[1] / "policies" / "model-budget-policy.json"


def _read_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_policy_profile(model_id: str) -> tuple[str, dict]:
    """Return (policy_version, profile) for the requested model."""
    if not _POLICY_PATH.is_file():
        raise FileNotFoundError(f"model-budget-policy.json missing at {_POLICY_PATH}")
    policy = json.loads(_POLICY_PATH.read_text(encoding="utf-8"))
    profile = policy["profiles"][model_id]
    return policy["policy_version"], profile


class RunJournal:
    """Append/update step records inside a run root.

    The journal owns ``run-manifest.json`` and requires a valid persisted
    holdout before recording extraction steps.
    """

    def __init__(
        self,
        run_root: Path,
        run_id: str,
        *,
        source_fingerprint: str,
        source_id: str | None = None,
        model_id: str = "synthetic-model",
        parser_version: str = "wenfeng-prepare-source/0.1.0",
    ) -> None:
        self.run_root = run_root
        self.run_id = run_id
        self.manifest_path = run_root / "run-manifest.json"
        self.config_path = run_root / "run-config.json"
        policy_version, profile = _load_policy_profile(model_id)
        self._initialize_manifest(
            source_fingerprint=source_fingerprint,
            source_id=source_id,
            parser_version=parser_version,
            policy_version=policy_version,
            profile=profile,
        )
    def _initialize_manifest(
        self,
        *,
        source_fingerprint: str,
        source_id: str | None,
        parser_version: str,
        policy_version: str,
        profile: dict,
    ) -> None:
        if self.manifest_path.is_file():
            return
        resolved_source_id = source_id or secrets.token_hex(6)
        if not re.fullmatch(r"[0-9a-f]{12}", resolved_source_id):
            raise ValueError("source_id must be 12 lowercase hexadecimal characters")
        data = {
            "run_id": self.run_id,
            "source_id": resolved_source_id,
            "run_model_budget_policy_version": policy_version,
            "scan_budget": {
                "max_requests": profile["max_requests"],
                "max_input_tokens_total": profile["max_input_tokens_total"],
                "max_tokens_per_batch": profile["max_tokens_per_batch"],
                "overlimit_policy": profile["overlimit_policy"],
            },
            "status": "incomplete",
            "step_log": [],
        }
        self.manifest_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        # Sidecar carries the parser_version without violating the Stage A
        # schema's ``additionalProperties: false`` rule on run-manifest.
        sidecar = {
            "parser_version": parser_version,
            "source_fingerprint": source_fingerprint,
            "normalizer_version": "v1",
        }
        (self.run_root / "run-config.json").write_text(
            json.dumps(sidecar, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def lock_holdout(self) -> None:
        """Confirm that a real, input-matched holdout lock exists."""
        try:
            read_locked_holdout(self.run_root)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise HoldoutNotLockedError(str(exc)) from exc

    def record_step(
        self,
        step_id: str,
        *,
        input_hash: str,
        prompt_template_version: str,
        model_id: str,
        output_path: str,
        output_hash: str,
        status: str,
        retry_count: int = 0,
        error_type: str = "",
    ) -> None:
        if retry_count > _MAX_RETRY:
            raise StepRetryExhausted(
                f"retry_count {retry_count} exceeds max {_MAX_RETRY} for step {step_id!r}"
            )
        if step_id.startswith("extract"):
            try:
                read_locked_holdout(self.run_root)
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                raise HoldoutNotLockedError(
                    f"step {step_id!r} requires a valid holdout lock: {exc}"
                ) from exc

        data = _read_manifest(self.manifest_path)
        existing = next((s for s in data["step_log"] if s["step_id"] == step_id), None)
        record = {
            "step_id": step_id,
            "input_hash": input_hash,
            "prompt_template_version": prompt_template_version,
            "model_id": model_id,
            "output_path": output_path,
            "output_hash": output_hash,
            "status": status,
            "retry_count": retry_count,
            "error_type": error_type,
        }
        if existing is None:
            data["step_log"].append(record)
        else:
            existing.update(record)
        self.manifest_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def set_status(self, status: str) -> None:
        if status not in STATES:
            raise ValueError(f"status must be one of {STATES}, got {status!r}")
        data = _read_manifest(self.manifest_path)
        data["status"] = status
        self.manifest_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def load(self) -> dict:
        return _read_manifest(self.manifest_path)


__all__ = [
    "RunJournal",
    "RunJournalError",
    "HoldoutNotLockedError",
    "StepRetryExhausted",
    "_read_manifest",
]
