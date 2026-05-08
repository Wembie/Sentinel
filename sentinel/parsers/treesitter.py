from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import structlog

from sentinel.parsers.base import detect_language

log = structlog.get_logger()

try:
    import tree_sitter_python as _tspython
    from tree_sitter import Language, Parser as _TSParser

    _PYTHON_LANGUAGE = Language(_tspython.language())
    _HAS_TREE_SITTER = True
except Exception:  # ImportError or OSError on missing shared lib
    _HAS_TREE_SITTER = False
    _PYTHON_LANGUAGE = None  # type: ignore[assignment]


class TreeSitterParser:
    """Extracts tree-sitter ASTs for supported languages.

    Fails gracefully when tree-sitter bindings are absent — the pipeline
    continues without ASTs and rules that rely on text patterns still run.
    """

    SUPPORTED: frozenset[str] = frozenset({"python"} if _HAS_TREE_SITTER else set())

    def can_parse(self, path: Path) -> bool:
        return detect_language(path) in self.SUPPORTED

    async def parse(self, path: Path, content: str) -> dict[str, Any]:
        return await asyncio.to_thread(self._parse_sync, content)

    def _parse_sync(self, content: str) -> dict[str, Any]:
        if not _HAS_TREE_SITTER:
            return {"error": "tree-sitter not available", "nodes": []}

        parser = _TSParser(_PYTHON_LANGUAGE)
        tree = parser.parse(content.encode())

        return {
            "root": self._node_to_dict(tree.root_node),
            "has_errors": tree.root_node.has_error,
        }

    def _node_to_dict(self, node: Any, depth: int = 0) -> dict[str, Any]:
        if depth > 20:
            return {"type": node.type, "truncated": True}

        result: dict[str, Any] = {
            "type": node.type,
            "start": (node.start_point[0], node.start_point[1]),
            "end": (node.end_point[0], node.end_point[1]),
        }

        if node.child_count == 0:
            result["text"] = node.text.decode(errors="replace")
        else:
            result["children"] = [self._node_to_dict(c, depth + 1) for c in node.children]

        return result
