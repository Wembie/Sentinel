#!/usr/bin/env python3
"""Bump VERSION and sync static manifests in one command.

Examples:
    python scripts/release/bump_version.py 1.0.1
    python scripts/release/bump_version.py patch
    python scripts/release/bump_version.py minor --commit
    python scripts/release/bump_version.py 2.0.0 --dry-run
"""
from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

import sync_version

ROOT = sync_version.ROOT
VERSION_FILE = ROOT / "VERSION"
RELEASE_RE = re.compile(r"^(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)(?:[-+].+)?$")
BUMP_KINDS = {"major", "minor", "patch"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Update VERSION and sync all static manifests."
    )
    parser.add_argument(
        "target",
        help="Exact version (e.g. 1.0.1) or bump kind: major, minor, patch.",
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Create a git commit with only the version-sync files.",
    )
    parser.add_argument(
        "--message",
        help="Custom commit message. Only used with --commit.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the changes that would be made without writing files.",
    )
    return parser.parse_args()


def resolve_target_version(current_version: str, target: str) -> str:
    normalized = target.strip().lower()
    if normalized in BUMP_KINDS:
        match = RELEASE_RE.fullmatch(current_version)
        if not match:
            raise ValueError(
                "Automatic major/minor/patch bumps require VERSION to be in X.Y.Z format."
            )
        major = int(match.group("major"))
        minor = int(match.group("minor"))
        patch = int(match.group("patch"))
        if normalized == "major":
            return f"{major + 1}.0.0"
        if normalized == "minor":
            return f"{major}.{minor + 1}.0"
        return f"{major}.{minor}.{patch + 1}"

    if not sync_version.is_valid_semver(target):
        raise ValueError(
            f"Invalid version {target!r}. Use semver like 1.0.1 or a bump kind."
        )
    return target


def _write_version(current_version: str, target_version: str, *, dry_run: bool = False) -> bool:
    if current_version == target_version:
        print(f"  OK   VERSION: already {target_version!r}")
        return False
    if dry_run:
        print(f"  DRY  VERSION: {current_version!r} -> {target_version!r}")
        return True
    VERSION_FILE.write_text(f"{target_version}\n", encoding="utf-8")
    print(f"  BUMP VERSION: {current_version!r} -> {target_version!r}")
    return True


def bump_version(target: str, *, dry_run: bool = False) -> tuple[str, bool, int]:
    current_version = sync_version.read_version(VERSION_FILE)
    target_version = resolve_target_version(current_version, target)

    print(f"Bumping project version toward {target_version!r}...\n")
    version_changed = _write_version(current_version, target_version, dry_run=dry_run)
    manifest_changes = sync_version.sync_static_manifests(target_version, dry_run=dry_run)
    return target_version, version_changed, manifest_changes


def maybe_commit(target_version: str, message: str | None = None) -> bool:
    paths = [VERSION_FILE, *sync_version.JSON_TARGETS, *sync_version.YAML_TARGETS]
    rel_paths = [str(path.relative_to(ROOT)) for path in paths]

    subprocess.run(["git", "add", "--", *rel_paths], cwd=ROOT, check=True)

    diff_result = subprocess.run(
        ["git", "diff", "--cached", "--quiet", "--", *rel_paths],
        cwd=ROOT,
        check=False,
    )
    if diff_result.returncode == 0:
        print("No version-sync changes to commit.")
        return False
    if diff_result.returncode != 1:
        raise subprocess.CalledProcessError(diff_result.returncode, diff_result.args)

    commit_message = message or f"chore: bump version to {target_version}"
    subprocess.run(
        ["git", "commit", "-m", commit_message, "--", *rel_paths],
        cwd=ROOT,
        check=True,
    )
    print(f"Created commit: {commit_message}")
    return True


def main() -> None:
    args = parse_args()
    if args.dry_run and args.commit:
        raise SystemExit("ERROR: --commit cannot be used with --dry-run")
    if args.message and not args.commit:
        raise SystemExit("ERROR: --message requires --commit")

    target_version, version_changed, manifest_changes = bump_version(
        args.target, dry_run=args.dry_run
    )

    total_changed = int(version_changed) + manifest_changes
    print()
    if args.dry_run:
        print(f"Dry-run complete. {total_changed} file(s) would be updated.")
        return

    print(f"Done. {total_changed} file(s) updated.")
    if args.commit:
        maybe_commit(target_version, args.message)


if __name__ == "__main__":
    main()
