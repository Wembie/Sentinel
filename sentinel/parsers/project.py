from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import structlog

from sentinel.config import Settings
from sentinel.core.context import AuditContext
from sentinel.parsers.base import detect_language

log = structlog.get_logger()

_DEFAULT_EXCLUDES = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        "env",
        ".env",
        "dist",
        "build",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".tox",
        "coverage",
        ".coverage",
    }
)


class ProjectParser:
    """Stage 1: ingests all source files into ``ctx.file_contents``."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def ingest(self, ctx: AuditContext) -> None:
        target = ctx.request.target
        scope = ctx.request.scope

        paths = await asyncio.to_thread(self._collect_files, target, scope)

        results = await asyncio.gather(
            *[self._read_file(p, target, ctx) for p in paths[: self._settings.max_files_per_audit]],
        )

        for result in results:
            if result:
                rel_path, content, metadata = result
                ctx.file_contents[rel_path] = content
                ctx.file_metadata[rel_path] = metadata

        log.info("ingest_done", files=ctx.files_analyzed, target=str(target))

    async def _read_file(
        self,
        path: Path,
        base: Path,
        ctx: AuditContext,
    ) -> tuple[str, str, dict[str, Any]] | None:
        try:
            content = await asyncio.to_thread(path.read_text, errors="replace")
            size_kb = len(content.encode()) / 1024
            if size_kb > self._settings.max_file_size_kb:
                log.warning("file_skipped_too_large", path=str(path), size_kb=round(size_kb))
                return None
            rel = str(path.relative_to(base))
            metadata: dict[str, Any] = {
                "path": str(path),
                "size_bytes": len(content.encode()),
                "language": detect_language(path),
                "lines": content.count("\n") + 1,
            }
            return rel, content, metadata
        except Exception as exc:
            ctx.add_error(f"Failed to read {path}: {exc}")
            return None

    def _collect_files(self, target: Path, scope: Any) -> list[Path]:
        exclude = _DEFAULT_EXCLUDES | set(scope.exclude_patterns or [])
        paths: list[Path] = []
        for path in target.rglob("*"):
            if not path.is_file():
                continue
            if any(part in exclude for part in path.parts):
                continue
            if scope.languages and detect_language(path) not in scope.languages:
                continue
            paths.append(path)
        return sorted(paths)
