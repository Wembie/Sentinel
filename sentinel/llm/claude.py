from __future__ import annotations

import json
from typing import Any

import anthropic

from sentinel.llm.base import LLMResponse, Message


class ClaudeProvider:
    """Anthropic Claude backend with prompt caching enabled on system prompts."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6") -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model

    @property
    def model(self) -> str:
        return self._model

    async def complete(
        self,
        messages: list[Message],
        system: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.1,
    ) -> LLMResponse:
        sdk_messages = [{"role": m.role, "content": m.content} for m in messages]

        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": sdk_messages,
        }

        if system:
            # Cache the system prompt — saves tokens on repeated calls with the same instructions
            kwargs["system"] = [
                {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}
            ]

        response = await self._client.messages.create(**kwargs)
        usage = response.usage

        return LLMResponse(
            content=response.content[0].text,
            model=response.model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cached_tokens=getattr(usage, "cache_read_input_tokens", 0),
        )

    async def complete_structured(
        self,
        messages: list[Message],
        response_model: type[Any],
        system: str | None = None,
        max_tokens: int = 4096,
    ) -> Any:
        schema = (
            response_model.model_json_schema()
            if hasattr(response_model, "model_json_schema")
            else {}
        )
        structured_system = f"{system or ''}\n\nRespond ONLY with valid JSON matching:\n{json.dumps(schema, indent=2)}"
        response = await self.complete(
            messages=messages,
            system=structured_system,
            max_tokens=max_tokens,
            temperature=0.0,
        )
        data = json.loads(response.content)
        return response_model(**data)
