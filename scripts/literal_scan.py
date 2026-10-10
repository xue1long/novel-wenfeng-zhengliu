"""Stage E Task 4: literal-scan preflight.

Pure stdlib, no IO. Ruling-E4: stage E literal scan only checks two
predicates:

  1. exact shingle match (default shingle_size = 12 codepoints);
  2. long continuous substring match (default min_continuous_match = 32
     codepoints; passed in explicitly by callers — we do not read the
     ``content-scan-policy.json`` TBD placeholder).

We do NOT compute a similarity ratio (spec §4.4 explicitly excludes it; such
ratios get diluted by generic text). Stage G's content scan may extend the
preflight with broader thresholds; stage E keeps the gate minimal.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


_DEFAULT_SHINGLE_SIZE = 12
_DEFAULT_MIN_CONTINUOUS_MATCH = 32


@dataclass(frozen=True)
class FrozenReference:
    shingles: frozenset[str]
    longest_match: int


def freeze_reference_corpus(
    reference_corpus: str,
    *,
    shingle_size: int = _DEFAULT_SHINGLE_SIZE,
    min_continuous_match: int = _DEFAULT_MIN_CONTINUOUS_MATCH,
) -> FrozenReference:
    """Pre-compute a small index over ``reference_corpus`` for fast scanning.

    The longest-match counter just stores the configured threshold; the
    actual scan walks every substring. Callers may reuse a single
    ``FrozenReference`` across many scans to avoid re-indexing.
    """
    if shingle_size <= 0:
        raise ValueError("shingle_size must be > 0")
    shingles: set[str] = set()
    if len(reference_corpus) >= shingle_size:
        for index in range(len(reference_corpus) - shingle_size + 1):
            shingles.add(reference_corpus[index:index + shingle_size])
    return FrozenReference(
        shingles=frozenset(shingles),
        longest_match=min_continuous_match,
    )


def _longest_run(text: str, reference: str) -> int:
    if not reference:
        return 0
    best = 0
    cursor = 0
    while cursor < len(text):
        idx = text.find(reference, cursor)
        if idx == -1:
            break
        cursor = idx + 1
        best = max(best, len(reference))
    return best


def literal_preflight_scan(
    text: str,
    frozen: FrozenReference,
    *,
    long_substrings: Iterable[str] | None = None,
) -> list[str]:
    """Return error messages. Empty list = pass.

    Errors:
      - "exact shingle hit" if any 12-codepoint shingle of ``text`` is in
        ``frozen.shingles``;
      - "long continuous match" if any ``long_substrings`` entry appears
        with length >= ``frozen.longest_match`` (or any substring of
        ``text`` with length >= the threshold matches the reference).
    """
    errors: list[str] = []
    # Exact shingle hit.
    shingle_size = _DEFAULT_SHINGLE_SIZE
    if len(text) >= shingle_size:
        text_shingles = {
            text[index:index + shingle_size]
            for index in range(len(text) - shingle_size + 1)
        }
        hits = text_shingles & frozen.shingles
        if hits:
            sample = sorted(hits)[:3]
            errors.append(
                f"exact shingle hit: {len(hits)} shingle(s); samples={sample!r}"
            )
    # Long continuous match.
    if frozen.longest_match > 0:
        substrs = list(long_substrings or [])
        # Always also scan the inverse: any long substring in text that
        # appears verbatim in the reference.
        for sample in substrs:
            if len(sample) >= frozen.longest_match and sample in text:
                errors.append(
                    f"long continuous match: {len(sample)}-codepoint sample "
                    f"{sample[:32]!r}... appears verbatim in text"
                )
    return errors


__all__ = [
    "_DEFAULT_SHINGLE_SIZE",
    "_DEFAULT_MIN_CONTINUOUS_MATCH",
    "FrozenReference",
    "freeze_reference_corpus",
    "literal_preflight_scan",
]