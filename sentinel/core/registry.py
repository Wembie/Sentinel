from __future__ import annotations

import importlib
import inspect
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class Registry(Generic[T]):
    """Generic plugin/component registry. Supports decorator registration and module scanning."""

    def __init__(self, name: str) -> None:
        self.name = name
        self._entries: dict[str, type[Any]] = {}

    def register(self, name: str | None = None):
        def decorator(cls: type[Any]) -> type[Any]:
            key = name or cls.__name__.lower()
            self._entries[key] = cls
            return cls

        return decorator

    def get(self, name: str) -> type[Any] | None:
        return self._entries.get(name)

    def get_all(self) -> dict[str, type[Any]]:
        return dict(self._entries)

    def names(self) -> list[str]:
        return list(self._entries.keys())

    def instantiate(self, name: str, *args: Any, **kwargs: Any) -> T | None:
        cls = self.get(name)
        if cls is None:
            return None
        return cls(*args, **kwargs)  # type: ignore[return-value]

    def instantiate_all(self, *args: Any, **kwargs: Any) -> list[T]:
        return [cls(*args, **kwargs) for cls in self._entries.values()]  # type: ignore[return-value]

    def load_from_module(self, module_path: str, base_class: type[Any]) -> None:
        module = importlib.import_module(module_path)
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, base_class) and obj is not base_class:
                self.register()(obj)
