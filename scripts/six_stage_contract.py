"""Stage D Task 2: six-stage data contract.

Pure stdlib. The contract mirrors spec §4.5:

  stage          required_inputs (from upstream)         primary_output       constraints
  write_entry    (none — top of chain)                   stage-context        does not call other Skills
  scene_design   user_brief, constraints                scene_plan           no source plot / characters
  character_beats scene_plan, user_characters           character_beats      no source character mapping
  prose_draft    scene_plan, character_beats,           prose_draft          only approved/limited mechanisms
                  bundle_mechanisms
  style_check    prose_draft, bundle_mechanisms,         diagnostics          diagnose only — no edits
                  hard_constraints
  revision       prose_draft, style_check_report,        final_text           preserve facts / sequence / POV / ending
                  hard_constraints

The contract is the source of truth that ``stage-context.stage_snapshot.input_refs``
must satisfy. ``validate_stage_contract`` checks that an upstream layer's output
exposes the keys the downstream stage declares it needs.
"""

from __future__ import annotations

from dataclasses import dataclass


STAGE_ORDER: tuple[str, ...] = (
    "write_entry",
    "scene_design",
    "character_beats",
    "prose_draft",
    "style_check",
    "revision",
)


@dataclass(frozen=True)
class StageContract:
    stage_id: str
    required_inputs: tuple[str, ...]
    primary_output: str
    constraints: tuple[str, ...]


STAGE_DATA_CONTRACT: dict[str, StageContract] = {
    "write_entry": StageContract(
        stage_id="write_entry",
        required_inputs=(),
        primary_output="stage-context",
        constraints=(
            "does_not_call_other_skills",
            "no_user_brief_rewrite",
        ),
    ),
    "scene_design": StageContract(
        stage_id="scene_design",
        required_inputs=(
            "stage_context_input_refs.user_brief",
            "stage_context_input_refs.constraints",
        ),
        primary_output="scene_plan",
        constraints=(
            "no_source_plot",
            "no_source_characters",
        ),
    ),
    "character_beats": StageContract(
        stage_id="character_beats",
        required_inputs=(
            "stage_context_input_refs.scene_plan",
            "stage_context_input_refs.user_characters",
        ),
        primary_output="character_beats",
        constraints=(
            "no_source_character_mapping",
            "no_prose_output",
        ),
    ),
    "prose_draft": StageContract(
        stage_id="prose_draft",
        required_inputs=(
            "stage_context_input_refs.scene_plan",
            "stage_context_input_refs.character_beats",
            "stage_context_input_refs.bundle_mechanisms",
        ),
        primary_output="prose_draft",
        constraints=(
            "only_approved_or_limited_mechanisms",
            "no_excluded_mechanisms",
            "no_source_plot_or_characters",
        ),
    ),
    "style_check": StageContract(
        stage_id="style_check",
        required_inputs=(
            "stage_context_input_refs.prose_draft",
            "stage_context_input_refs.bundle_mechanisms",
            "stage_context_input_refs.hard_constraints",
        ),
        primary_output="diagnostics",
        constraints=(
            "diagnose_only",
            "no_prose_edits",
            "no_plot_additions",
        ),
    ),
    "revision": StageContract(
        stage_id="revision",
        required_inputs=(
            "stage_context_input_refs.prose_draft",
            "stage_context_input_refs.style_check_report",
            "stage_context_input_refs.hard_constraints",
        ),
        primary_output="final_text",
        constraints=(
            "preserve_facts",
            "preserve_event_sequence",
            "preserve_pov",
            "preserve_user_ending",
            "no_source_characters",
        ),
    ),
}


class ContractError(Exception):
    def __init__(self, message: str, *, error_type: str = "contract_error") -> None:
        super().__init__(message)
        self.error_type = error_type


def stage_index(stage_id: str) -> int:
    if stage_id not in STAGE_ORDER:
        raise ContractError(f"unknown stage_id {stage_id!r}")
    return STAGE_ORDER.index(stage_id)


def get_contract(stage_id: str) -> StageContract:
    if stage_id not in STAGE_DATA_CONTRACT:
        raise ContractError(f"unknown stage_id {stage_id!r}")
    return STAGE_DATA_CONTRACT[stage_id]


def validate_stage_contract(stage_id: str, available_input_keys: set[str]) -> list[str]:
    """Return error messages for any required input the caller is missing."""
    contract = get_contract(stage_id)
    missing = [key for key in contract.required_inputs if key not in available_input_keys]
    if missing:
        return [
            f"{stage_id} requires {missing!r}; available keys = {sorted(available_input_keys)}"
        ]
    return []


def assert_contract_compatibility(
    current_stage: str,
    next_stage: str,
    *,
    chain_outputs: set[str] | None = None,
) -> None:
    """Assert that the data context can satisfy ``next_stage``.

    The data context for ``next_stage`` is the union of:
      - always-available keys supplied at the entry stage or by the bundle
      - every prior stage's primary_output in the chain
      - the immediate upstream's primary_output

    The function does NOT enforce handoff legality — that is the
    state-machine layer's job. This function only checks whether the data
    context can in principle satisfy the downstream contract.

    Raises ``ContractError`` if any required input cannot be supplied.
    """
    if current_stage not in STAGE_DATA_CONTRACT:
        raise ContractError(f"unknown current_stage {current_stage!r}")
    if next_stage not in STAGE_DATA_CONTRACT:
        raise ContractError(f"unknown next_stage {next_stage!r}")
    next_contract = STAGE_DATA_CONTRACT[next_stage]
    upstream_output = STAGE_DATA_CONTRACT[current_stage].primary_output
    required_keys = [
        key.split(".", 1)[1] for key in next_contract.required_inputs
        if key.startswith("stage_context_input_refs.")
    ]
    always_provided = {
        "user_brief", "constraints", "user_characters", "hard_constraints",
        "bundle_mechanisms", "stage-context",
        # The style_check stage emits diagnostics; revision requires
        # style_check_report. The contract treats them as the same key
        # because the Stage D factory Skill emits one document with both
        # names; see docs/contracts/six-stage-data-contract.md.
        "style_check_report", "diagnostics",
    }
    provided = always_provided | (chain_outputs or set()) | {upstream_output}
    missing = [key for key in required_keys if key not in provided]
    if missing:
        raise ContractError(
            f"{next_stage} requires {missing!r}; data context after {current_stage} "
            f"does not cover them"
        )


__all__ = [
    "STAGE_ORDER",
    "StageContract",
    "STAGE_DATA_CONTRACT",
    "ContractError",
    "stage_index",
    "get_contract",
    "validate_stage_contract",
    "assert_contract_compatibility",
]