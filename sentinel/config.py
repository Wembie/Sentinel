from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="SENTINEL_",
        env_ignore_empty=True,
        extra="ignore",
    )

    debug: bool = False
    log_level: str = "INFO"

    # LLM
    llm_provider: Literal["claude", "openai", "none"] = "claude"
    llm_model: str = "claude-sonnet-4-6"
    llm_api_key: str = ""
    llm_max_tokens: int = 8192

    # Graph
    graph_backend: Literal["networkx", "neo4j"] = "networkx"
    graph_neo4j_uri: str = "bolt://localhost:7687"
    graph_neo4j_user: str = "neo4j"
    graph_neo4j_password: str = ""

    # API server
    server_host: str = "0.0.0.0"
    server_port: int = 8000
    server_reload: bool = False

    # Audit limits
    max_file_size_kb: int = 512
    max_files_per_audit: int = 1000

    plugin_dirs: list[Path] = Field(default_factory=list)
    rules_dirs: list[Path] = Field(default_factory=list)


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
