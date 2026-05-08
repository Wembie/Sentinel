from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sentinel import __version__
from sentinel.config import get_settings
from sentinel.logging import configure_logging

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)

    from sentinel.core.engine import AuditEngine

    engine = AuditEngine(settings)
    await engine.initialize()
    app.state.engine = engine

    log.info("sentinel_ready", host=settings.server_host, port=settings.server_port)
    yield
    log.info("sentinel_shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title="SENTINEL",
        description="AI-powered contextual security auditing platform",
        version=__version__,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from sentinel.api.routes import audit, health

    app.include_router(health.router, prefix="/health", tags=["health"])
    app.include_router(audit.router, prefix="/audit", tags=["audit"])

    return app


app = create_app()
