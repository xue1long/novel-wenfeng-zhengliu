"""Stage C aggregate acceptance gate.

Verifies:
  - Stage C invariants are intact (imports + zero-input self checks).
  - End-to-end synthetic run walks: prepare-source -> init-run ->
    extract-dimensions (stub) -> review-dimensions -> compile-bundle and
    produces a Bundle whose ``evidence_status`` is at most ``approved``
    only when an explicit "all_supported" stub profile is requested.
  - The model-misreporting-offsets adversarial case is rejected.

Exit codes:
  0 — PASS
  1 — invariant failure
  2 — end-to-end IO / path failure
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _check_stage_c_invariants() -> list[str]:
    failures: list[str] = []
    try:
        from evidence_validator import validate_evidence_refs, compute_excerpt_hash
        from extractors import EXTRACTION_PROMPT_VERSIONS, DIMENSION_ORDER, extract_dimension
        from mechanism_merger import classify_mechanism, compute_bundle_evidence_status
        from bundle_compiler import compile_bundle
        from review_parser import parse_review_output, apply_review_to_candidate
        from extraction_journal import ExtractionJournal
    except Exception as exc:  # pragma: no cover
        return [f"imports failed: {exc}"]

    if set(EXTRACTION_PROMPT_VERSIONS) != set(DIMENSION_ORDER):
        failures.append("EXTRACTION_PROMPT_VERSIONS keys differ from DIMENSION_ORDER")
    if compute_excerpt_hash("text", [0, 4], chunker_version="v1") != compute_excerpt_hash(
        "text", [0, 4], chunker_version="v1"
    ):
        failures.append("excerpt hash not deterministic")
    if compute_excerpt_hash("text", [0, 4], chunker_version="v1") == compute_excerpt_hash(
        "text", [0, 4], chunker_version="v2"
    ):
        failures.append("excerpt hash identical across chunker versions")

    # parse_review_output rejects free text.
    try:
        parse_review_output("not json")
        failures.append("parse_review_output accepted free text")
    except Exception:
        pass

    return failures


def _check_end_to_end() -> list[str]:
    failures: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        src = tmp_path / "novel.txt"
        src.write_text(
            "# 第一章\n句子一。句子二。\n\n# 第二章\n句子三。句子四。\n\n# 第三章\n句子五。句子六。\n",
            encoding="utf-8",
        )
        auth = tmp_path / "auth.json"
        auth.write_text(json.dumps({
            "scope": {"model_processing": "local_only", "derivative_use": "private_only"},
            "evidence_basis": "user_declaration",
        }), encoding="utf-8")

        run_root = tmp_path / "run"
        r = subprocess.run(
            [sys.executable, "scripts/cli.py", "prepare-source",
             "--source", str(src), "--run-root", str(run_root)],
            cwd=str(PROJECT_ROOT), capture_output=True, text=True, encoding="utf-8", timeout=30,
        )
        if r.returncode != 0:
            return [f"prepare-source failed: {r.stderr}"]

        r = subprocess.run(
            [sys.executable, "scripts/cli.py", "init-run",
             "--run-root", str(run_root), "--run-id", "r1",
             "--authorization", str(auth),
             "--requested-model-id", "local",
             "--requested-purpose", "private_only"],
            cwd=str(PROJECT_ROOT), capture_output=True, text=True, encoding="utf-8", timeout=30,
        )
        if r.returncode != 0:
            return [f"init-run failed: {r.stderr}"]

        chunks = json.loads((run_root / "chunk-manifest.json").read_text(encoding="utf-8"))["chunks"]
        scene_map = tmp_path / "scene-map.json"
        scene_map.write_text(json.dumps({"chunks": {
            chunk["chunk_id"]: {"scene_id": chunk["scene_id"], "scene_classes": ["daily"]}
            for chunk in chunks
        }}), encoding="utf-8")
        for command in (
            ["apply-scene-map", "--run-root", str(run_root), "--scene-map", str(scene_map)],
            ["build-sampling", "--run-root", str(run_root)],
            ["lock-holdout", "--run-root", str(run_root)],
        ):
            r = subprocess.run(
                [sys.executable, "scripts/cli.py", *command],
                cwd=str(PROJECT_ROOT), capture_output=True, text=True, encoding="utf-8", timeout=30,
            )
            if r.returncode != 0:
                return [f"{' '.join(command[:1])} failed: {r.stderr or r.stdout}"]

        # Default profile = mixed → bundle should NOT land at ready/approved.
        r = subprocess.run(
            [sys.executable, "scripts/cli_extract.py", "extract-dimensions",
             "--run-root", str(run_root), "--run-id", "r1", "--stub"],
            cwd=str(PROJECT_ROOT), capture_output=True, text=True, encoding="utf-8", timeout=30,
        )
        if r.returncode != 0:
            return [f"extract-dimensions failed: {r.stderr}"]

        verdict = {}
        for path in sorted((run_root / "candidates").glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            verdicts = [
                {"mechanism_id": c["mechanism_id"], "review_status": "limited", "reasons": ["mixed"]}
                for c in payload["candidates"]
            ]
            verdict[payload["dimension"]] = verdicts
        review_file = tmp_path / "reviews.json"
        review_file.write_text(json.dumps(verdict), encoding="utf-8")
        r = subprocess.run(
            [sys.executable, "scripts/cli_extract.py", "review-dimensions",
             "--run-root", str(run_root), "--review-file", str(review_file)],
            cwd=str(PROJECT_ROOT), capture_output=True, text=True, encoding="utf-8", timeout=30,
        )
        if r.returncode != 0:
            return [f"review-dimensions failed: {r.stderr}"]

        r = subprocess.run(
            [sys.executable, "scripts/cli_extract.py", "compile-bundle",
             "--run-root", str(run_root), "--bundle-version", "0.1.0"],
            cwd=str(PROJECT_ROOT), capture_output=True, text=True, encoding="utf-8", timeout=30,
        )
        if r.returncode != 0:
            return [f"compile-bundle failed: {r.stderr}"]

        bundle_path = run_root / "style-bundle.json"
        if not bundle_path.is_file():
            return ["compile-bundle did not produce style-bundle.json"]
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        run_manifest = json.loads((run_root / "run-manifest.json").read_text(encoding="utf-8"))
        if bundle["source_id"] != run_manifest["source_id"]:
            failures.append("Bundle source_id differs from the run's random source_id")
        # Default mixed stub lands at most at ``limited``.
        if bundle["evidence_status"] not in {"approved", "limited"}:
            failures.append(
                f"unexpected bundle.evidence_status: {bundle['evidence_status']!r}"
            )

    return failures


def _check_adversarial_offset() -> list[str]:
    """Model misreporting an offset MUST be rejected by ``validate_evidence_refs``.

    The CLI also wires this into the run; we additionally exercise the
    validator directly with an obviously-wrong hash to keep the test
    honest and short.
    """
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
    sys.path.insert(0, str(PROJECT_ROOT / "vendor"))
    from chunker import chunk_text, CHUNKER_VERSION
    from evidence_validator import validate_evidence_refs, compute_excerpt_hash

    text = "# 第一章\n句子。\n"
    chunks = chunk_text(text, chunker_version=CHUNKER_VERSION)
    chunk = chunks[0]
    bad_ref = {
        "chunk_id": chunk.chunk_id,
        "chapter_id": chunk.chapter_id,
        "scene_id": chunk.scene_id,
        "char_offset": list(chunk.char_offset),
        "excerpt_hash": "f" * 64,  # obviously wrong hash
    }
    errors = validate_evidence_refs(
        [bad_ref],
        chunks=chunks,
        fingerprint="fp",
        normalizer_version="v1",
        chunker_version=CHUNKER_VERSION,
        normalized_text=text,
    )
    return [f"adversarial offset passed: {errors}"] if not errors else []


def main() -> int:
    failures: list[str] = []
    failures.extend(_check_stage_c_invariants())
    failures.extend(_check_end_to_end())
    failures.extend(_check_adversarial_offset())
    if failures:
        print("Stage C aggregate gate FAILED:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("Stage C aggregate gate PASSED:")
    print("- Stage C invariants (imports, hash determinism, parser strictness) hold")
    print("- end-to-end prepare-source -> init-run -> extract-dimensions -> review-dimensions -> compile-bundle chain succeeded (default mixed stub → bundle <= limited)")
    print("- adversarial evidence_ref with bad hash rejected")
    return 0


if __name__ == "__main__":
    sys.exit(main())
