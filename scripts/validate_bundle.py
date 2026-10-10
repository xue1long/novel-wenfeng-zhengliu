"""Structural checks for a wenfeng-distill Style Bundle."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


SOURCE_ID_RE = re.compile(r"^[0-9a-f]{12}$")
ALLOWED_EVIDENCE_STATUSES = {"ready", "limited"}
ALLOWED_DECISION_STATUSES = {"model_approved", "model_limited"}
TOP_LEVEL_FIELDS = {
    "schema_version",
    "source_id",
    "evidence_status",
    "claimed_dimensions",
    "mechanisms",
    "content_exclusions",
    "evaluation_ref",
}
MECHANISM_FIELDS = {
    "mechanism_id",
    "dimension",
    "rule",
    "actions",
    "scope",
    "evidence",
    "counterexamples",
    "decision_status",
    "decision_reason",
}


def _nonempty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _validate_reference(
    reference: Any, location: str, errors: list[str], *, require_note: bool = False
) -> tuple[str | None, str | None]:
    if not isinstance(reference, dict):
        errors.append(f"{location} must be an object")
        return None, None

    scene_id = reference.get("scene_id")
    chapter_id = reference.get("chapter_id")
    if not _nonempty_text(scene_id):
        errors.append(f"{location}.scene_id must be a non-empty string")
        scene_id = None
    if not _nonempty_text(chapter_id):
        errors.append(f"{location}.chapter_id must be a non-empty string")
        chapter_id = None

    lines = reference.get("lines")
    if (
        not isinstance(lines, list)
        or len(lines) != 2
        or any(type(line) is not int for line in lines)
        or lines[0] < 1
        or lines[1] < lines[0]
    ):
        errors.append(f"{location}.lines must be a positive [start, end] line range")

    if require_note and not _nonempty_text(reference.get("note")):
        errors.append(f"{location}.note must be a non-empty string")

    return scene_id, chapter_id


def validate_bundle(data: Any) -> list[str]:
    """Return structural/evidence-threshold errors; do not inspect source semantics."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["root must be a JSON object"]

    for field in sorted(TOP_LEVEL_FIELDS - data.keys()):
        errors.append(f"missing required field: {field}")

    if data.get("schema_version") != "1":
        errors.append('schema_version must equal "1"')

    source_id = data.get("source_id")
    if not isinstance(source_id, str) or SOURCE_ID_RE.fullmatch(source_id) is None:
        errors.append("source_id must be exactly 12 lowercase hexadecimal characters")

    evidence_status = data.get("evidence_status")
    if not isinstance(evidence_status, str) or evidence_status not in ALLOWED_EVIDENCE_STATUSES:
        errors.append('evidence_status must be "ready" or "limited"')

    claimed_dimensions = data.get("claimed_dimensions")
    if not isinstance(claimed_dimensions, list) or not claimed_dimensions:
        errors.append("claimed_dimensions must be a non-empty list")
        claimed_dimensions = []
    elif any(not _nonempty_text(dimension) for dimension in claimed_dimensions):
        errors.append("claimed_dimensions entries must be non-empty strings")
        claimed_dimensions = [d for d in claimed_dimensions if _nonempty_text(d)]
    if len(set(claimed_dimensions)) != len(claimed_dimensions):
        errors.append("claimed_dimensions must not contain duplicates")

    if not isinstance(data.get("content_exclusions"), list):
        errors.append("content_exclusions must be a list")
    elif any(not isinstance(item, str) for item in data["content_exclusions"]):
        errors.append("content_exclusions entries must be strings")

    if not _nonempty_text(data.get("evaluation_ref")):
        errors.append("evaluation_ref must be a non-empty string")

    mechanisms = data.get("mechanisms")
    if not isinstance(mechanisms, list) or not mechanisms:
        errors.append("mechanisms must contain at least one mechanism")
        mechanisms = []

    seen_ids: set[str] = set()
    approved_dimensions: set[str] = set()

    for index, mechanism in enumerate(mechanisms):
        location = f"mechanisms[{index}]"
        if not isinstance(mechanism, dict):
            errors.append(f"{location} must be an object")
            continue

        for field in sorted(MECHANISM_FIELDS - mechanism.keys()):
            errors.append(f"{location} is missing required field: {field}")

        mechanism_id = mechanism.get("mechanism_id")
        if not _nonempty_text(mechanism_id):
            errors.append(f"{location}.mechanism_id must be a non-empty string")
        elif mechanism_id in seen_ids:
            errors.append(f"{location} has duplicate mechanism_id: {mechanism_id}")
        else:
            seen_ids.add(mechanism_id)

        dimension = mechanism.get("dimension")
        if not _nonempty_text(dimension):
            errors.append(f"{location}.dimension must be a non-empty string")
        elif dimension not in claimed_dimensions:
            errors.append(f"{location}.dimension must appear in claimed_dimensions")

        for field in ("rule", "scope", "decision_reason"):
            if not _nonempty_text(mechanism.get(field)):
                errors.append(f"{location}.{field} must be a non-empty string")

        actions = mechanism.get("actions")
        if not isinstance(actions, list) or not actions or any(not _nonempty_text(x) for x in actions):
            errors.append(f"{location}.actions must be a non-empty list of strings")

        status = mechanism.get("decision_status")
        if not isinstance(status, str) or status not in ALLOWED_DECISION_STATUSES:
            errors.append(f"{location}.decision_status must be model_approved or model_limited")

        evidence = mechanism.get("evidence")
        scene_ids: set[str] = set()
        chapter_ids: set[str] = set()
        if not isinstance(evidence, list) or not evidence:
            errors.append(f"{location}.evidence must be a non-empty list")
            evidence = []
        for evidence_index, reference in enumerate(evidence):
            scene_id, chapter_id = _validate_reference(
                reference, f"{location}.evidence[{evidence_index}]", errors
            )
            if scene_id is not None:
                scene_ids.add(scene_id)
            if chapter_id is not None:
                chapter_ids.add(chapter_id)

        counterexamples = mechanism.get("counterexamples")
        if not isinstance(counterexamples, list) or not counterexamples:
            errors.append(f"{location}.counterexamples must be a non-empty list")
            counterexamples = []
        for counterexample_index, reference in enumerate(counterexamples):
            _validate_reference(
                reference,
                f"{location}.counterexamples[{counterexample_index}]",
                errors,
                require_note=True,
            )

        if status == "model_approved":
            if len(scene_ids) < 3 or len(chapter_ids) < 2:
                errors.append(
                    f"{location} model_approved requires at least 3 unique scenes across 2 chapters"
                )
            elif _nonempty_text(dimension):
                approved_dimensions.add(dimension)
        elif status == "model_limited" and len(scene_ids) < 2:
            errors.append(f"{location} model_limited requires at least 2 unique scenes")

    if evidence_status == "ready":
        uncovered = set(claimed_dimensions) - approved_dimensions
        if uncovered:
            errors.append(
                "ready Bundle requires a model_approved mechanism for every claimed dimension: "
                + ", ".join(sorted(uncovered))
            )

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check Style Bundle structure and declared evidence thresholds."
    )
    parser.add_argument("path", help="Path to a Style Bundle JSON file")
    args = parser.parse_args(argv)

    bundle_path = Path(args.path)
    try:
        with bundle_path.open("r", encoding="utf-8-sig") as handle:
            data = json.load(handle)
    except json.JSONDecodeError as error:
        print(f"invalid JSON at line {error.lineno}, column {error.colno}")
        return 2
    except OSError as error:
        print(f"could not read Bundle: {error.strerror or 'file access failed'}")
        return 2

    errors = validate_bundle(data)
    if errors:
        print("Style Bundle is invalid:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Style Bundle structure and declared evidence thresholds are valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
