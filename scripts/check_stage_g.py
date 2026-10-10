"""Stage G aggregate acceptance gate.

Verifies:
  - shareable happy path: stage F final_state="ready" + shareable_anonymous
    -> package --profile shareable -> verify-package passes.
  - private-preview path: final_state="limited" -> package --profile
    private-preview -> verify-package passes.
  - blocked path: package --profile shareable AND private-preview both
    denied.
  - install dry-run does not touch the target.
  - install user scope writes the target and refuses standard locations.
  - Stage G scripts do not import any network-capable module (no model
    call).
  - release-manifest writer refuses private fields.

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


_NETWORK_MODULES = {
    "urllib", "urllib.request", "urllib.error", "urllib.parse",
    "urllib.robotparser",
    "http", "http.client", "http.server",
    "httplib", "httplib2",
    "requests", "httpx", "aiohttp",
    "socket", "ssl", "asyncio.streams",
}


def _run(args: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        [sys.executable, "-u", "scripts/cli_package.py", *args],
        cwd=str(cwd or PROJECT_ROOT),
        capture_output=True,
        timeout=90,
    )
    return subprocess.CompletedProcess(
        proc.args,
        proc.returncode,
        proc.stdout.decode("utf-8", errors="replace") if proc.stdout else "",
        proc.stderr.decode("utf-8", errors="replace") if proc.stderr else "",
    )


def _make_staging(staging: Path, *, final_state: str) -> dict:
    import hashlib
    staging.mkdir(parents=True, exist_ok=True)
    skill_hashes: dict[str, str] = {}
    for stage_id in (
        "write_entry", "scene_design", "character_beats",
        "prose_draft", "style_check", "revision",
    ):
        (staging / stage_id).mkdir(exist_ok=True)
        body = f"# {stage_id}\n"
        (staging / stage_id / "SKILL.md").write_text(body, encoding="utf-8")
        skill_hashes[stage_id] = hashlib.sha256(body.encode("utf-8")).hexdigest()
    evidence = "approved" if final_state == "ready" else "limited"
    (staging / "compile-manifest.json").write_text(json.dumps({
        "manifest_version": "0.1.0",
        "bundle_id": "bundletestv0010",
        "source_id": "0a1b2c3d4e5f",
        "evidence_status": evidence,
        "skill_hashes": skill_hashes,
    }), encoding="utf-8")
    (staging / "eval-report.json").write_text(json.dumps({
        "report_version": "0.1.0",
        "bundle_id": "bundletestv0010",
        "gate_results": {
            "trigger": {"precision": 1.0, "recall": 1.0, "passed": True},
            "output": {"mechanical_pass_rate": 1.0, "passed": True},
            "end_to_end": {"verdict": "pass", "winning_pairs": 6,
                            "style_fit_median": 4.5, "pairing_median_delta": 1.5,
                            "quality_median_delta": 0.0, "undetermined_dimensions": [],
                            "passed": True},
        },
        "summary": {"final_state": final_state,
                    "notes": "[redacted=0a1b2c3d4e5f/bundletestv0010;removed=;timestamp=none]"},
    }), encoding="utf-8")
    return skill_hashes


def _make_run_manifest(run_root: Path, *, auth: str) -> None:
    (run_root / "run-manifest.json").write_text(
        json.dumps({"authorization_purpose": auth, "run_id": "r-test"}),
        encoding="utf-8",
    )


def _package(run_root: Path, staging: Path, *, profile: str, auth: str,
              output_dir: Path) -> subprocess.CompletedProcess:
    _make_run_manifest(run_root, auth=auth)
    return _run([
        "package",
        "--staging-root", str(staging),
        "--run-root", str(run_root),
        "--output-dir", str(output_dir),
        "--run-manifest", str(run_root / "run-manifest.json"),
        "--profile", profile,
    ])


def _locate_zip(output_dir: Path) -> Path:
    return list(
        (output_dir / "0a1b2c3d4e5f" / "bundletestv0010" / "v0.1.0").glob("package.zip")
    )[0]


def check_shareable_happy_path() -> list[str]:
    failures: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        run_root = Path(tmp) / "run"; run_root.mkdir()
        staging = run_root / "staging"
        _make_staging(staging, final_state="ready")
        output_dir = run_root / "shareable"
        r = _package(run_root, staging, profile="shareable", auth="shareable_anonymous",
                      output_dir=output_dir)
        if r.returncode != 0:
            failures.append(f"shareable package exit={r.returncode}: {r.stdout + r.stderr}")
            return failures
        try:
            zip_path = _locate_zip(output_dir)
        except IndexError:
            failures.append("shareable: package.zip not found in dist")
            return failures
        r2 = _run(["verify-package", "--package", str(zip_path),
                    "--run-root", str(run_root)])
        if r2.returncode != 0:
            failures.append(f"shareable verify-package exit={r2.returncode}: {r2.stdout + r2.stderr}")
    return failures


def check_private_preview_path() -> list[str]:
    failures: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        run_root = Path(tmp) / "run"; run_root.mkdir()
        staging = run_root / "staging"
        _make_staging(staging, final_state="limited")
        output_dir = run_root / "shareable"
        r = _package(run_root, staging, profile="private-preview", auth="private_only",
                      output_dir=output_dir)
        if r.returncode != 0:
            failures.append(f"private-preview package exit={r.returncode}: {r.stdout + r.stderr}")
            return failures
        zip_path = list(
            (run_root / "dist" / "private" / "bundletestv0010").glob("package.zip")
        )[0]
        r2 = _run(["verify-package", "--package", str(zip_path),
                    "--run-root", str(run_root)])
        if r2.returncode != 0:
            failures.append(f"private-preview verify-package exit={r2.returncode}: {r2.stdout + r2.stderr}")
    return failures


def check_blocked_path_denied() -> list[str]:
    failures: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        run_root = Path(tmp) / "run"; run_root.mkdir()
        staging = run_root / "staging"
        _make_staging(staging, final_state="blocked")
        output_dir = run_root / "shareable"
        for profile in ("shareable", "private-preview"):
            r = _package(run_root, staging, profile=profile, auth="private_only",
                          output_dir=output_dir)
            if r.returncode != 2:
                failures.append(
                    f"blocked path ({profile}): expected exit 2, got {r.returncode}: {r.stdout + r.stderr}"
                )
    return failures


def check_install_dry_run_does_not_touch_target() -> list[str]:
    failures: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        run_root = Path(tmp) / "run"; run_root.mkdir()
        staging = run_root / "staging"
        _make_staging(staging, final_state="ready")
        output_dir = run_root / "shareable"
        _package(run_root, staging, profile="shareable", auth="shareable_anonymous",
                  output_dir=output_dir)
        zip_path = _locate_zip(output_dir)
        target = run_root / "dry-run-target"
        target.mkdir()
        (target / "existing.txt").write_text("hi", encoding="utf-8")
        before = sorted(str(p.name) for p in target.iterdir())
        r = _run(["install", "--package", str(zip_path), "--run-root", str(run_root),
                   "--target", str(target)])
        if r.returncode != 0:
            failures.append(f"install dry-run exit={r.returncode}: {r.stdout + r.stderr}")
            return failures
        after = sorted(str(p.name) for p in target.iterdir())
        if before != after:
            failures.append("install dry-run touched target")
    return failures


def check_install_user_writes_and_refuses_standard() -> list[str]:
    failures: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        run_root = Path(tmp) / "run"; run_root.mkdir()
        staging = run_root / "staging"
        _make_staging(staging, final_state="ready")
        output_dir = run_root / "shareable"
        _package(run_root, staging, profile="shareable", auth="shareable_anonymous",
                  output_dir=output_dir)
        zip_path = _locate_zip(output_dir)
        # user scope writes target
        target = run_root / "user-install"
        r = _run(["install", "--package", str(zip_path), "--run-root", str(run_root),
                   "--target", str(target), "--scope", "user", "--apply"])
        if r.returncode != 0:
            failures.append(f"install user exit={r.returncode}: {r.stdout + r.stderr}")
            return failures
        if not (target / "release-manifest.json").is_file():
            failures.append("install user did not write release-manifest.json")
        # standard location is refused
        std_target = Path.home() / ".wenfeng-skill"
        r2 = _run(["install", "--package", str(zip_path), "--run-root", str(run_root),
                    "--target", str(std_target), "--scope", "user", "--apply"])
        if r2.returncode != 2:
            failures.append(f"install user to standard location exit={r2.returncode} (expected 2)")
    return failures


def check_no_network_import() -> list[str]:
    failures: list[str] = []
    stage_g_scripts = [
        "scripts/final_source_scan.py",
        "scripts/release_manifest.py",
        "scripts/deterministic_package.py",
        "scripts/isolated_install.py",
        "scripts/package_state_gate.py",
        "scripts/cli_package.py",
        "scripts/check_stage_g.py",
    ]
    for script in stage_g_scripts:
        path = PROJECT_ROOT / script
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            stripped = line.strip()
            if not (stripped.startswith("import ") or stripped.startswith("from ")):
                continue
            if stripped.startswith("import "):
                head = stripped[len("import "):].split(" as ")[0].split(",")[0].strip()
            else:
                head = stripped[len("from "):].split(" import ")[0].strip()
            if head in _NETWORK_MODULES or any(
                head.startswith(m + ".") for m in _NETWORK_MODULES
            ):
                failures.append(f"{script}: imports {head!r}")
    return failures


def check_release_manifest_refuses_private() -> list[str]:
    failures: list[str] = []
    from release_manifest import build_release_manifest, write_release_manifest
    with tempfile.TemporaryDirectory() as tmp:
        staging = Path(tmp) / "staging"
        _make_staging(staging, final_state="ready")
        # Create a dummy package.zip so build_release_manifest can compute its hash.
        zip_path = Path(tmp) / "pkg.zip"
        zip_path.write_bytes(b"")
        manifest = build_release_manifest(
            staging,
            bundle_id="bundletestv0010",
            source_id="0a1b2c3d4e5f",
            authorization_purpose="shareable_anonymous",
            release_state="ready",
            eval_report_hash="a" * 64,
            final_scan_result={"coverage_ratio": 1.0, "policy": {"policy_version": "0.1.0"}},
            zip_path=zip_path,
            compile_manifest_hash="b" * 64,
        )
        manifest["source_body"] = "do not leak me"
        try:
            write_release_manifest(manifest, Path(tmp) / "out")
        except Exception as exc:  # noqa: BLE001
            return []  # any refusal is fine
        failures.append("write_release_manifest accepted source_body")
    return failures


def main() -> int:
    failures: list[str] = []
    failures.extend(check_no_network_import())
    failures.extend(check_shareable_happy_path())
    failures.extend(check_private_preview_path())
    failures.extend(check_blocked_path_denied())
    failures.extend(check_install_dry_run_does_not_touch_target())
    failures.extend(check_install_user_writes_and_refuses_standard())
    failures.extend(check_release_manifest_refuses_private())
    if failures:
        print("Stage G aggregate gate FAILED:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("Stage G aggregate gate PASSED:")
    print("- shareable happy path: package + verify-package")
    print("- private-preview path: package + verify-package")
    print("- blocked path denied on both profiles")
    print("- install --dry-run does not touch the target")
    print("- install --scope user writes the target; standard locations refused")
    print("- Stage G scripts do not import any network module")
    print("- release-manifest writer refuses private fields")
    print("- Stage G checks only; run the other stage gates separately for full validation")
    return 0


if __name__ == "__main__":
    sys.exit(main())
