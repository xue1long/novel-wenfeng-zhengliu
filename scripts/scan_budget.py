"""Stage B Task 7: scan budget estimator.

Spec anchor: §6 阶段 B 验收'预算估算可解释,窗口清单完整且可续跑'.

Ruling-4 pins the constants used here:
  - BATCH_WINDOW_CODEPOINTS must equal the model-budget-policy
    ``max_tokens_per_batch`` in tokens × TOKEN_CHARS_PER_TOKEN. Stage B
    fixes ``max_tokens_per_batch = 8000`` for the synthetic-model profile,
    giving ``8000 * 4 = 32000`` codepoints per batch.
  - TOKEN_CHARS_PER_TOKEN = 4 is the estimate agreed on for Stage B; it is
    an *explanation* knob, not a contract value.

Each numeric field in the resulting plan is derived directly from the
chunks + policy_version + these constants. There are no other magic numbers.
"""

from __future__ import annotations

import hashlib
from typing import Any


TOKEN_CHARS_PER_TOKEN: int = 4
BATCH_WINDOW_CODEPOINTS: int = 32000  # 8000 tokens * 4 chars/token.


class ScanBudgetIncompleteError(Exception):
    def __init__(self, missing: list[str]) -> None:
        super().__init__(f"scan budget inputs incomplete; missing: {missing}")
        self.missing = missing


def _chunk_codepoints(chunk) -> int:
    start, end = chunk.char_offset[0], chunk.char_offset[1]
    return end - start


def estimate_scan_budget(
    chunks,
    policy: dict,
    *,
    fingerprint: str,
    chunker_version: str,
) -> dict[str, Any]:
    missing: list[str] = []
    if not isinstance(policy, dict) or "policy_version" not in policy:
        missing.append("policy.policy_version")
    if not isinstance(policy, dict) or "overlimit_policy" not in policy:
        missing.append("policy.overlimit_policy")
    if not fingerprint:
        missing.append("fingerprint")
    if not chunker_version:
        missing.append("chunker_version")
    for index, chunk in enumerate(chunks):
        if not getattr(chunk, "chunk_id", None):
            missing.append(f"chunks[{index}].chunk_id")
    if missing:
        raise ScanBudgetIncompleteError(missing)

    total_codepoints = sum(_chunk_codepoints(c) for c in chunks)
    estimated_requests = -(-total_codepoints // BATCH_WINDOW_CODEPOINTS)
    estimated_tokens_total = total_codepoints // TOKEN_CHARS_PER_TOKEN
    estimated_tokens_per_batch = BATCH_WINDOW_CODEPOINTS // TOKEN_CHARS_PER_TOKEN

    windows = []
    for chunk in chunks:
        cid = chunk.chunk_id
        codepoints = _chunk_codepoints(chunk)
        # Deterministic window_id derived from chunk_id + fingerprint.
        window_id = "w-" + hashlib.sha256(
            (fingerprint + "|" + cid).encode("utf-8")
        ).hexdigest()[:12]
        windows.append({
            "window_id": window_id,
            "chunk_id": cid,
            "estimated_codepoints": codepoints,
            "estimated_tokens": codepoints // TOKEN_CHARS_PER_TOKEN,
            "char_offset": list(chunk.char_offset),
        })

    return {
        "policy_version": policy["policy_version"],
        "overlimit_policy": policy["overlimit_policy"],
        "fingerprint": fingerprint,
        "chunker_version": chunker_version,
        "windows": windows,
        "aggregate": {
            "total_codepoints": total_codepoints,
            "estimated_requests": estimated_requests,
            "estimated_tokens_total": estimated_tokens_total,
            "estimated_tokens_per_batch": estimated_tokens_per_batch,
            "batch_window_codepoints": BATCH_WINDOW_CODEPOINTS,
            "token_chars_per_token": TOKEN_CHARS_PER_TOKEN,
        },
    }


def resume_windows(plan: dict, *, completed_ids: set[str]) -> list[dict]:
    """Return the windows whose ``window_id`` is NOT in ``completed_ids``."""
    return [w for w in plan["windows"] if w["window_id"] not in completed_ids]


__all__ = [
    "TOKEN_CHARS_PER_TOKEN",
    "BATCH_WINDOW_CODEPOINTS",
    "ScanBudgetIncompleteError",
    "estimate_scan_budget",
    "resume_windows",
]