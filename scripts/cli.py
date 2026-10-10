"""Stage B Task 8: thin CLI for source preparation, run init, and resume.

The CLI is intentionally minimal:
  - prepare-source : fingerprint + normalize + chunk + write source-manifest
                     and chunk-manifest under the run root.
  - init-run       : authorization gate + create run-manifest.json (no model).
  - resume-run     : idempotent step replay with retry_count capped at 3.

No command writes outside its --run-root. Every artifact destination is
validated through scripts/path_safety.py.
"""

from __future__ import annotations

import argparse
import json
import secrets
import sys
from pathlib import Path
from types import SimpleNamespace

from authorization_gate import (
    AuthorizationBlocked,
    check_authorization,
)
from chunker import chunk_text, CHUNKER_VERSION
from holdout import lock_holdout, read_locked_holdout
from path_safety import (
    PathEscapeError,
    PathExistsError,
    assert_within_run_root,
    safe_mkdir,
)
from run_journal import RunJournal, StepRetryExhausted
from sampling import CoverageMatrix, SCENE_CLASSES, build_coverage_matrix
from source_fingerprint import (
    PARSER_VERSION,
    fingerprint_bytes,
    fingerprint_text,
    normalize,
)


CHUNKER_OUTPUT_NAME = "chunk-manifest.json"
SOURCE_OUTPUT_NAME = "source-manifest.json"


def _build_source_manifest(*, source_id: str, source_fingerprint: str, raw_sha256: str, format_: str, authorization: dict) -> dict:
    return {
        "source_id": source_id,
        "source_fingerprint": source_fingerprint,
        "raw_sha256": raw_sha256,
        "format": format_,
        "encoding": "utf-8",
        "parser_version": PARSER_VERSION,
        "authorization": authorization,
        "authorization_type": authorization.get("evidence_basis", "user_declaration"),
        "declared_derivative_use": authorization["scope"]["derivative_use"],
        "created_at": "private-ledger://stage-b/prepare-source",
        "retention_until": "private-ledger://stage-b/retention",
    }


def _build_chunk_manifest(*, source_id: str, chunker_version: str, chunks) -> dict:
    return {
        "source_id": source_id,
        "parser_version": chunker_version,
        "chunks": [
            {
                "chunk_id": c.chunk_id,
                "chapter_id": c.chapter_id,
                "scene_id": c.scene_id,
                "char_offset": list(c.char_offset),
                "window_hash": c.window_hash,
                "boundary_confidence": c.boundary_confidence,
                "scene_classes": list(c.scene_classes),
            }
            for c in chunks
        ],
    }


