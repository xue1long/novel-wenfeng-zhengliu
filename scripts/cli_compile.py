"""Stage E Task 6: thin CLI for the deterministic compiler.

Lives next to the Stage B / C CLIs and exposes two subcommands:
  - compile      --staging-root <path> --bundle <bundle.json> ... 
                  [--templates-root <templates/stages>]
  - validate-dist --staging-root <path> [--run-root <path>]

Exit codes:
  0 — success
  1 — data / contract / authorization error
  2 — path / IO error
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from deterministic_compiler import (
    CompilerError,
    ExistingStagingRootError,
    compile_six_skills,
    validate_dist,
)
from path_safety import (
    PathEscapeError,
    assert_within_run_root,
)


def _load_bundle(bundle_path: Path) -> dict:
    if not bundle_path.is_file():
        print(f"bundle file not found: {bundle_path}")
        sys.exit(2)
    try:
        return json.loads(bundle_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"bundle is not valid JSON: {exc}")
        sys.exit(2)


def _resolve_run_root(staging_root: Path, run_root: Path | None) -> Path:
    if run_root is not None:
        return Path(run_root).resolve()
    return Path(staging_root).resolve().parent


def cmd_compile(args: argparse.Namespace) -> int:
    bundle = _load_bundle(Path(args.bundle).resolve())
    staging_root = Path(args.staging_root).resolve()
    templates_root = Path(args.templates_root).resolve()
    run_root = Path(args.run_root).resolve()
    try:
        assert_within_run_root(run_root, staging_root)
    except PathEscapeError as exc:
        print(f"path safety violation: {exc}")
        return 2
    try:
        result = compile_six_skills(
            bundle,
            templates_root=templates_root,
            staging_root=staging_root,
            lock_root=run_root,
            lock_key=args.lock_key,
        )
    except ExistingStagingRootError as exc:
        print(f"compile refused: {exc}")
        return 2
    except (CompilerError, FileNotFoundError, KeyError, ValueError) as exc:
        print(f"compile failed: {exc}")
        return 1
    print(
        f"compiled {len(result.manifest['skill_hashes'])} skills into "
        f"{staging_root}; manifest_version={result.manifest['manifest_version']}"
    )
    return 0


def cmd_validate_dist(args: argparse.Namespace) -> int:
    staging_root = Path(args.staging_root).resolve()
    run_root = _resolve_run_root(staging_root, args.run_root)
    try:
        assert_within_run_root(run_root, staging_root)
    except PathEscapeError as exc:
        print(f"path safety violation: {exc}")
        return 2
    errors = validate_dist(staging_root, run_root=run_root)
    if errors:
        for err in errors:
            print(f"- {err}")
        return 1
    print(f"staging {staging_root} validated")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Stage E thin CLI.")
    sub = parser.add_subparsers(dest="command", required=True)

    c = sub.add_parser("compile", help="compile six skills into staging")
    c.add_argument("--staging-root", required=True)
    c.add_argument("--run-root", required=True)
    c.add_argument("--bundle", required=True)
    c.add_argument("--templates-root", default="templates/stages")
    c.add_argument("--lock-key", default="wenfeng.compile")
    c.set_defaults(func=cmd_compile)

    v = sub.add_parser("validate-dist", help="verify a frozen staging against its manifest")
    v.add_argument("--staging-root", required=True)
    v.add_argument("--run-root", default=None)
    v.set_defaults(func=cmd_validate_dist)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())