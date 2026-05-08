from __future__ import annotations

from typing import Protocol, runtime_checkable

from sentinel.core.context import AuditContext


@runtime_checkable
class Analyzer(Protocol):
    """Protocol every analyzer must satisfy.

    Use structural subtyping — analyzers don't need to inherit from anything.
    Implement ``name``, ``description``, ``analyze``, and ``supports``.
    """

    name: str
    description: str

    async def analyze(self, ctx: AuditContext) -> None:
        """Run analysis and write findings directly to ctx."""
        ...

    def supports(self, language: str) -> bool:
        """Return True if this analyzer handles the given language."""
        ...


class BaseAnalyzer:
    """Optional convenience base. Inherit only if it saves you boilerplate."""

    name: str = "base"
    description: str = ""
    supported_languages: list[str] = []

    def supports(self, language: str) -> bool:
        return not self.supported_languages or language in self.supported_languages

    async def analyze(self, ctx: AuditContext) -> None:
        raise NotImplementedError
