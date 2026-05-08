from __future__ import annotations

import importlib
import importlib.util
import inspect
import sys
from pathlib import Path

import structlog

from sentinel.rules.base import BaseRule, Rule

log = structlog.get_logger()


class RuleLoader:
    def __init__(self) -> None:
        self._rules: list[Rule] = []

    def load_builtin(self) -> None:
        builtin_dir = Path(__file__).parent / "builtin"
        for module_file in sorted(builtin_dir.glob("*.py")):
            if module_file.name.startswith("_"):
                continue
            module_name = f"sentinel.rules.builtin.{module_file.stem}"
            try:
                module = importlib.import_module(module_name)
                self._load_from_module(module)
            except Exception as exc:
                log.error("builtin_rule_load_failed", module=module_name, error=str(exc))

    def load_from_directory(self, path: Path) -> None:
        if not path.exists():
            return
        for py_file in sorted(path.glob("*.py")):
            if py_file.name.startswith("_"):
                continue
            module_name = f"_sentinel_rules_{py_file.stem}"
            try:
                spec = importlib.util.spec_from_file_location(module_name, py_file)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[module_name] = module
                    spec.loader.exec_module(module)
                    self._load_from_module(module)
            except Exception as exc:
                log.error("rule_file_load_failed", file=str(py_file), error=str(exc))

    def _load_from_module(self, module: object) -> None:
        for _, cls in inspect.getmembers(module, inspect.isclass):
            if not (issubclass(cls, BaseRule) and cls is not BaseRule):
                continue
            try:
                instance = cls()
                self._rules.append(instance)
                log.debug("rule_registered", id=instance.metadata.id)
            except Exception as exc:
                log.error("rule_instantiate_failed", cls=cls.__name__, error=str(exc))

    @property
    def rules(self) -> list[Rule]:
        return list(self._rules)
