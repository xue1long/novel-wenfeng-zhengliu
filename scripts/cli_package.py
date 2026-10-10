"""Stage G Task 6: thin CLI for package / install / verify-package / purge-run.

Lives next to ``scripts/cli.py`` / ``cli_extract.py`` / ``cli_compile.py`` /
``cli_evaluate.py``. Four subcommands (Ruling-G8):

  - ``package``  : run final source scan, build deterministic directory +
    ZIP, write release-manifest. Two profiles: ``shareable`` (default
    behavior) / ``private-preview`` (run-root private only).
  - ``install``  : dry-run is the default and does not touch the target;
    ``--apply --scope user --target <path>`` explicitly installs.
  - ``verify-package`` : extracts to a managed tmpdir and runs cross-stage
    verification (release-manifest self-consistency + 6 Skill hashes + stage
    F eval-report redaction + final_state). Never modifies the package.
  - ``purge-run`` : removes ``run_root/dist/`` private preview directories
    only. Never touches ``dist/<source_id>/<bundle_version>/``.

Exit codes:
  0 — success
  1 — invariant failure
  2 — path / IO / state-gate failure
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

from deterministic_package import (
    build_directory_dist,
    build_zip_dist,
    compute_zip_hash,
)
from final_source_scan import (
    SourceScanPolicy,
    evaluate_scan_coverage,
    final_source_scan,
    write_scan_report,
)
from isolated_install import (
    IsolatedInstallError,
    dry_run_install,
    user_install,
    verify_package,
)
from package_state_gate import (
    PackageGateError,
    PackageProfile,
    assert_decision,
)
from path_safety import PathEscapeError, assert_within_run_root
from release_manifest import (
    ReleaseManifestError,
    build_release_manifest,
    write_release_manifest,
)


def _read_final_state(staging_root: Path) -> tuple[str, str]:
    eval_path = staging_root / "eval-report.json"
    if not eval_path.is_file():
        raise PackageGateError("eval-report.json missing; run stage F first")
    report = json.loads(eval_path.read_text(encoding="utf-8"))
    return report.get("summary", {}).get("final_state", ""), report.get(
        "bundle_id", ""
    )


def cmd_package(args: argparse.Namespace) -> int:
    staging_root = Path(args.staging_root).resolve()
    run_root = Path(args.run_root).resolve()
    profile = PackageProfile(args.profile)
    output_dir = Path(args.output_dir).resolve()

    try:
        assert_within_run_root(run_root, staging_root)
    except PathEscapeError as exc:
        print(f"path safety violation: {exc}")
        return 2

    final_state, bundle_id = _read_final_state(staging_root)

    # Decide whether to proceed.
    try:
        # authorization_purpose is read from the run manifest if present,
        # otherwise default to private_only.
        auth_purpose = "private_only"
        rm_path = Path(args.run_manifest).resolve() if args.run_manifest else None
        if rm_path and rm_path.is_file():
            data = json.loads(rm_path.read_text(encoding="utf-8"))
            auth_purpose = data.get("authorization_purpose", "private_only")
        assert_decision(final_state, auth_purpose, profile)
    except PackageGateError as exc:
        print(f"package refused: {exc}")
        return 2

    compile_manifest = json.loads(
        (staging_root / "compile-manifest.json").read_text(encoding="utf-8")
    )
    source_id = compile_manifest.get("source_id", "")
    if not re.fullmatch(r"[0-9a-f]{12}", source_id):
        print("compile-manifest.json must contain a non-semantic 12-character source_id")
        return 1

    # Final source scan.
    policy = SourceScanPolicy.default()
    scan = final_source_scan(staging_root, policy)
    coverage_errors = evaluate_scan_coverage(scan)
    if coverage_errors:
        print(f"final source scan failed: {coverage_errors}")
        return 1
    if profile == PackageProfile.SHAREABLE:
        scan_dir = output_dir
    else:
        scan_dir = run_root / "dist" / "private"
    write_scan_report(scan, scan_dir)

    # Build directory dist.
    if profile == PackageProfile.SHAREABLE:
        dist_dir = output_dir / source_id / (bundle_id or "bundle") / "v0.1.0"
    else:
        dist_dir = run_root / "dist" / "private" / (bundle_id or "bundle")
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    # Build the directory dist without the release manifest first; the
    # manifest is written *after* the ZIP is built so its hash can be
    # embedded in the manifest itself (Ruling-G2).
    build_directory_dist(staging_root, {}, output_dir=dist_dir,
                          include_scan_report=True)

    # Build the ZIP and compute its hash.
    zip_path = dist_dir / "package.zip"
    if zip_path.exists():
        zip_path.unlink()
    build_zip_dist(dist_dir, zip_path)
    zip_hash = compute_zip_hash(zip_path)

    # Compute compile-manifest hash + eval-report hash.
    compile_manifest_bytes = (staging_root / "compile-manifest.json").read_bytes()
    compile_manifest_hash = hashlib.sha256(compile_manifest_bytes).hexdigest()
    eval_report_bytes = (staging_root / "eval-report.json").read_bytes()
    eval_report_hash = hashlib.sha256(eval_report_bytes).hexdigest()

    # Gate status reflects trigger / output / end-to-end pass-state.
    gate_status = {
        "trigger": bool(compile_manifest.get("evidence_status", "") in ("approved", "limited")),
        "output": True,  # mechanical_pass_rate 1.0 is already enforced by stage F.
        "end_to_end": bool(compile_manifest.get("evidence_status", "") == "approved"),
    }

    # Build the release manifest.
    final_scan_result = {
        "policy": scan["policy"],
        "scanned_at_marker": "",
        "coverage_ratio": scan["coverage_ratio"],
        "coverage_target": scan["coverage_target"],
        "covered_targets": scan["covered_targets"],
        "total_targets": scan["total_targets"],
    }
    try:
        manifest = build_release_manifest(
            staging_root,
            bundle_id=bundle_id or "bundle-x-v0_1_0",
            source_id=source_id,
            authorization_purpose=auth_purpose,
            release_state=final_state,
            eval_report_hash=eval_report_hash,
            final_scan_result=final_scan_result,
            zip_path=zip_path,
            compile_manifest_hash=compile_manifest_hash,
            gate_status=gate_status,
        )
    except ReleaseManifestError as exc:
        print(f"release manifest build failed: {exc}")
        return 1
    try:
        write_release_manifest(manifest, dist_dir)
    except ReleaseManifestError as exc:
        print(f"release manifest write failed: {exc}")
        return 1

    print(
        f"package {profile.value} succeeded; dist_dir={dist_dir}; zip={zip_path}"
    )
    return 0


def cmd_install(args: argparse.Namespace) -> int:
    package_path = Path(args.package).resolve()
    run_root = Path(args.run_root).resolve()
    if not package_path.is_file():
        print(f"package not found: {package_path}")
        return 2
    if not args.apply:
        target = Path(args.target).resolve() if args.target else run_root / "dry-run-target"
        try:
            result = dry_run_install(
                package_path,
                target=target,
                run_root=run_root,
            )
        except IsolatedInstallError as exc:
            print(f"install dry-run failed: {exc}")
            return 2
        if not result.get("verify_result", {}).get("ok"):
            print(f"install dry-run verify failed: {result.get('verify_result')}")
            return 1
        print(f"install dry-run ok; target={target} unchanged")
        return 0

    if args.scope != "user":
        print(f"only --scope user is supported; got {args.scope!r}")
        return 2
    target = Path(args.target).resolve() if args.target else None
    if target is None:
        print("--scope user requires --target <path>")
        return 2
    try:
        result = user_install(
            package_path,
            target=target,
            run_root=run_root,
            force=args.force,
        )
    except IsolatedInstallError as exc:
        print(f"install failed: {exc}")
        return 2
    print(f"installed into {target}; files={len(result['files'])}")
    return 0


def cmd_verify_package(args: argparse.Namespace) -> int:
    package_path = Path(args.package).resolve()
    run_root = Path(args.run_root).resolve()
    if not package_path.is_file():
        print(f"package not found: {package_path}")
        return 2
    try:
        result = verify_package(package_path, run_root=run_root)
    except IsolatedInstallError as exc:
        print(f"verify-package failed: {exc}")
        return 2
    if not result.get("ok"):
        print(f"verify-package FAILED: {result}")
        return 1
    print(f"verify-package ok; tmpdir={result.get('tmpdir')}")
    return 0


def cmd_purge_run(args: argparse.Namespace) -> int:
    run_root = Path(args.run_root).resolve()
    private = run_root / "dist"
    if private.exists():
        for child in list(private.iterdir()):
            if child.is_dir() and not child.is_symlink():
                shutil.rmtree(child)
            else:
                child.unlink()
        private.rmdir()
    print(f"purged run_root/dist under {run_root}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Stage G thin CLI.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("package", help="build deterministic dist + release-manifest")
    p.add_argument("--staging-root", required=True)
    p.add_argument("--run-root", required=True)
    p.add_argument("--output-dir", required=True,
                   help="where to write shareable dist (default for shareable profile)")
    p.add_argument("--run-manifest", default=None,
                   help="optional run-manifest.json; supplies authorization_purpose")
    p.add_argument("--profile", default="shareable",
                   choices=[p.value for p in PackageProfile])
    p.set_defaults(func=cmd_package)

    i = sub.add_parser("install", help="verify by default; use --apply to write files")
    i.add_argument("--package", required=True)
    i.add_argument("--run-root", required=True)
    i.add_argument("--target", default=None)
    i.add_argument("--scope", default="user", choices=["user"],
                   help="only --scope user is supported; system is rejected")
    apply_group = i.add_mutually_exclusive_group()
    apply_group.add_argument("--dry-run", dest="apply", action="store_false",
                             help="extract to a tmpdir and verify (default)")
    apply_group.add_argument("--apply", dest="apply", action="store_true",
                             help="write the verified package to --target")
    i.set_defaults(apply=False)
    i.add_argument("--force", action="store_true",
                   help="overwrite an existing non-empty target (user scope only)")
    i.set_defaults(func=cmd_install)

    v = sub.add_parser("verify-package", help="verify a package in a tmpdir")
    v.add_argument("--package", required=True)
    v.add_argument("--run-root", required=True)
    v.set_defaults(func=cmd_verify_package)

    g = sub.add_parser("purge-run", help="remove run_root/dist/ private previews")
    g.add_argument("--run-root", required=True)
    g.set_defaults(func=cmd_purge_run)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
