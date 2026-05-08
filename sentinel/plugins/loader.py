from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import structlog

log = structlog.get_logger()


class PluginLoader:
    """Discovers and loads external plugin packages from a directory.

    A plugin is any directory containing an ``__init__.py``. Optional
    ``plugin.toml`` manifest is reserved for future metadata (name, version,
    author, sentinel_min_version).
    """

    def __init__(self) -> None:
        self._loaded: list[str] = []

    def load_directory(self, directory: Path) -> None:
        if not directory.exists():
            return
        for plugin_dir in sorted(directory.iterdir()):
            if not plugin_dir.is_dir():
                continue
            entry = plugin_dir / "__init__.py"
            if entry.exists():
                self._load_plugin(plugin_dir.name, entry)

    def _load_plugin(self, name: str, entry: Path) -> None:
        module_name = f"_sentinel_plugin_{name}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, entry)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
                self._loaded.append(name)
                log.info("plugin_loaded", name=name)
        except Exception as exc:
            log.error("plugin_load_failed", name=name, error=str(exc))

    @property
    def loaded_plugins(self) -> list[str]:
        return list(self._loaded)
