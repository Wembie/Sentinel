#!/usr/bin/env python3
"""Sync the VERSION file to all static manifests.

Run before tagging a release:
    python scripts/sync_version.py

Dry-run (print diffs, write nothing):
    python scripts/sync_version.py --dry-run
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
DRY_RUN = "--dry-run" in sys.argv

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


def _read_version() -> str:
    vf = ROOT / "VERSION"
    if not vf.exists():
        sys.exit(f"ERROR: VERSION file not found at {vf}")
    v = vf.read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:[-+].+)?", v):
        sys.exit(f"ERROR: VERSION contains invalid semver: {v!r}")
    return v


def _sync_json(path: Path, version: str) -> bool:
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
    if DRY_RUN:
        print(f"  DRY  {path.relative_to(ROOT)}: {old!r} -> {version!r}")
        return True
    path.write_text(new_raw, encoding="utf-8")
    print(f"  BUMP {path.relative_to(ROOT)}: {old!r} -> {version!r}")
    return True


def _sync_yaml(path: Path, version: str) -> bool:
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
    if DRY_RUN:
        print(f"  DRY  {path.relative_to(ROOT)}: {old!r} -> {version!r}")
        return True
    path.write_text(new_raw, encoding="utf-8")
    print(f"  BUMP {path.relative_to(ROOT)}: {old!r} -> {version!r}")
    return True


def main() -> None:
    version = _read_version()
    print(f"Syncing version {version!r} to static manifests...\n")

    changed = 0
    for p in JSON_TARGETS:
        if _sync_json(p, version):
            changed += 1
    for p in YAML_TARGETS:
        if _sync_yaml(p, version):
            changed += 1

    print()
    if DRY_RUN:
        print(f"Dry-run complete. {changed} file(s) would be updated.")
    else:
        print(f"Done. {changed} file(s) updated.")


if __name__ == "__main__":
    main()
