"""Stage B aggregate acceptance gate.

Verifies that:
  - All Stage B invariants are intact (checked in-process, NOT by spawning
    another unittest runner — that would recurse and time out).
  - An end-to-end synthetic run walks the entire Stage B toolchain.

The gate is read-only: it never modifies the project tree.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(PROJECT_ROOT / "vendor"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))


def _check_stage_b_invariants() -> list[str]:
    """Import the Stage B modules and exercise a few invariants in-process.
    The unit suite in tests/ already covers these exhaustively; this function
    only re-checks a smoke subset so the aggregate gate is self-contained.
    """
    failures: list[str] = []
    # Import lazily so a broken Stage B module does not break the gate.
    try:
        from authorization_gate import check_authorization
        from chunker import chunk_text, CHUNKER_VERSION
        from holdout import lock_holdout, verify_holdout_lock
        from path_safety import assert_within_run_root
        from sampling import build_coverage_matrix
        from scan_budget import estimate_scan_budget, resume_windows
        from source_fingerprint import fingerprint_text, normalize
    except Exception as exc:  # pragma: no cover
        failures.append(f"imports failed: {exc}")
        return failures

    # Source fingerprint stability.
    text = "正文。\n"
    if fingerprint_text(text) != fingerprint_text(text):
        failures.append("source fingerprint unstable")

    # Normalization round-trips BOM and CRLF.
    normalized = normalize("\ufeffa\r\nb\r\n")
    if "\ufeff" in normalized or "\r" in normalized:
        failures.append("normalizer did not strip BOM/CRLF")

    # Chunker idempotence.
    chunks_a = chunk_text(text * 5, chunker_version=CHUNKER_VERSION)
    chunks_b = chunk_text(text * 5, chunker_version=CHUNKER_VERSION)
    if [c.chunk_id for c in chunks_a] != [c.chunk_id for c in chunks_b]:
        failures.append("chunker is not idempotent")

    # Coverage matrix shape.
    matrix = build_coverage_matrix(chunks_a, seed=1)
    if len(matrix.cells) != 7:
        failures.append(f"coverage matrix has wrong shape: {len(matrix.cells)}")

    # Holdout lock + verify.
    env = {"chunks": chunks_a, "matrix": matrix}
    locked = lock_holdout(
        env, holdout_fraction=0.20, seed=1,
        fingerprint="fp", normalizer_version="v1", chunker_version=CHUNKER_VERSION,
    )
    if not verify_holdout_lock(env, locked):
        failures.append("holdout lock failed to verify")

    # Authorization: missing field rejects.
    if not check_authorization({}, requested_model_id="local", requested_purpose="private_only"):
        failures.append("authorization gate should reject empty dict")

    # Scan budget: windows resume.
    policy = json.loads(
        (PROJECT_ROOT / "policies" / "content-scan-policy.json").read_text(encoding="utf-8")
    )
    plan = estimate_scan_budget(
        chunks_a, policy, fingerprint="fp", chunker_version=CHUNKER_VERSION
    )
    if not resume_windows(plan, completed_ids=set()):
        failures.append("resume_windows(empty) returned no windows")
    if resume_windows(plan, completed_ids={w["window_id"] for w in plan["windows"]}):
        failures.append("resume_windows(all) should be empty")

    # Path safety: containment.
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "run"
        root.mkdir()
        try:
            assert_within_run_root(root, root / "sub")
        except Exception as exc:
            failures.append(f"containment check failed unexpectedly: {exc}")
        try:
            assert_within_run_root(root, root / ".." / "evil")
            failures.append("containment should reject ..\\evil")
        except Exception:
            pass

    return failures


def _check_end_to_end() -> list[str]:
    failures: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        run_root = Path(tmp) / "run"
        src = Path(tmp) / "novel.txt"
        payload = "\ufeff第一章 开始\r\n这是测试正文。\r\n第二章 续\r\n更多测试。\r\n".encode("utf-8")
        src.write_bytes(payload)
        auth = Path(tmp) / "auth.json"
        auth.write_text(json.dumps({
            "scope": {"model_processing": "local_only", "derivative_use": "private_only"},
            "evidence_basis": "user_declaration",
        }), encoding="utf-8")

        cli = [sys.executable, "scripts/cli.py"]
        r = subprocess.run(cli + ["prepare-source", "--source", str(src), "--run-root", str(run_root)],
                           capture_output=True, text=True, encoding="utf-8")
        if r.returncode != 0:
            failures.append(f"prepare-source failed: {r.stderr}")
            return failures
        if not (run_root / "source-manifest.json").is_file() or not (run_root / "chunk-manifest.json").is_file():
            failures.append("prepare-source did not write both manifests")
            return failures

        init_root = run_root
        r = subprocess.run(cli + [
            "init-run",
            "--run-root", str(init_root),
            "--run-id", "r1",
            "--authorization", str(auth),
            "--requested-model-id", "local",
            "--requested-purpose", "private_only",
        ], capture_output=True, text=True, encoding="utf-8")
        if r.returncode != 0:
            failures.append(f"init-run failed: {r.stderr}")
            return failures
        chunk_data = json.loads((run_root / "chunk-manifest.json").read_text(encoding="utf-8"))
        scene_map = Path(tmp) / "scene-map.json"
        scene_map.write_text(json.dumps({"chunks": {
            chunk["chunk_id"]: {"scene_id": chunk["scene_id"], "scene_classes": ["daily"]}
            for chunk in chunk_data["chunks"]
        }}), encoding="utf-8")
        for command in (
            ["apply-scene-map", "--run-root", str(run_root), "--scene-map", str(scene_map)],
            ["build-sampling", "--run-root", str(run_root)],
            ["lock-holdout", "--run-root", str(run_root)],
        ):
            r = subprocess.run(cli + command, capture_output=True, text=True, encoding="utf-8")
            if r.returncode != 0:
                failures.append(f"{' '.join(command[:1])} failed: {r.stderr or r.stdout}")
                return failures
        manifest = json.loads((init_root / "run-manifest.json").read_text(encoding="utf-8"))
        if manifest["status"] != "incomplete":
            failures.append(f"newly initialized run must be incomplete, got {manifest['status']}")

        for _ in range(2):
            r = subprocess.run(cli + [
                "resume-run", "--run-root", str(init_root),
                "--run-id", "r1", "--step-id", "prepare-source",
                "--retry-count", "0",
            ], capture_output=True, text=True, encoding="utf-8")
            if r.returncode != 0:
                failures.append(f"resume-run failed: {r.stderr}")
                return failures
        after = json.loads((init_root / "run-manifest.json").read_text(encoding="utf-8"))
        steps = [s for s in after["step_log"] if s["step_id"] == "prepare-source"]
        if len(steps) != 1:
            failures.append(f"resume-run was not idempotent: {len(steps)} copies")
    return failures


def main() -> int:
    failures: list[str] = []
    failures.extend(_check_stage_b_invariants())
    failures.extend(_check_end_to_end())
    if failures:
        print("Stage B aggregate gate FAILED:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("Stage B aggregate gate PASSED:")
    print("- Stage B invariants (imports, fingerprint, normalizer, chunker, sampling, holdout, authorization, scan budget, path safety) all hold")
    print("- end-to-end prepare-source -> init-run -> scene map -> sampling -> holdout -> resume-run succeeded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
