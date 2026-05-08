from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from sentinel.core.context import AuditContext
from sentinel.models.finding import Finding


@dataclass
class RuleMetadata:
    id: str
    title: str
    description: str
    severity: str
    confidence: str
    cwe_ids: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)  # empty = language-agnostic


@runtime_checkable
class Rule(Protocol):
    metadata: RuleMetadata

    async def match(self, ctx: AuditContext) -> list[Finding]: ...


class BaseRule:
    """Optional base. Subclass for convenience; not required by the Protocol."""

    metadata: RuleMetadata

    async def match(self, ctx: AuditContext) -> list[Finding]:
        raise NotImplementedError
