from __future__ import annotations

import json
from typing import Any

from openai import AsyncOpenAI

from sentinel.llm.base import LLMResponse, Message


class OpenAIProvider:
    """OpenAI backend."""

    def __init__(self, api_key: str, model: str = "gpt-4o") -> None:
        self._client = AsyncOpenAI(api_key=api_key)
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
        sdk_messages: list[dict[str, str]] = []
        if system:
            sdk_messages.append({"role": "system", "content": system})
        sdk_messages.extend({"role": m.role, "content": m.content} for m in messages)

        response = await self._client.chat.completions.create(
            model=self._model,
            messages=sdk_messages,  # type: ignore[arg-type]
            max_tokens=max_tokens,
            temperature=temperature,
        )

        usage = response.usage
        return LLMResponse(
            content=response.choices[0].message.content or "",
            model=response.model,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
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
