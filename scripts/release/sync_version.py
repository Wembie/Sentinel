#!/usr/bin/env python3
"""Sync the VERSION file to all static manifests.

Run before tagging a release:
    python scripts/release/sync_version.py

Dry-run (print diffs, write nothing):
    python scripts/release/sync_version.py --dry-run

Check mode (exit non-zero if files need updates):
    python scripts/release/sync_version.py --check
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEMVER_RE = re.compile(r"\d+\.\d+\.\d+(?:[-+].+)?")

# JSON files where {"version": "<value>"} must be updated.
JSON_TARGETS: list[Path] = [
    ROOT / ".claude-plugin" / "plugin.json",
    ROOT / ".agents" / "plugins" / "marketplace.json",
    ROOT / "gemini-extension.json",
]

# Files using YAML/frontmatter where the pattern `version: "X.Y.Z"` must be updated.
YAML_TARGETS: list[Path] = [
    ROOT / "sentinel.skill",
]


def is_valid_semver(version: str) -> bool:
    return bool(SEMVER_RE.fullmatch(version))


def read_version(vf: Path | None = None) -> str:
    vf = vf or (ROOT / "VERSION")
    if not vf.exists():
        sys.exit(f"ERROR: VERSION file not found at {vf}")
    v = vf.read_text(encoding="utf-8").strip()
    if not is_valid_semver(v):
        sys.exit(f"ERROR: VERSION contains invalid semver: {v!r}")
    return v


def _sync_json(path: Path, version: str, *, dry_run: bool = False, check_only: bool = False) -> bool:
    if not path.exists():
        print(f"  SKIP (missing): {path.relative_to(ROOT)}")
        return False
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    if data.get("version") == version:
        print(f"  OK   (current): {path.relative_to(ROOT)}")
        return False
    old = data.get("version", "<none>")
    data["version"] = version
    new_raw = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    if dry_run or check_only:
        prefix = "DRY " if dry_run else "NEED"
        print(f"  {prefix} {path.relative_to(ROOT)}: {old!r} -> {version!r}")
        return True
    path.write_text(new_raw, encoding="utf-8")
    print(f"  BUMP {path.relative_to(ROOT)}: {old!r} -> {version!r}")
    return True


def _sync_yaml(path: Path, version: str, *, dry_run: bool = False, check_only: bool = False) -> bool:
    if not path.exists():
        print(f"  SKIP (missing): {path.relative_to(ROOT)}")
        return False
    raw = path.read_text(encoding="utf-8")
    pattern = re.compile(r'^version:\s*["\']?([^"\'\n]+)["\']?', re.MULTILINE)
    m = pattern.search(raw)
    if not m:
        print(f"  SKIP (no version field): {path.relative_to(ROOT)}")
        return False
    old = m.group(1).strip()
    if old == version:
        print(f"  OK   (current): {path.relative_to(ROOT)}")
        return False
    new_raw = pattern.sub(f'version: "{version}"', raw, count=1)
    if dry_run or check_only:
        prefix = "DRY " if dry_run else "NEED"
        print(f"  {prefix} {path.relative_to(ROOT)}: {old!r} -> {version!r}")
        return True
    path.write_text(new_raw, encoding="utf-8")
    print(f"  BUMP {path.relative_to(ROOT)}: {old!r} -> {version!r}")
    return True


def sync_static_manifests(
    version: str | None = None, *, dry_run: bool = False, check_only: bool = False
) -> int:
    if dry_run and check_only:
        raise ValueError("use only one of dry_run or check_only")

    version = version or read_version()
    if not is_valid_semver(version):
        raise ValueError(f"invalid semver: {version!r}")

    print(f"Syncing version {version!r} to static manifests...\n")

    changed = 0
    for p in JSON_TARGETS:
        if _sync_json(p, version, dry_run=dry_run, check_only=check_only):
            changed += 1
    for p in YAML_TARGETS:
        if _sync_yaml(p, version, dry_run=dry_run, check_only=check_only):
            changed += 1
    return changed


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    check_only = "--check" in sys.argv

    if dry_run and check_only:
        sys.exit("ERROR: use only one of --dry-run or --check")

    changed = sync_static_manifests(dry_run=dry_run, check_only=check_only)

    print()
    if check_only:
        if changed:
            sys.exit(
                "ERROR: Static manifests are out of sync with VERSION. "
                "Run: python scripts/release/sync_version.py and commit the updates."
            )
        print("Check complete. All static manifests are in sync.")
    elif dry_run:
        print(f"Dry-run complete. {changed} file(s) would be updated.")
    else:
        print(f"Done. {changed} file(s) updated.")


if __name__ == "__main__":
    main()
