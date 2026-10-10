"""Stage E Task 2: deterministic Skill projector.

Reads a Stage D ``templates/stages/<stage_id>.md`` file and produces a
``ProjectedSkill`` whose body has all ``{placeholder}`` markers substituted.
The output is byte-stable: identical inputs MUST produce identical bytes.

Placeholders (locked at the top of this file):
    {stage_id}              -> the stage id (sanity)
    {contract_version}      -> the contract version
    {mechanism_ids}         -> sorted mechanism ids joined with ", "
    {bundle_id}             -> bundle id (or empty if not provided)
    {generated_at}          -> ALWAYS empty (spec §4.7 "no generation time")
    {manifest_version}      -> compile-manifest version

Ruling-E2 forbids any non-deterministic substitution. ``os.urandom`` /
``time.time`` / ``uuid.uuid4`` MUST NOT appear in the substitution path.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from skill_template import REQUIRED_BODY_SECTIONS, parse_template


PLACEHOLDER_RE = re.compile(r"\{([a-z_]+)\}")

_VALID_PLACEHOLDERS: frozenset[str] = frozenset({
    "stage_id", "contract_version", "mechanism_ids", "bundle_id",
    "generated_at", "manifest_version",
})


@dataclass(frozen=True)
class ProjectedSkill:
    stage_id: str
    file_name: str  # always "SKILL.md" in Stage E
    body: str  # post-substitution markdown bytes-as-text
    required_mechanism_ids: list[str]


def project_skill(
    stage_id: str,
    template_path: Path,
    *,
    mechanism_subset: list[str] | None = None,
    contract_version: str = "0.1.0",
    bundle_id: str = "",
    manifest_version: str = "0.1.0",
) -> ProjectedSkill:
    parsed = parse_template(template_path)
    if parsed.frontmatter["stage_id"] != stage_id:
        raise ValueError(
            f"template {template_path.name} stage_id {parsed.frontmatter['stage_id']!r} "
            f"does not match requested {stage_id!r}"
        )
    body = parsed.body
    mechanism_subset = sorted(set(mechanism_subset or []))
    for required in REQUIRED_BODY_SECTIONS:
        if required not in parsed.sections:
            raise ValueError(
                f"template {template_path.name} missing body section {required!r}"
            )
    # Placeholder resolution. The template body may carry ``{placeholder}``
    # tokens; we substitute them with deterministic values.
    substitutions: dict[str, str] = {
        "stage_id": stage_id,
        "contract_version": contract_version,
        "mechanism_ids": ", ".join(mechanism_subset),
        "bundle_id": bundle_id,
        "generated_at": "",  # Ruling-E2: never embed build time.
        "manifest_version": manifest_version,
    }
    # Sanity check: refuse any undeclared placeholder.
    declared = set(substitutions)
    for match in PLACEHOLDER_RE.finditer(body):
        if match.group(1) not in declared:
            raise ValueError(
                f"template {template_path.name} contains undeclared placeholder "
                f"{{{match.group(1)}}}"
            )
    body = PLACEHOLDER_RE.sub(
        lambda match: substitutions[match.group(1)], body
    )

    return ProjectedSkill(
        stage_id=stage_id,
        file_name="SKILL.md",
        body=body,
        required_mechanism_ids=mechanism_subset,
    )


__all__ = [
    "PLACEHOLDER_RE",
    "ProjectedSkill",
    "project_skill",
]