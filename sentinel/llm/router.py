from __future__ import annotations

from sentinel.config import Settings
from sentinel.llm.base import LLMProvider


def build_provider(settings: Settings) -> LLMProvider | None:
    """Construct the configured LLM provider. Returns None when provider is 'none'."""
    if settings.llm_provider == "none":
        return None

    if settings.llm_provider == "claude":
        from sentinel.llm.claude import ClaudeProvider

        return ClaudeProvider(api_key=settings.llm_api_key, model=settings.llm_model)

    if settings.llm_provider == "openai":
        from sentinel.llm.openai import OpenAIProvider

        return OpenAIProvider(api_key=settings.llm_api_key, model=settings.llm_model)

    raise ValueError(f"Unknown LLM provider: {settings.llm_provider!r}")
