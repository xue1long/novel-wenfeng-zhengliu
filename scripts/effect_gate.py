"""Effect gate calculator (Stage A scaffold).

Spec §4.8 fixes the end-to-end effect gate. Stage A only ships the numeric
predicate so that downstream stages can be evaluated against a stable rule.
"""

from __future__ import annotations

import statistics
from typing import Any


MIN_PAIRS = 6
MIN_WINNING_PAIRS = 4
MIN_PAIRING_MEDIAN_DELTA = 0.5
MIN_STYLE_FIT_MEDIAN = 4.0
MIN_QUALITY_MEDIAN_DELTA = -0.5
DISAGREEMENT_THRESHOLD = 1.0


def _median(values: list[float]) -> float:
    return statistics.median(values) if values else 0.0


def evaluate_effect_gate(payload: dict[str, Any]) -> dict[str, Any]:
    pairs = payload.get("pairs") or []
    disagreement = payload.get("disagreement_per_dimension") or {}

    if len(pairs) < MIN_PAIRS:
        return {
            "verdict": "limited",
            "winning_pairs": 0,
            "style_fit_median": 0.0,
            "pairing_median_delta": 0.0,
            "quality_median_delta": 0.0,
            "undetermined_dimensions": [],
            "reason": f"need at least {MIN_PAIRS} pairs, got {len(pairs)}",
        }

    deltas: list[float] = []
    quality_deltas: list[float] = []
    style_fits: list[float] = []
    winning = 0
    for pair in pairs:
        sf_delta = pair["style_fit_six_stage"] - pair["style_fit_baseline"]
        q_delta = pair["quality_six_stage"] - pair["quality_baseline"]
        deltas.append(sf_delta)
        quality_deltas.append(q_delta)
        style_fits.append(pair["style_fit_six_stage"])
        if sf_delta > 0:
            winning += 1

    undetermined = [
        dim for dim, value in disagreement.items() if value > DISAGREEMENT_THRESHOLD
    ]

    pairing_median_delta = _median(deltas)
    quality_median_delta = _median(quality_deltas)
    style_fit_median = _median(style_fits)

    if undetermined:
        verdict = "limited"
    elif (
        winning >= MIN_WINNING_PAIRS
        and pairing_median_delta >= MIN_PAIRING_MEDIAN_DELTA
        and style_fit_median >= MIN_STYLE_FIT_MEDIAN
        and quality_median_delta >= MIN_QUALITY_MEDIAN_DELTA
    ):
        verdict = "pass"
    else:
        verdict = "limited"

    return {
        "verdict": verdict,
        "winning_pairs": winning,
        "style_fit_median": style_fit_median,
        "pairing_median_delta": pairing_median_delta,
        "quality_median_delta": quality_median_delta,
        "undetermined_dimensions": undetermined,
    }


__all__ = [
    "evaluate_effect_gate",
    "MIN_PAIRS",
    "MIN_WINNING_PAIRS",
    "MIN_PAIRING_MEDIAN_DELTA",
    "MIN_STYLE_FIT_MEDIAN",
    "MIN_QUALITY_MEDIAN_DELTA",
    "DISAGREEMENT_THRESHOLD",
]