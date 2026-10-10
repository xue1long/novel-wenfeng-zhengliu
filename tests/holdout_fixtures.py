"""Helpers for tests that need a real persisted holdout lock."""

from __future__ import annotations

import json
import subprocess
import sys
from types import SimpleNamespace
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from holdout import lock_holdout  # noqa: E402
from sampling import build_coverage_matrix  # noqa: E402


def _run_cli(*args: str) -> None:
    result = subprocess.run(
        [sys.executable, "scripts/cli.py", *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    if result.returncode:
        raise AssertionError(result.stdout + result.stderr)


def persist_test_holdout(root: Path, fingerprint: str) -> None:
    """Write the minimal real lock files needed by journal unit tests."""
    chunks = [SimpleNamespace(
        chunk_id=f"SC{i:03d}-000",
        chapter_id="C001",
        scene_id=f"SC{i:03d}",
        scene_classes=("daily",),
        char_offset=[i * 10, (i + 1) * 10],
        window_hash=f"{i:064x}",
    ) for i in range(9)]
    matrix = build_coverage_matrix(chunks, seed=1, chunker_version="v1")
    lock = lock_holdout(
        {"chunks": chunks, "matrix": matrix},
        holdout_fraction=0.2,
        seed=1,
        fingerprint=fingerprint,
        normalizer_version="v1",
        chunker_version="v1",
    )
    (root / "run-config.json").write_text(json.dumps({
        "source_fingerprint": fingerprint,
        "normalizer_version": "v1",
    }), encoding="utf-8")
    (root / "chunk-manifest.json").write_text(json.dumps({
        "parser_version": "v1",
        "chunks": [{
            "chunk_id": chunk.chunk_id,
            "chapter_id": chunk.chapter_id,
            "scene_id": chunk.scene_id,
            "scene_classes": list(chunk.scene_classes),
            "char_offset": chunk.char_offset,
            "window_hash": chunk.window_hash,
        } for chunk in chunks],
    }), encoding="utf-8")
    (root / "coverage-matrix.json").write_text(json.dumps(matrix.as_dict()), encoding="utf-8")
    (root / "holdout.json").write_text(json.dumps(lock), encoding="utf-8")


def prepare_locked_run(root: Path, text: str) -> Path:
    """Run the actual Stage B preparation, scene-map, sampling, and lock CLIs."""
    root.mkdir(parents=True, exist_ok=True)
    source = root / "novel.txt"
    source.write_text(text, encoding="utf-8")
    auth = root / "auth.json"
    auth.write_text(json.dumps({
        "scope": {"model_processing": "local_only", "derivative_use": "private_only"},
        "evidence_basis": "user_declaration",
    }), encoding="utf-8")
    run_root = root / "run"
    _run_cli("prepare-source", "--source", str(source), "--run-root", str(run_root))
    _run_cli(
        "init-run", "--run-root", str(run_root), "--run-id", "r1",
        "--authorization", str(auth), "--requested-model-id", "local",
        "--requested-purpose", "private_only",
    )
    chunks = json.loads((run_root / "chunk-manifest.json").read_text(encoding="utf-8"))["chunks"]
    scene_map = root / "scene-map.json"
    scene_map.write_text(json.dumps({
        "chunks": {
            chunk["chunk_id"]: {"scene_id": chunk["scene_id"], "scene_classes": ["daily"]}
            for chunk in chunks
        }
    }), encoding="utf-8")
    _run_cli("apply-scene-map", "--run-root", str(run_root), "--scene-map", str(scene_map))
    _run_cli("build-sampling", "--run-root", str(run_root))
    _run_cli("lock-holdout", "--run-root", str(run_root))
    return run_root
