"""Stage C Task 7: thin CLI for extraction / review / compile.

Lives next to ``scripts/cli.py`` (Stage B's CLI). Stage B's CLI exposes
``prepare-source`` / ``init-run`` / ``resume-run``; this one exposes
``extract-dimensions`` / ``review-dimensions`` / ``compile-bundle``.

The CLI does NOT call any model. ``--stub`` switches the dimension
extractors to ``_stub_model_call``. ``review-dimensions`` reads a
caller-supplied JSON file (the factory Skill writes one of these per run)
and merges the model verdicts into the candidate pool.

Exit codes:
  0 — success
  1 — data / contract / authorization error
  2 — path / IO error
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from bundle_compiler import compile_bundle
from chunker import CHUNKER_VERSION
from evidence_validator import (
    compute_excerpt_hash,
    validate_evidence_refs,
)
from extraction_journal import ExtractionJournal
from extractors import EXTRACTION_PROMPT_VERSIONS, _stub_model_call, extract_dimension
from mechanism_merger import classify_mechanism, compute_bundle_evidence_status
from path_safety import (
    PathEscapeError,
    PathExistsError,
    assert_within_run_root,
    safe_mkdir,
)
from review_parser import ReviewParseError, apply_review_to_candidate, parse_review_output
from source_fingerprint import normalize
from holdout import read_locked_holdout


SIX_STAGES_FOR_STAGE_BINDINGS = (
    "write_entry", "scene_design", "character_beats",
    "prose_draft", "style_check", "revision",
)


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_chunk_manifest(run_root: Path) -> dict:
    path = run_root / "chunk-manifest.json"
    if not path.is_file():
        raise FileNotFoundError(f"chunk-manifest.json missing at {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _load_holdout(run_root: Path) -> set[str]:
    data = read_locked_holdout(run_root)
    return set(data["holdout_chunk_ids"])


def _build_in_memory_chunks(chunk_manifest: dict) -> list:
    """Recreate ChunkRecord-style objects (need only the fields the validators use)."""
    class _Chunk:
        __slots__ = ("chunk_id", "chapter_id", "scene_id", "char_offset", "window_hash", "boundary_confidence", "text", "scene_classes")
        def __init__(self, d):
            self.chunk_id = d["chunk_id"]
            self.chapter_id = d["chapter_id"]
            self.scene_id = d["scene_id"]
            self.char_offset = (d["char_offset"][0], d["char_offset"][1])
            self.window_hash = d["window_hash"]
            self.boundary_confidence = d.get("boundary_confidence", "high")
            self.text = ""
            self.scene_classes = tuple(d.get("scene_classes", []))
    return [_Chunk(d) for d in chunk_manifest.get("chunks", [])]


def _populate_chunk_text(chunks: list, normalized_text: str) -> list:
    """Attach the canonical slice of normalized text to each chunk so the
    validator can recompute excerpt hashes against the actual text rather
    than relying on the chunker's cached window_hash alone."""
    for chunk in chunks:
        start, end = chunk.char_offset
        chunk.text = normalized_text[start:end]
    return chunks


