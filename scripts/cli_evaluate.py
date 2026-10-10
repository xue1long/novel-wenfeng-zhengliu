"""Stage F Task 6: thin CLI for the evaluation pipeline.

Lives next to ``scripts/cli.py`` / ``scripts/cli_extract.py`` /
``scripts/cli_compile.py``. Exposes two subcommands:

  - ``run-evaluation --staging-root <path>``
  - ``validate-evaluation --staging-root <path>``

The run-evaluation path is a deterministic local synthesis: it does NOT
call any model. Synthetic trigger / output / end-to-end fixtures live in
``scripts/cli_evaluate_synth.py`` and the CLI just orchestrates them.

Exit codes:
  0 — successful run; report written; final state "limited" or "ready".
  1 — data / contract error; one or more gates failed; report still
      written (redacted) but demerit surfaced.
  2 — path / IO error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from end_to_end_eval import evaluate_effect_gate
from evaluation_freezer import (
    FreezerError,
    freeze_all_artifacts,
    write_eval_cases,
    write_eval_report,
    write_eval_suite,
)
from final_state_evaluator import (
    compute_run_state,
    evaluate_evaluation_state,
)
from output_assertions import evaluate_all_stages
from path_safety import PathEscapeError, assert_within_run_root
from trigger_metrics import assert_trigger_thresholds, compute_trigger_metrics

from cli_evaluate_synth import (  # noqa: E402  - near top of F layer
    build_synth_suite,
    build_synth_cases,
    build_synth_output_eval_inputs,
    build_synth_end_to_end_pairs,
    synth_eval_generation_text,
    synth_eval_generation_text_to_results,
)


SIX_STAGES: tuple[str, ...] = (
    "write_entry", "scene_design", "character_beats",
    "prose_draft", "style_check", "revision",
)


def _run_root(staging_root: Path) -> Path:
    return Path(staging_root).resolve().parent


def cmd_run_evaluation(args: argparse.Namespace) -> int:
    staging_root = Path(args.staging_root).resolve()
    run_root = _run_root(staging_root)
    try:
        assert_within_run_root(run_root, staging_root)
    except PathEscapeError as exc:
        print(f"path safety violation: {exc}")
        return 2

    if not (staging_root / "compile-manifest.json").is_file():
        print(f"compile-manifest.json missing at {staging_root}; run stage E first")
        return 1

    source_id = json.loads((staging_root / "compile-manifest.json").read_text(encoding="utf-8")).get(
        "bundle_id", ""
    )[:12] or "0" * 12
    bundle_id = json.loads((staging_root / "compile-manifest.json").read_text(encoding="utf-8")).get(
        "bundle_id", "bundle-x-v0_1_0"
    )
    # Stage F CLI does not read the run manifest; default to
    # ``shareable_anonymous`` so the state machine treats a fully-green run
    # as ``ready``. The actual authorization_purpose is plumbed through
    # stage G's run-manifest read; the state machine here is a
    # deterministic local stand-in.
    auth_purpose = "shareable_anonymous"

    # Synthetic gate inputs (Stage F never calls a model).
    suite = build_synth_suite(staging_root, profile=args.profile)
    cases = build_synth_cases(staging_root, profile=args.profile)
    trigger_results_list = synth_eval_generation_text_to_results(staging_root, profile=args.profile)
    output_eval_inputs = build_synth_output_eval_inputs(staging_root, profile=args.profile)
    pairs = build_synth_end_to_end_pairs(staging_root, profile=args.profile)
    generation_text = synth_eval_generation_text(staging_root, profile=args.profile)

    # Trigger gate.
    try:
        write_eval_suite(staging_root, suite)
        write_eval_cases(staging_root, cases)
    except FreezerError as exc:
        print(f"eval-suite/cases schema rejected: {exc}")
        return 1
    trigger_metrics = compute_trigger_metrics(cases, trigger_results_list)
    trigger_errors = assert_trigger_thresholds(trigger_metrics)

    # Output gate.
    output_eval = evaluate_all_stages(output_eval_inputs)

    # End-to-end gate.
    e2e = evaluate_effect_gate(pairs)

    # Missing outputs detection.
    missing_outputs = [sid for sid in SIX_STAGES if sid not in output_eval_inputs]

    final_state = evaluate_evaluation_state(
        {
            "all_stages_meet_precision_and_recall_threshold": not trigger_errors,
            "stages_with_full_coverage": trigger_metrics["_summary"]["stages_with_full_coverage"],
        },
        output_eval,
        e2e,
        has_unredacted_artifacts=args.profile == "contains_private",
        missing_outputs=missing_outputs,
        authorization_purpose=auth_purpose,
    )

    report = {
        "report_version": "0.1.0",
        "bundle_id": bundle_id,
        "gate_results": {
            "trigger": {
                "precision": trigger_metrics["_summary"]["stages_meeting_precision_threshold"] / 6,
                "recall": trigger_metrics["_summary"]["stages_meeting_recall_threshold"] / 6,
                "passed": not trigger_errors,
            },
            "output": {
                "mechanical_pass_rate": output_eval["mechanical_pass_rate"],
                "passed": output_eval["mechanical_pass_rate"] >= 1.0 and not output_eval["missing_outputs"],
            },
            "end_to_end": {
                "verdict": e2e["verdict"],
                "winning_pairs": e2e["winning_pairs"],
                "style_fit_median": e2e["style_fit_median"],
                "pairing_median_delta": e2e["pairing_median_delta"],
                "quality_median_delta": e2e["quality_median_delta"],
                "undetermined_dimensions": e2e["undetermined_dimensions"],
                "passed": e2e["verdict"] == "pass",
            },
        },
        "summary": {
            "final_state": final_state,
            "notes": "",
        },
    }

    try:
        write_eval_report(
            staging_root,
            report,
            source_id=source_id,
            bundle_id=bundle_id,
            redacted=True,
        )
    except FreezerError as exc:
        print(f"eval-report write failed: {exc}")
        return 1
    freeze_all_artifacts(
        staging_root,
        eval_generation_text=generation_text,
        report=report,
    )
    # Re-write report with frozen_hashes embedded.
    write_eval_report(
        staging_root, report,
        source_id=source_id, bundle_id=bundle_id, redacted=True,
    )

    print(f"evaluation complete; final_state={final_state}; gate_results reported in eval-report.json", flush=True)
    if final_state == "blocked":
        return 1
    if final_state == "incomplete":
        return 1
    return 0


def cmd_validate_evaluation(args: argparse.Namespace) -> int:
    staging_root = Path(args.staging_root).resolve()
    if not (staging_root / "eval-report.json").is_file():
        print(f"eval-report.json missing at {staging_root}")
        return 1
    try:
        with (staging_root / "eval-report.json").open("r", encoding="utf-8") as fh:
            report = json.load(fh)
    except json.JSONDecodeError as exc:
        print(f"eval-report.json not valid JSON: {exc}")
        return 1
    notes = report.get("summary", {}).get("notes", "")
    required = ["unblinding_map", "pair_results", "rating_secrets"]
    if any(name in report for name in required):
        leaked = [name for name in required if name in report]
        print(f"eval-report still carries private fields: {leaked}")
        return 1
    if "redacted" not in notes:
        print("eval-report.notes missing redaction marker")
        return 1
    print(f"eval-report validated; final_state={report['summary'].get('final_state')}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Stage F thin CLI.")
    sub = parser.add_subparsers(dest="command", required=True)

    e = sub.add_parser("run-evaluation", help="run trigger / output / e2e gates")
    e.add_argument("--staging-root", required=True)
    e.add_argument("--profile", default="mixed",
                   choices=["happy", "mixed", "contains_private"])
    e.set_defaults(func=cmd_run_evaluation)

    v = sub.add_parser("validate-evaluation", help="verify eval-report is redacted")
    v.add_argument("--staging-root", required=True)
    v.set_defaults(func=cmd_validate_evaluation)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())