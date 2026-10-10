"""Stage F Task 6: synthetic fixture builders for the eval CLI.

Pure stdlib. The CLI never calls a model; instead it walks a small set of
deterministic local fixtures:

  - ``build_synth_suite`` / ``build_synth_cases``: the trigger / output
    structure the Stage A ``eval-suite`` / ``eval-cases`` schemas want.
  - ``build_synth_eval_generation_text``: per-case generation text for the
    freeze-hash step.
  - ``build_synth_output_eval_inputs``: six per-stage output dicts.
  - ``build_synth_end_to_end_pairs``: six ``PairResult`` instances.

The CLI selects a profile:
  - ``happy``              -> trigger 1.0/1.0, output 6/6 pass, e2e "pass"
  - ``mixed``              -> trigger 1.0/1.0, output 6/6 pass, e2e "limited"
  - ``contains_private``   -> forces the CLI to mark has_unredacted_artifacts
    so the gate enforces the redaction blocker.

These are *fixtures*, not model responses. They are deterministic and
demonstrate the gate plumbing; real scores must come from running the
six stages with a real model in production.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from end_to_end_eval import PairResult  # noqa: E402


SIX_STAGES: tuple[str, ...] = (
    "write_entry", "scene_design", "character_beats",
    "prose_draft", "style_check", "revision",
)


def build_synth_suite(staging_root: Path, *, profile: str = "mixed") -> dict:
    bundle_id = _bundle_id(staging_root)
    return {
        "suite_version": "0.1.0",
        "policy_version": "0.1.0",
        "model": {"id": "synthetic-model", "version": "0.1.0"},
        "prompt_version": "wenfeng-eval-prompts@0.1.0",
        "tool_version": "wenfeng-skill@0.1.0",
        "case_version": "cases@0.1.0",
        "generation_params": {"temperature": 0.0},
        "budget": {
            "max_requests": 64,
            "max_input_tokens_total": 200000,
            "max_tokens_per_batch": 8000,
            "overlimit_policy": "degrade_to_limited",
        },
        "entries": [],
    }


def build_synth_cases(staging_root: Path, *, profile: str = "mixed") -> dict:
    must_trigger = []
    must_not_trigger = []
    boundary = []
    for stage_id in SIX_STAGES:
        for i in range(10):
            must_trigger.append({
                "case_id": f"{stage_id}-P-{i:02d}",
                "stage_id": stage_id,
                "input_excerpt": f"synthetic pos {stage_id} {i}",
            })
        for i in range(10):
            must_not_trigger.append({
                "case_id": f"{stage_id}-N-{i:02d}",
                "stage_id": stage_id,
                "input_excerpt": f"synthetic neg {stage_id} {i}",
            })
        for i in range(5):
            boundary.append({
                "case_id": f"{stage_id}-B-{i:02d}",
                "input_excerpt": f"synthetic boundary {stage_id} {i}",
            })
    return {
        "case_version": "0.1.0",
        "trigger_cases": {
            "must_trigger": must_trigger,
            "must_not_trigger": must_not_trigger,
            "boundary": boundary,
        },
        "output_cases": [
            {"case_id": f"O-{stage_id}-001", "stage_id": stage_id, "kind": "normal"}
            for stage_id in SIX_STAGES
        ] + [
            {"case_id": f"O-{stage_id}-002", "stage_id": stage_id, "kind": "missing_input"}
            for stage_id in SIX_STAGES
        ],
        "end_to_end_pairs": [
            {
                "pair_id": f"EP-{i:02d}",
                "brief": f"synthetic brief {i}",
                "scenario_class": "opening_meet" if i % 2 == 0 else "conflict_climax",
            }
            for i in range(6)
        ],
    }


def synth_eval_generation_text_to_results(
    staging_root: Path, *, profile: str = "mixed"
) -> list[dict]:
    """Return the results list consumed by ``compute_trigger_metrics``."""
    cases = build_synth_cases(staging_root, profile=profile)
    out: list[dict] = []
    for case in cases["trigger_cases"]["must_trigger"]:
        out.append({"case_id": case["case_id"], "stage_id": case["stage_id"], "triggered": True})
    for case in cases["trigger_cases"]["must_not_trigger"]:
        out.append({"case_id": case["case_id"], "stage_id": case["stage_id"], "triggered": False})
    for case in cases["trigger_cases"]["boundary"]:
        # ``boundary`` cases do not carry a stage_id in the schema. Recover
        # it from the case_id prefix to satisfy compute_trigger_metrics.
        sid = case["case_id"].rsplit("-B-", 1)[0]
        out.append({"case_id": case["case_id"], "stage_id": sid, "triggered": False})
    return out


def _good_output(stage_id: str) -> dict:
    base = {
        "stage_id": stage_id,
        "stop_condition_hit": "preserve_user_ending"
        if stage_id == "revision"
        else "diagnose_only"
        if stage_id == "style_check"
        else "only_approved_or_limited_mechanisms"
        if stage_id == "prose_draft"
        else "no_source_character_mapping"
        if stage_id == "character_beats"
        else "no_source_plot"
        if stage_id == "scene_design"
        else "does_not_call_other_skills",
    }
    if stage_id == "write_entry":
        return {**base,
                "primary_output": "stage-context",
                "trace_id": "t-1",
                "stage_order": list(SIX_STAGES)}
    if stage_id == "scene_design":
        return {**base, "primary_output": "scene_plan",
                "user_brief": "...", "constraints": "..."}
    if stage_id == "character_beats":
        return {**base, "primary_output": "character_beats",
                "scene_plan": "...", "user_characters": "..."}
    if stage_id == "prose_draft":
        return {**base, "primary_output": "prose_draft",
                "scene_plan": "...", "character_beats": "...",
                "bundle_mechanisms": ["M01"],
                "mechanism_ids_applied": ["M01"]}
    if stage_id == "style_check":
        return {**base, "primary_output": "diagnostics",
                "prose_draft": "...", "bundle_mechanisms": ["M01"],
                "hard_constraints": "..."}
    return {**base, "primary_output": "final_text",
            "prose_draft": "...", "style_check_report": "...",
            "hard_constraints": "..."}


def build_synth_output_eval_inputs(
    staging_root: Path, *, profile: str = "mixed"
) -> dict:
    return {sid: _good_output(sid) for sid in SIX_STAGES}


def build_synth_end_to_end_pairs(
    staging_root: Path, *, profile: str = "mixed"
) -> list[PairResult]:
    """Six pairs. ``happy`` -> six_stage wins by 1.5; otherwise baseline
    closes the gap so the verdict is "limited"."""
    pairs: list[PairResult] = []
    for i in range(6):
        if profile == "happy":
            pairs.append(PairResult(
                pair_id=f"EP-{i:02d}",
                scenario_class="opening_meet" if i % 2 == 0 else "conflict_climax",
                baseline_score=3.0,
                six_stage_score=4.5,
                quality_baseline=4.0,
                quality_six_stage=4.0,
            ))
        else:
            pairs.append(PairResult(
                pair_id=f"EP-{i:02d}",
                scenario_class="opening_meet" if i % 2 == 0 else "conflict_climax",
                baseline_score=4.5,
                six_stage_score=4.5,
                quality_baseline=4.0,
                quality_six_stage=4.0,
            ))
    return pairs


def _bundle_id(staging_root: Path) -> str:
    manifest_path = staging_root / "compile-manifest.json"
    if manifest_path.is_file():
        try:
            return json.loads(manifest_path.read_text(encoding="utf-8")).get(
                "bundle_id", "bundle-x-v0_1_0"
            )
        except json.JSONDecodeError:
            pass
    return "bundle-x-v0_1_0"


def synth_eval_generation_text(staging_root: Path, profile: str) -> dict[str, str]:
    cases = build_synth_cases(staging_root, profile=profile)
    out: dict[str, str] = {}
    for case in cases["trigger_cases"]["must_trigger"]:
        out[case["case_id"]] = f"synthetic generation for {case['case_id']}"
    for case in cases["trigger_cases"]["must_not_trigger"]:
        out[case["case_id"]] = f"synthetic generation for {case['case_id']}"
    for case in cases["trigger_cases"]["boundary"]:
        out[case["case_id"]] = f"synthetic generation for {case['case_id']}"
    return out


__all__ = [
    "build_synth_suite",
    "build_synth_cases",
    "synth_eval_generation_text_to_results",
    "build_synth_output_eval_inputs",
    "build_synth_end_to_end_pairs",
    "synth_eval_generation_text",
]