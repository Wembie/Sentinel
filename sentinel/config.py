from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict


def _find_config_file() -> Path | None:
    """Discover config file via XDG chain: $SENTINEL_CONFIG → ~/.config/sentinel/config.json → ~/.sentinel/config.json."""
    if cfg := os.environ.get("SENTINEL_CONFIG"):
        p = Path(cfg)
        return p if p.exists() else None
    candidates = [
        Path.home() / ".config" / "sentinel" / "config.json",
        Path.home() / ".sentinel" / "config.json",
    ]
    return next((p for p in candidates if p.exists()), None)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SENTINEL_",
        env_ignore_empty=True,
        extra="ignore",
    )

    debug: bool = False
    log_level: str = "INFO"

    # LLM — defaults to "none" so SENTINEL works without any API key.
    # Set SENTINEL_LLM_PROVIDER=claude and SENTINEL_LLM_API_KEY=sk-... to enable enrichment.
    llm_provider: Literal["claude", "openai", "none"] = "none"
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

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Priority: init kwargs > env vars > XDG config file > defaults."""
        from pydantic_settings import JsonConfigSettingsSource

        config_file = _find_config_file()
        if config_file:
            return (init_settings, env_settings, JsonConfigSettingsSource(settings_cls, config_file))
        return (init_settings, env_settings)


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
