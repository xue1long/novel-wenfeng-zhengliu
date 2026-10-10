"""Cross-file reference validation for the Style Bundle.

The vendored Draft 2020-12 subset does not implement $id resolution across files.
Stage A still needs the rule "stage_bindings must reference existing mechanisms"
to be enforced somewhere deterministic, so it lives here as a read-only check.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


SIX_STAGES = [
    "write_entry",
    "scene_design",
    "character_beats",
    "prose_draft",
    "style_check",
    "revision",
]

FORBIDDEN_EXCLUSION_CATEGORIES = {
    "book_name",
    "author_name",
    "character_name",
    "location_name",
    "publisher_name",
    "source_title",
}


def validate_bundle_cross_refs(data: dict) -> list[str]:
    errors: list[str] = []
    mechanisms = data.get("mechanisms") or []
    known_ids = {
        m["mechanism_id"]
        for m in mechanisms
        if isinstance(m, dict) and isinstance(m.get("mechanism_id"), str)
    }

    stage_bindings = data.get("stage_bindings") or {}
    if not isinstance(stage_bindings, dict):
        errors.append("stage_bindings must be an object")
        return errors
    unknown_stages = set(stage_bindings.keys()) - set(SIX_STAGES)
    if unknown_stages:
        errors.append(
            f"stage_bindings includes unknown stages: {sorted(unknown_stages)}"
        )
    for stage, ids in stage_bindings.items():
        if stage not in SIX_STAGES:
            continue
        if not isinstance(ids, list):
            errors.append(f"stage_bindings[{stage}] must be a list")
            continue
        for mid in ids:
            if not re.fullmatch(r"M[0-9]{2,}", mid or ""):
                errors.append(
                    f"stage_bindings[{stage}] references malformed mechanism_id {mid!r}"
                )
                continue
            if mid not in known_ids:
                errors.append(
                    f"stage_bindings[{stage}] references missing mechanism: {mid}"
                )

    for index, exclusion in enumerate(data.get("content_exclusions") or []):
        if exclusion in FORBIDDEN_EXCLUSION_CATEGORIES:
            errors.append(
                f"content_exclusions[{index}]={exclusion!r} is source-specific; "
                "spec §4.4 forbids such categories in shareable bundles."
            )

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Cross-reference validation for a wenfeng Style Bundle.",
    )
    parser.add_argument("path", help="Path to a Style Bundle JSON file")
    args = parser.parse_args(argv)

    path = Path(args.path)
    try:
        with path.open("r", encoding="utf-8-sig") as handle:
            data = json.load(handle)
    except json.JSONDecodeError as error:
        print(f"invalid JSON at line {error.lineno}, column {error.colno}")
        return 2
    except OSError as error:
        print(f"could not read Bundle: {error.strerror or 'file access failed'}")
        return 2

    errors = validate_bundle_cross_refs(data)
    if errors:
        print("Style Bundle cross-references are invalid:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Style Bundle cross-references are valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())