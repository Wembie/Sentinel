from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, runtime_checkable

LANGUAGE_EXTENSIONS: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".jsx": "javascript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".rb": "ruby",
    ".php": "php",
    ".cs": "csharp",
    ".cpp": "cpp",
    ".c": "c",
    ".kt": "kotlin",
    ".swift": "swift",
}


def detect_language(path: Path) -> str | None:
    return LANGUAGE_EXTENSIONS.get(path.suffix.lower())


@runtime_checkable
class Parser(Protocol):
    def can_parse(self, path: Path) -> bool: ...
    async def parse(self, path: Path, content: str) -> dict[str, Any]: ...
