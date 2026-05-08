from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel


class Message(BaseModel):
    role: str  # "user" | "assistant" | "system"
    content: str


class LLMResponse(BaseModel):
    content: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@runtime_checkable
class LLMProvider(Protocol):
    """Provider-agnostic LLM interface.

    Implement this protocol to add a new backend (Claude, OpenAI, local model, etc.).
    No base class required — structural subtyping.
    """

    @property
    def model(self) -> str: ...

    async def complete(
        self,
        messages: list[Message],
        system: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.1,
    ) -> LLMResponse: ...

    async def complete_structured(
        self,
        messages: list[Message],
        response_model: type[Any],
        system: str | None = None,
        max_tokens: int = 4096,
    ) -> Any: ...
