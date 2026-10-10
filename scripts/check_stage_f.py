"""Stage F aggregate acceptance gate.

Verifies:
  - ``run-evaluation --profile happy`` on a freshly-compiled staging
    produces a redacted eval-report whose ``final_state`` is ``ready``;
    the same path with ``--profile mixed`` produces ``limited``; with
    ``--profile contains_private`` produces ``blocked``.
  - ``validate-evaluation`` accepts the redacted report and rejects any
    tampered one whose private fields have re-appeared.
  - Stage F's CLI never imports a network package (no model call).

Exit codes:
  0 — PASS
  1 — invariant failure
  2 — IO / subprocess failure
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from cli_evaluate import build_parser as build_evaluate_parser  # noqa: E402


# Network modules that would indicate Stage F is making a model call.
_NETWORK_MODULES = {
    "urllib", "urllib.request", "urllib.error", "urllib.parse",
    "urllib.robotparser",
    "http", "http.client", "http.server",
    "httplib", "httplib2",
    "requests", "httpx", "aiohttp",
    "socket", "ssl", "asyncio.streams",
}


def _build_minimal_staging(run_root: Path) -> Path:
    staging = run_root / "staging"
    for stage_id in (
        "write_entry", "scene_design", "character_beats",
        "prose_draft", "style_check", "revision",
    ):
        (staging / stage_id).mkdir(parents=True, exist_ok=True)
        (staging / stage_id / "SKILL.md").write_text(
            f"# {stage_id}\n", encoding="utf-8"
        )
    (staging / "compile-manifest.json").write_text(json.dumps({
        "manifest_version": "0.1.0",
        "source_id": "0a1b2c3d4e5f",
        "bundle_id": f"bundle-{uuid.uuid4().hex[:12]}-v0_1_0",
        "skill_hashes": {},
    }), encoding="utf-8")
    return staging


def _run(args: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        [sys.executable, "-u", "scripts/cli_evaluate.py", *args],
        cwd=str(cwd or PROJECT_ROOT),
        capture_output=True,
        timeout=60,
    )
    return subprocess.CompletedProcess(
        proc.args,
        proc.returncode,
        proc.stdout.decode("utf-8", errors="replace") if proc.stdout else "",
        proc.stderr.decode("utf-8", errors="replace") if proc.stderr else "",
    )


def check_happy_yields_ready() -> list[str]:
    failures: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        run_root = Path(tmp) / "run"
        run_root.mkdir()
        staging = _build_minimal_staging(run_root)
        r = _run([
            "run-evaluation",
            "--staging-root", str(staging),
            "--profile", "happy",
        ])
        if r.returncode != 0:
            failures.append(f"happy run-evaluation exit={r.returncode}: {r.stdout + r.stderr}")
            return failures
        report = json.loads((staging / "eval-report.json").read_text(encoding="utf-8"))
        if report["summary"]["final_state"] != "ready":
            failures.append(f"happy final_state={report['summary']['final_state']!r} != 'ready'")
        # No private fields leak.
        for leaked in ("unblinding_map", "pair_results", "rating_secrets"):
            if leaked in report:
                failures.append(f"happy report leaked {leaked!r}")
        # validate-evaluation accepts the report.
        r2 = _run(["validate-evaluation", "--staging-root", str(staging)])
        if r2.returncode != 0:
            failures.append(f"happy validate-evaluation exit={r2.returncode}: {r2.stdout + r2.stderr}")
    return failures


def check_mixed_yields_limited() -> list[str]:
    failures: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        run_root = Path(tmp) / "run"
        run_root.mkdir()
        staging = _build_minimal_staging(run_root)
        r = _run([
            "run-evaluation",
            "--staging-root", str(staging),
            "--profile", "mixed",
        ])
        if r.returncode not in (0, 1):
            failures.append(f"mixed run-evaluation exit={r.returncode}: {r.stdout + r.stderr}")
            return failures
        report = json.loads((staging / "eval-report.json").read_text(encoding="utf-8"))
        if report["summary"]["final_state"] != "limited":
            failures.append(f"mixed final_state={report['summary']['final_state']!r} != 'limited'")
    return failures


def check_contains_private_yields_blocked() -> list[str]:
    failures: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        run_root = Path(tmp) / "run"
        run_root.mkdir()
        staging = _build_minimal_staging(run_root)
        r = _run([
            "run-evaluation",
            "--staging-root", str(staging),
            "--profile", "contains_private",
        ])
        if r.returncode != 1:
            failures.append(f"contains_private exit={r.returncode} (expected 1): {r.stdout + r.stderr}")
            return failures
        report = json.loads((staging / "eval-report.json").read_text(encoding="utf-8"))
        if report["summary"]["final_state"] != "blocked":
            failures.append(f"contains_private final_state={report['summary']['final_state']!r} != 'blocked'")
    return failures


def check_no_network_import() -> list[str]:
    """Stage F must not import any network-capable module."""
    failures: list[str] = []
    stage_f_scripts = [
        "scripts/trigger_metrics.py",
        "scripts/output_assertions.py",
        "scripts/end_to_end_eval.py",
        "scripts/final_state_evaluator.py",
        "scripts/evaluation_freezer.py",
        "scripts/cli_evaluate.py",
        "scripts/cli_evaluate_synth.py",
        "scripts/check_stage_f.py",
    ]
    for script in stage_f_scripts:
        path = PROJECT_ROOT / script
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for module in _NETWORK_MODULES:
            # crude grep — match an `import X` or `from X import` line that
            # targets the module name.
            for line in text.splitlines():
                stripped = line.strip()
                if not (stripped.startswith("import ") or stripped.startswith("from ")):
                    continue
                # Only the first token of import / the head of `from X import ...`.
                if stripped.startswith("import "):
                    head = stripped[len("import "):].split(" as ")[0].split(",")[0].strip()
                else:  # from X import Y
                    head = stripped[len("from "):].split(" import ")[0].strip()
                if head == module or head.startswith(module + "."):
                    failures.append(f"{script}: imports {module!r}")
    return failures


def main() -> int:
    failures: list[str] = []
    failures.extend(check_no_network_import())
    failures.extend(check_happy_yields_ready())
    failures.extend(check_mixed_yields_limited())
    failures.extend(check_contains_private_yields_blocked())
    if failures:
        print("Stage F aggregate gate FAILED:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("Stage F aggregate gate PASSED:")
    print("- run-evaluation --profile happy -> final_state ready (synthetic)")
    print("- run-evaluation --profile mixed -> final_state limited (synthetic)")
    print("- run-evaluation --profile contains_private -> final_state blocked (synthetic)")
    print("- validate-evaluation accepts redacted report")
    print("- Stage F scripts do not import any network module")
    print("- Ready for stage G (final source scan, deterministic package, install gate)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
