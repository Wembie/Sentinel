from __future__ import annotations

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

import structlog

log = structlog.get_logger()


@dataclass
class Span:
    name: str
    start_time: float = field(default_factory=time.monotonic)
    end_time: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_ms(self) -> float | None:
        if self.end_time is None:
            return None
        return (self.end_time - self.start_time) * 1000

    def finish(self) -> None:
        self.end_time = time.monotonic()


class AuditTracer:
    def __init__(self, audit_id: str) -> None:
        self.audit_id = audit_id
        self._spans: list[Span] = []

    @asynccontextmanager
    async def span(self, name: str, **metadata: Any) -> AsyncIterator[Span]:
        s = Span(name=name, metadata=metadata)
        self._spans.append(s)
        try:
            yield s
        finally:
            s.finish()
            log.debug("span_done", span=name, duration_ms=s.duration_ms, **metadata)

    def summary(self) -> list[dict[str, Any]]:
        return [{"name": s.name, "duration_ms": s.duration_ms, **s.metadata} for s in self._spans]