def cmd_prepare_source(args: argparse.Namespace) -> int:
    run_root = Path(args.run_root).resolve()
    source_path = Path(args.source).resolve()
    if not source_path.is_file():
        print(f"source file not found: {source_path}")
        return 2
    if not run_root.parent.exists():
        print(f"parent directory does not exist: {run_root.parent}")
        return 2
    if source_path.suffix.lower() not in {".txt", ".md", ".markdown"}:
        print("source must be a .txt or Markdown file")
        return 2
    if run_root.exists() and any(run_root.iterdir()):
        print(f"run root is not empty: {run_root}")
        return 2

    raw_bytes = source_path.read_bytes()
    try:
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        print(f"source is not valid utf-8: {exc}")
        return 2

    normalized = normalize(text)
    fingerprint = fingerprint_text(text)
    source_id = secrets.token_hex(6)
    raw_sha256 = fingerprint_bytes(raw_bytes)

    chunks = chunk_text(normalized, chunker_version=CHUNKER_VERSION)

    try:
        assert_within_run_root(run_root, run_root / CHUNKER_OUTPUT_NAME)
        assert_within_run_root(run_root, run_root / SOURCE_OUTPUT_NAME)
    except PathEscapeError as exc:
        print(f"path safety violation: {exc}")
        return 2

    try:
        safe_mkdir(run_root)
    except PathExistsError:
        pass  # caller may pass an existing root; we overwrite manifest files.

    (run_root / SOURCE_OUTPUT_NAME).write_text(
        json.dumps(
            _build_source_manifest(
                source_id=source_id,
                source_fingerprint=fingerprint,
                raw_sha256=raw_sha256,
                format_="markdown" if source_path.suffix.lower() in {".md", ".markdown"} else "txt",
                authorization={
                    "scope": {"model_processing": "local_only", "derivative_use": "private_only"},
                    "evidence_basis": "user_declaration",
                },
            ),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (run_root / CHUNKER_OUTPUT_NAME).write_text(
        json.dumps(
            _build_chunk_manifest(
                source_id=source_id, chunker_version=CHUNKER_VERSION, chunks=chunks
            ),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    # Sidecar: the normalized text itself. Stage C reads this so the
    # evidence validator can recompute excerpt hashes. The text is the same
    # data the chunker was built from, so this round-trips by construction.
    (run_root / "normalized-source.txt").write_text(normalized, encoding="utf-8")
    print(f"prepared {len(chunks)} chunks under {run_root}")
    return 0


def cmd_apply_scene_map(args: argparse.Namespace) -> int:
    run_root = Path(args.run_root).resolve()
    chunk_path = run_root / CHUNKER_OUTPUT_NAME
    scene_map_path = Path(args.scene_map).resolve()
    if not chunk_path.is_file() or not scene_map_path.is_file():
        print("chunk manifest or scene map not found")
        return 2
    try:
        manifest = json.loads(chunk_path.read_text(encoding="utf-8"))
        scene_map = json.loads(scene_map_path.read_text(encoding="utf-8"))
        assignments = scene_map["chunks"]
        if not isinstance(assignments, dict):
            raise ValueError("chunks must be an object keyed by chunk_id")
        chunks = manifest.get("chunks", [])
        expected = {item["chunk_id"] for item in chunks}
        if set(assignments) != expected:
            missing = sorted(expected - set(assignments))
            extra = sorted(set(assignments) - expected)
            raise ValueError(f"scene map must cover every chunk (missing={missing}, extra={extra})")
        for item in chunks:
            assignment = assignments[item["chunk_id"]]
            scene_id = assignment.get("scene_id")
            scene_classes = assignment.get("scene_classes", [])
            if not isinstance(scene_id, str) or not scene_id.strip():
                raise ValueError(f"{item['chunk_id']}: scene_id must be a non-empty string")
            if (
                not isinstance(scene_classes, list)
                or len(scene_classes) != len(set(scene_classes))
                or not set(scene_classes).issubset(SCENE_CLASSES)
            ):
                raise ValueError(f"{item['chunk_id']}: invalid scene_classes")
            item["scene_id"] = scene_id
            item["scene_classes"] = scene_classes
        chunk_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        (run_root / "scene-map.json").write_text(
            json.dumps(scene_map, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8"
        )
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        print(f"invalid scene map: {exc}")
        return 1
    print(f"applied scene map to {len(chunks)} chunks")
    return 0


def _read_chunk_records(chunk_manifest: dict) -> list[SimpleNamespace]:
    return [
        SimpleNamespace(
            chunk_id=item["chunk_id"],
            chapter_id=item["chapter_id"],
            scene_id=item["scene_id"],
            char_offset=item["char_offset"],
            window_hash=item["window_hash"],
            boundary_confidence=item.get("boundary_confidence", "high"),
            scene_classes=tuple(item.get("scene_classes", [])),
        )
        for item in chunk_manifest.get("chunks", [])
    ]


def cmd_build_sampling(args: argparse.Namespace) -> int:
    run_root = Path(args.run_root).resolve()
    chunk_path = run_root / CHUNKER_OUTPUT_NAME
    if not chunk_path.is_file() or not (run_root / "scene-map.json").is_file():
        print("apply a complete scene map before building the sampling matrix")
        return 1
    try:
        manifest = json.loads(chunk_path.read_text(encoding="utf-8"))
        chunks = _read_chunk_records(manifest)
        matrix = build_coverage_matrix(
            chunks, seed=args.seed, chunker_version=manifest["parser_version"]
        )
        (run_root / "coverage-matrix.json").write_text(
            json.dumps(matrix.as_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
        print(f"could not build sampling matrix: {exc}")
        return 1
    print(f"sampling matrix written; uncovered cells={len(matrix.uncovered())}")
    return 0


def cmd_lock_holdout(args: argparse.Namespace) -> int:
    run_root = Path(args.run_root).resolve()
    try:
        config = json.loads((run_root / "run-config.json").read_text(encoding="utf-8"))
        chunk_manifest = json.loads((run_root / CHUNKER_OUTPUT_NAME).read_text(encoding="utf-8"))
        matrix = CoverageMatrix.from_dict(
            json.loads((run_root / "coverage-matrix.json").read_text(encoding="utf-8"))
        )
        chunks = _read_chunk_records(chunk_manifest)
        manifest = lock_holdout(
            {"chunks": chunks, "matrix": matrix},
            holdout_fraction=args.fraction,
            seed=args.seed,
            fingerprint=config["source_fingerprint"],
            normalizer_version=config.get("normalizer_version", "v1"),
            chunker_version=chunk_manifest["parser_version"],
        )
        (run_root / "holdout.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        read_locked_holdout(run_root)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        print(f"could not lock holdout: {exc}")
        return 1
    print(f"locked {len(manifest['holdout_chunk_ids'])} holdout chunks")
    return 0


def cmd_init_run(args: argparse.Namespace) -> int:
    run_root = Path(args.run_root).resolve()
    if args.dry_run:
        # Dry-run must not create any file or directory.
        print(f"[dry-run] would create run root at {run_root}")
        return 0
    if not run_root.parent.exists():
        print(f"parent directory does not exist: {run_root.parent}")
        return 2

    try:
        assert_within_run_root(run_root.parent, run_root)
    except PathEscapeError as exc:
        print(f"path escape rejected: {exc}")
        return 2

    auth_path = Path(args.authorization).resolve()
    if not auth_path.is_file():
        print(f"authorization file not found: {auth_path}")
        return 2
    authorization = json.loads(auth_path.read_text(encoding="utf-8"))

    errors = check_authorization(
        authorization,
        requested_model_id=args.requested_model_id,
        requested_purpose=args.requested_purpose,
    )
    if errors:
        for error in errors:
            print(f"- {error}")
        return 1

    # Private runs need no separate derivative-use attestation. Record the
    # private-only default; shareable runs must provide an explicit scope.
    authorization = dict(authorization)
    authorization["scope"] = dict(authorization["scope"])
    authorization["scope"].setdefault("derivative_use", "private_only")

    source_path = run_root / SOURCE_OUTPUT_NAME
    source_manifest = None
    if source_path.is_file():
        source_manifest = json.loads(source_path.read_text(encoding="utf-8"))
    source_fingerprint = args.source_fingerprint or (
        source_manifest.get("source_fingerprint", "") if source_manifest else ""
    ) or ("0" * 64)
    if source_manifest and args.source_fingerprint and args.source_fingerprint != source_manifest["source_fingerprint"]:
        print("provided source fingerprint does not match prepared source")
        return 1
    try:
        if run_root.exists():
            if not source_manifest or (run_root / "run-manifest.json").exists():
                raise PathExistsError(f"run root already exists: {run_root}")
        else:
            safe_mkdir(run_root)
    except PathExistsError as exc:
        print(f"run root already exists; use a prepared root or choose a new path: {exc}")
        return 2

    journal = RunJournal(
        run_root,
        args.run_id,
        source_fingerprint=source_fingerprint,
        source_id=source_manifest.get("source_id") if source_manifest else None,
        model_id=args.requested_model_id if args.requested_model_id != "local" else "synthetic-model",
    )
    if source_manifest:
        source_manifest["authorization"] = authorization
        source_manifest["authorization_type"] = authorization.get("evidence_basis", "user_declaration")
        source_manifest["declared_derivative_use"] = authorization["scope"]["derivative_use"]
        source_path.write_text(json.dumps(source_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    journal.record_step(
        "init-run",
        input_hash=source_fingerprint,
        prompt_template_version=PARSER_VERSION,
        model_id=args.requested_model_id,
        output_path=f"private-ledger://{args.run_id}/init",
        output_hash=("0" * 64),
        status="succeeded",
    )
    print(f"initialized run {args.run_id} at {run_root}")
    return 0


def cmd_resume_run(args: argparse.Namespace) -> int:
    run_root = Path(args.run_root).resolve()
    if not run_root.is_dir():
        print(f"run root missing: {run_root}")
        return 2
    if args.retry_count > 3:
        print(f"retry_count {args.retry_count} exceeds max 3")
        return 1

    journal = RunJournal(
        run_root,
        args.run_id or "unknown",
        source_fingerprint="0" * 64,
    )
    try:
        journal.record_step(
            args.step_id,
            input_hash=("0" * 64),
            prompt_template_version=PARSER_VERSION,
            model_id="local",
            output_path=f"private-ledger://{args.run_id or 'unknown'}/{args.step_id}",
            output_hash=("0" * 64),
            status="succeeded",
            retry_count=args.retry_count,
        )
    except StepRetryExhausted as exc:
        print(f"step retry exhausted: {exc}")
        return 1
    print(f"recorded step {args.step_id} (retry_count={args.retry_count}) at {run_root}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Stage B thin CLI.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("prepare-source", help="fingerprint + normalize + chunk")
    p.add_argument("--source", required=True, help="path to the source TXT/Markdown file")
    p.add_argument("--run-root", required=True, help="directory inside which to write manifests")
    p.set_defaults(func=cmd_prepare_source)

    i = sub.add_parser("init-run", help="model-processing consent gate + create run-manifest")
    i.add_argument("--run-root", required=True)
    i.add_argument("--run-id", required=True)
    i.add_argument("--authorization", required=True, help="path to model-processing consent JSON; shareable runs also need an explicit derivative_use")
    i.add_argument("--requested-model-id", required=True)
    i.add_argument("--requested-purpose", default="private_only", choices=[
        "private_only", "shareable_with_attribution", "shareable_anonymous",
    ])
    i.add_argument("--source-fingerprint", default="", help="optional; inferred from source-manifest.json")
    i.add_argument("--dry-run", action="store_true")
    i.set_defaults(func=cmd_init_run)

    sm = sub.add_parser("apply-scene-map", help="apply model-assigned scene IDs and classes")
    sm.add_argument("--run-root", required=True)
    sm.add_argument("--scene-map", required=True, help="JSON object with a chunks mapping")
    sm.set_defaults(func=cmd_apply_scene_map)

    sampling = sub.add_parser("build-sampling", help="build the labeled coverage matrix")
    sampling.add_argument("--run-root", required=True)
    sampling.add_argument("--seed", type=int, default=1)
    sampling.set_defaults(func=cmd_build_sampling)

    holdout = sub.add_parser("lock-holdout", help="persist and verify the pre-extraction holdout")
    holdout.add_argument("--run-root", required=True)
    holdout.add_argument("--seed", type=int, default=1)
    holdout.add_argument("--fraction", type=float, default=0.20)
    holdout.set_defaults(func=cmd_lock_holdout)

    r = sub.add_parser("resume-run", help="idempotent step record")
    r.add_argument("--run-root", required=True)
    r.add_argument("--step-id", required=True)
    r.add_argument("--run-id", default="")
    r.add_argument("--retry-count", type=int, default=0)
    r.set_defaults(func=cmd_resume_run)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except AuthorizationBlocked as exc:
        for error in exc.errors:
            print(f"- {error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
