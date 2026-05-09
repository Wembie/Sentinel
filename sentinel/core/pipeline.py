from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

import structlog

from sentinel.core.context import AuditContext
from sentinel.tracing.tracer import AuditTracer

log = structlog.get_logger()

PipelineStage = Callable[[AuditContext], Awaitable[None]]


class AuditPipeline:
    """Composable async pipeline.

    Stages are plain async callables: ``async def stage(ctx: AuditContext) -> None``.
    Each stage reads/writes the shared context. Order matters; stages run sequentially.
    """

    def __init__(self) -> None:
        self._stages: list[tuple[str, PipelineStage]] = []

    def add_stage(self, name: str, fn: PipelineStage) -> AuditPipeline:
        self._stages.append((name, fn))
        return self

    async def run(self, ctx: AuditContext, tracer: AuditTracer | None = None) -> None:
        for name, stage in self._stages:
            if tracer:
                async with tracer.span(name):
                    await self._run_stage(name, stage, ctx)
            else:
                await self._run_stage(name, stage, ctx)

    async def _run_stage(self, name: str, stage: PipelineStage, ctx: AuditContext) -> None:
        try:
            log.info("stage_start", stage=name)
            t0 = time.monotonic()
            await stage(ctx)
            log.info("stage_done", stage=name, elapsed_ms=round((time.monotonic() - t0) * 1000))
        except Exception as exc:
            log.error("stage_failed", stage=name, error=str(exc))
            ctx.add_error(f"Stage '{name}' failed: {exc}")
