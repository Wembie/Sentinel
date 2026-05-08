"""ASGI entry point for uvicorn: ``uvicorn sentinel.main:app``"""

from sentinel.api.main import app

__all__ = ["app"]
