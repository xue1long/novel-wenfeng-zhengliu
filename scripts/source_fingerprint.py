"""Stage B Task 2: source fingerprint + normalizer.

Pure stdlib. The fingerprint is ``sha256(normalizer_version || "\\0" || utf8(normalized))``.
Stage B locks the normalizer rules here; any change MUST bump ``normalizer_version``.
"""

from __future__ import annotations

import hashlib
from typing import Final


PARSER_VERSION: Final[str] = "wenfeng-prepare-source/0.1.0"

_ZERO_WIDTH = ("\u200b", "\u200c", "\u200d", "\ufeff")


def normalize(text: str, *, normalizer_version: str = "v1") -> str:
    """Apply Stage B's locked normalization rules.

    Rules (do not change without bumping ``normalizer_version``):
      - BOM (\ufeff) stripped from the leading position.
      - Zero-width joiners (\u200b–\u200d) removed anywhere.
      - CRLF / CR line endings collapsed to LF.
      - Trailing whitespace on every line stripped.
    Other content (punctuation, CJK, emoji, control characters not listed
    above) is preserved verbatim.
    """
    if text.startswith("\ufeff"):
        text = text[1:]
    for zw in _ZERO_WIDTH:
        if text.startswith(zw):
            text = text[len(zw):]
    for zw in _ZERO_WIDTH:
        text = text.replace(zw, "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    return "\n".join(lines)


def fingerprint_bytes(data: bytes, *, encoding: str = "utf-8") -> str:
    """SHA-256 hex of raw bytes (the canonical on-disk source)."""
    if encoding != "utf-8":
        raise ValueError(f"Stage B only supports utf-8; got {encoding!r}")
    return hashlib.sha256(data).hexdigest()


def fingerprint_text(text: str, *, normalizer_version: str = "v1") -> str:
    """SHA-256 hex of ``(normalizer_version, normalized text)``.

    The version tag is hashed *together with* the text so that bumping the
    normalizer naturally changes every digest, which is what downstream
    invalidation rules rely on (spec §4.2).
    """
    normalized = normalize(text, normalizer_version=normalizer_version)
    payload = normalizer_version.encode("utf-8") + b"\x00" + normalized.encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


__all__ = ["PARSER_VERSION", "normalize", "fingerprint_bytes", "fingerprint_text"]