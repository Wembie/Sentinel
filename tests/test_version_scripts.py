from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts" / "release"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import bump_version
import sync_version


def _make_version_files(root: Path, version: str) -> tuple[list[Path], list[Path]]:
    version_file = root / "VERSION"
    version_file.write_text(f"{version}\n", encoding="utf-8")

    json_targets = [
        root / ".claude-plugin" / "plugin.json",
        root / ".agents" / "plugins" / "marketplace.json",
        root / "gemini-extension.json",
    ]
    yaml_targets = [root / "sentinel.skill"]

    json_payloads = [
        '{\n  "name": "sentinel",\n  "version": "0.1.0"\n}\n',
        '{\n  "id": "sentinel",\n  "version": "0.1.0"\n}\n',
        '{\n  "name": "sentinel",\n  "version": "0.1.0"\n}\n',
    ]
    yaml_payload = '---\nname: sentinel\nversion: "0.1.0"\n---\n'

    for path, payload in zip(json_targets, json_payloads, strict=True):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload, encoding="utf-8")
    yaml_targets[0].write_text(yaml_payload, encoding="utf-8")

    return json_targets, yaml_targets


def _point_scripts_at_tmp_root(monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    json_targets, yaml_targets = _make_version_files(root, "1.0.0")
    monkeypatch.setattr(sync_version, "ROOT", root)
    monkeypatch.setattr(sync_version, "JSON_TARGETS", json_targets)
    monkeypatch.setattr(sync_version, "YAML_TARGETS", yaml_targets)
    monkeypatch.setattr(bump_version, "ROOT", root)
    monkeypatch.setattr(bump_version, "VERSION_FILE", root / "VERSION")


def test_resolve_target_version_supports_semver_and_bump_kinds() -> None:
    assert bump_version.resolve_target_version("1.2.3", "1.2.4") == "1.2.4"
    assert bump_version.resolve_target_version("1.2.3", "patch") == "1.2.4"
    assert bump_version.resolve_target_version("1.2.3", "minor") == "1.3.0"
    assert bump_version.resolve_target_version("1.2.3", "major") == "2.0.0"


def test_bump_version_updates_version_and_manifests(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _point_scripts_at_tmp_root(monkeypatch, tmp_path)

    target_version, version_changed, manifest_changes = bump_version.bump_version("1.0.1")

    assert target_version == "1.0.1"
    assert version_changed is True
    assert manifest_changes == 4
    assert (tmp_path / "VERSION").read_text(encoding="utf-8").strip() == "1.0.1"
    assert '"version": "1.0.1"' in (tmp_path / ".claude-plugin" / "plugin.json").read_text(
        encoding="utf-8"
    )
    assert 'version: "1.0.1"' in (tmp_path / "sentinel.skill").read_text(encoding="utf-8")


def test_bump_version_dry_run_does_not_write_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _point_scripts_at_tmp_root(monkeypatch, tmp_path)

    target_version, version_changed, manifest_changes = bump_version.bump_version(
        "patch", dry_run=True
    )

    assert target_version == "1.0.1"
    assert version_changed is True
    assert manifest_changes == 4
    assert (tmp_path / "VERSION").read_text(encoding="utf-8").strip() == "1.0.0"
    assert '"version": "0.1.0"' in (tmp_path / "gemini-extension.json").read_text(
        encoding="utf-8"
    )
