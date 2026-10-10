"""Stage D Task 5: template <-> contract consistency checker.

Validates that each ``templates/stages/<stage_id>.md`` file:

  - parses cleanly via ``scripts/skill_template.parse_template``;
  - exposes ``required_inputs`` / ``primary_output`` / ``constraints`` keys
    that match the corresponding entries in ``STAGE_DATA_CONTRACT``;
  - contains the six required body sections;
  - does not reference another template path (Ruling-D3).

The checker is the bulk of the Stage D aggregate gate's "templates ready"
assertion. It deliberately stops short of testing runtime behavior; that is
the factory Skill's job.

The constraint check is locale-aware: each constraint token in the
contract maps to one or more keyword fragments in Chinese. The mapping
lives below in ``_CONSTRAINT_KEYWORDS``; expanding it does not require any
schema change.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from six_stage_contract import STAGE_DATA_CONTRACT
from skill_template import (
    REQUIRED_BODY_SECTIONS,
    parse_template,
    list_stage_templates,
)


_CONSTRAINT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "does_not_call_other_skills": ("调用其他 Skill", "不调用"),
    "no_user_brief_rewrite": ("改写",),
    "no_source_plot": ("来源剧情",),
    "no_source_characters": ("来源人物",),
    "no_source_character_mapping": ("映射", "来源人物"),
    "no_source_plot_or_characters": ("来源剧情", "来源人物"),
    "no_prose_output": ("输出正文", "正文"),
    "only_approved_or_limited_mechanisms": ("approved", "limited", "机制"),
    "no_excluded_mechanisms": ("excluded",),
    "diagnose_only": ("只诊断",),
    "no_prose_edits": ("改正文", "不改正文"),
    "no_plot_additions": ("添加情节",),
    "preserve_facts": ("保持事实", "事实"),
    "preserve_event_sequence": ("事件顺序",),
    "preserve_pov": ("视角",),
    "preserve_user_ending": ("用户指定结尾", "结尾"),
}


@dataclass
class TemplateCheckResult:
    stage_id: str
    errors: list[str]


def check_template_matches_contract(parsed_template) -> list[str]:
    """Compare the parsed template's frontmatter to STAGE_DATA_CONTRACT."""
    errors: list[str] = []
    stage_id = parsed_template.frontmatter.get("stage_id")
    if stage_id not in STAGE_DATA_CONTRACT:
        errors.append(f"template stage_id {stage_id!r} not in contract")
        return errors
    contract = STAGE_DATA_CONTRACT[stage_id]

    fm_required_raw = list(parsed_template.frontmatter.get("required_inputs") or [])
    # Template may use either ``stage_context_input_refs.X`` or bare ``X``.
    def _strip_prefix(key: str) -> str:
        return key.split(".", 1)[1] if key.startswith("stage_context_input_refs.") else key
    fm_required = sorted({_strip_prefix(k) for k in fm_required_raw})
    contract_required = sorted({k.split(".", 1)[1] for k in contract.required_inputs
                                if k.startswith("stage_context_input_refs.")})

    # The entry stage (write_entry) is allowed to declare additional
    # user-supplied inputs that exist *before* any stage-context does. Its
    # required_inputs set may legitimately be wider than the contract's
    # empty stage-input set.
    if stage_id == "write_entry":
        # Every contract key must appear; template may list extra entry inputs.
        if not set(contract_required).issubset(set(fm_required)):
            errors.append(
                f"{stage_id}: template required_inputs {fm_required} missing "
                f"contract keys {sorted(set(contract_required) - set(fm_required))}"
            )
    else:
        if fm_required != contract_required:
            errors.append(
                f"{stage_id}: template required_inputs {fm_required} differs from "
                f"contract {contract_required}"
            )

    fm_output = (parsed_template.frontmatter.get("primary_output") or "").strip()
    if not fm_output:
        errors.append(f"{stage_id}: primary_output is empty")
    elif contract.primary_output not in fm_output:
        # The template's primary_output must contain the contract's primary_output
        # token at minimum (templates may elaborate).
        errors.append(
            f"{stage_id}: primary_output does not mention {contract.primary_output!r}"
        )

    fm_constraints_text = parsed_template.body + "\n" + parsed_template.frontmatter.get("description", "")
    for constraint in contract.constraints:
        keywords = _CONSTRAINT_KEYWORDS.get(constraint, (constraint,))
        if not any(keyword in fm_constraints_text for keyword in keywords):
            errors.append(
                f"{stage_id}: constraint {constraint!r} (keywords {keywords}) "
                f"not mentioned in template body"
            )

    missing_sections = [
        s for s in REQUIRED_BODY_SECTIONS if s not in parsed_template.sections
    ]
    if missing_sections:
        errors.append(
            f"{stage_id}: missing required body sections {missing_sections}"
        )

    return errors


def assert_no_template_circular_dep(templates_root: Path) -> list[str]:
    errors: list[str] = []
    for path in list_stage_templates(templates_root):
        text = path.read_text(encoding="utf-8")
        if "templates/stages/" in text:
            errors.append(f"{path.name}: body references another template path")
    return errors


def check_all_templates(templates_root: Path) -> dict[str, list[str]]:
    """Return ``{stage_id: [errors]}`` for every template under ``templates_root``."""
    results: dict[str, list[str]] = {}
    for path in list_stage_templates(templates_root):
        parsed = parse_template(path)
        errs = check_template_matches_contract(parsed)
        errs.extend(assert_no_template_circular_dep_for_file(path))
        results[parsed.frontmatter["stage_id"]] = errs
    return results


def assert_no_template_circular_dep_for_file(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    if "templates/stages/" in text:
        return [f"{path.name}: body references another template path"]
    return []


__all__ = [
    "TemplateCheckResult",
    "check_template_matches_contract",
    "assert_no_template_circular_dep",
    "check_all_templates",
]