def cmd_extract_dimensions(args: argparse.Namespace) -> int:
    run_root = Path(args.run_root).resolve()
    try:
        assert_within_run_root(run_root.parent, run_root)
    except PathEscapeError as exc:
        print(f"path escape rejected: {exc}")
        return 2
    if not run_root.is_dir():
        print(f"run root missing: {run_root}")
        return 2

    chunk_manifest = _load_chunk_manifest(run_root)
    chunks = _build_in_memory_chunks(chunk_manifest)
    try:
        holdout_ids = _load_holdout(run_root)
    except (OSError, ValueError, KeyError) as exc:
        print(f"valid holdout lock required before extraction: {exc}")
        return 1

    run_manifest = json.loads((run_root / "run-manifest.json").read_text(encoding="utf-8"))
    fingerprint = json.loads(
        (run_root / "run-config.json").read_text(encoding="utf-8")
    ).get("source_fingerprint", "0" * 64)
    journal = ExtractionJournal(
        run_root, args.run_id, source_fingerprint=fingerprint
    )

    # Stage C --stub mode reads the normalized text from the run root's
    # sidecar (`normalized-source.txt`) written by ``prepare-source``. This
    # round-trips with the chunker's window hashes by construction.
    if args.stub:
        sidecar = run_root / "normalized-source.txt"
        if sidecar.is_file():
            normalized_text = sidecar.read_text(encoding="utf-8")
        else:
            normalized_text = ""
    else:
        normalized_text = ""
    _populate_chunk_text(chunks, normalized_text)

    candidates_dir = run_root / "candidates"
    try:
        safe_mkdir(candidates_dir)
    except PathExistsError:
        pass

    summary: list[dict] = []
    for dimension in EXTRACTION_PROMPT_VERSIONS:
        journal.record_dimension_start(dimension)
        try:
            cands = extract_dimension(
                normalized_text=normalized_text,
                chunks=chunks,
                holdout_ids=holdout_ids,
                dimension=dimension,
                prompt_version=EXTRACTION_PROMPT_VERSIONS[dimension],
                chunker_version=CHUNKER_VERSION,
                # CLI always uses the local stub; the production path is the
                # ``wenfeng-distill`` factory Skill calling ``extract_dimension``
                # with its real ``model_call`` (Ruling-C5).
                model_call=None,
                profile=args.stub_profile if args.stub else None,
            )
            rejected: list[str] = []
            for c in cands:
                ref_errors = validate_evidence_refs(
                    c.get("evidence_refs", []),
                    chunks=chunks,
                    fingerprint=fingerprint,
                    normalizer_version="v1",
                    chunker_version=CHUNKER_VERSION,
                    normalized_text=normalized_text or None,
                )
                if ref_errors:
                    rejected.extend(ref_errors)
            if rejected:
                journal.record_dimension_failure(
                    dimension,
                    error_type="evidence_validation_failed",
                    error_detail="; ".join(rejected),
                )
                summary.append({
                    "dimension": dimension, "status": "failed",
                    "candidates": 0, "errors": rejected[:5],
                })
                continue
            payload = {
                "dimension": dimension,
                "extraction_prompt_version": EXTRACTION_PROMPT_VERSIONS[dimension],
                "candidates": cands,
            }
            out_path = candidates_dir / f"{dimension}.json"
            out_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            journal.record_dimension_checkpoint(
                dimension,
                candidates_path=str(out_path),
                candidates_hash=_hash_text(out_path.read_text(encoding="utf-8")),
                status="succeeded",
                retry_count=0,
            )
            summary.append({
                "dimension": dimension, "status": "succeeded",
                "candidates": len(cands),
            })
        except Exception as exc:  # noqa: BLE001 — Stage C keeps the run going
            journal.record_dimension_failure(
                dimension, error_type="extract_exception", error_detail=str(exc),
            )
            summary.append({
                "dimension": dimension, "status": "failed",
                "candidates": 0, "errors": [str(exc)],
            })
    (run_root / "extract-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"extracted {len(summary)} dimensions; see {run_root / 'extract-summary.json'}")
    return 0


def _normalize_review_file(raw: dict, dimension: str) -> dict[str, dict]:
    """Accept {dimension: [{mechanism_id, review_status, reasons}, ...]} or
    {dimension: {mechanism_id: review_status, ...}}.
    """
    out: dict[str, dict] = {}
    if dimension in raw:
        value = raw[dimension]
        if isinstance(value, list):
            for entry in value:
                mid = entry.get("mechanism_id")
                if mid:
                    out[mid] = {
                        "review_status": entry.get("review_status"),
                        "reasons": entry.get("reasons", []),
                    }
        elif isinstance(value, dict):
            for mid, status in value.items():
                if isinstance(status, str):
                    out[mid] = {
                        "review_status": status,
                        "reasons": [f"implicit support for {mid}"],
                    }
                elif isinstance(status, dict):
                    out[mid] = status
    return out


def cmd_review_dimensions(args: argparse.Namespace) -> int:
    run_root = Path(args.run_root).resolve()
    if not run_root.is_dir():
        print(f"run root missing: {run_root}")
        return 2
    review_file = Path(args.review_file).resolve()
    if not review_file.is_file():
        print(f"review file not found: {review_file}")
        return 2
    try:
        raw = json.loads(review_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"review file is not valid JSON: {exc}")
        return 1
    if not isinstance(raw, dict):
        print("review file must be a JSON object")
        return 1

    candidates_dir = run_root / "candidates"
    if not candidates_dir.is_dir():
        print(f"candidates dir missing: {candidates_dir}")
        return 2

    summary: list[dict] = []
    for path in sorted(candidates_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        dimension = data.get("dimension")
        verdicts = _normalize_review_file(raw, dimension)
        merged_count = 0
        for index, candidate in enumerate(data.get("candidates", [])):
            mid = candidate.get("mechanism_id")
            if mid not in verdicts:
                continue
            verdict = verdicts[mid]
            raw_review = json.dumps({
                "review_status": verdict["review_status"],
                "reasons": verdict["reasons"],
            })
            try:
                parsed = parse_review_output(raw_review)
            except ReviewParseError as exc:
                summary.append({"dimension": dimension, "mechanism_id": mid, "error": str(exc)})
                continue
            data["candidates"][index] = apply_review_to_candidate(candidate, parsed)
            merged_count += 1
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        summary.append({"dimension": dimension, "merged": merged_count})
    (run_root / "review-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"merged reviews for {len(summary)} dimensions")
    return 0


def cmd_compile_bundle(args: argparse.Namespace) -> int:
    run_root = Path(args.run_root).resolve()
    if not run_root.is_dir():
        print(f"run root missing: {run_root}")
        return 2
    candidates_dir = run_root / "candidates"
    if not candidates_dir.is_dir():
        print(f"candidates dir missing: {candidates_dir}")
        return 2

    all_candidates: list[dict] = []
    for path in sorted(candidates_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        all_candidates.extend(data.get("candidates", []))

    mechanisms = classify_mechanism(all_candidates)
    bundle_status = compute_bundle_evidence_status(mechanisms)

    run_manifest = json.loads((run_root / "run-manifest.json").read_text(encoding="utf-8"))

    try:
        bundle = compile_bundle(
            [m for m in mechanisms if m.bundle_status != "excluded"],
            source_id=run_manifest["source_id"],
            bundle_version=args.bundle_version,
        )
    except ValueError as exc:
        print(f"bundle compilation refused: {exc}")
        return 1

    out_path = run_root / "style-bundle.json"
    out_path.write_text(
        json.dumps(bundle, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"compiled Bundle ({bundle_status}) at {out_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Stage C thin CLI.")
    sub = parser.add_subparsers(dest="command", required=True)

    e = sub.add_parser("extract-dimensions")
    e.add_argument("--run-root", required=True)
    e.add_argument("--run-id", required=True)
    e.add_argument("--stub", action="store_true", help="use the deterministic stub model")
    e.add_argument("--stub-profile", default="mixed", choices=[
        "mixed", "all_supported", "all_limited", "all_unsupported",
    ])
    e.set_defaults(func=cmd_extract_dimensions)

    r = sub.add_parser("review-dimensions")
    r.add_argument("--run-root", required=True)
    r.add_argument("--review-file", required=True, help="path to JSON of model verdicts")
    r.set_defaults(func=cmd_review_dimensions)

    c = sub.add_parser("compile-bundle")
    c.add_argument("--run-root", required=True)
    c.add_argument("--bundle-version", default="0.1.0")
    c.set_defaults(func=cmd_compile_bundle)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
