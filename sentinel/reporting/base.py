from __future__ import annotations

from typing import Protocol, runtime_checkable

from sentinel.models.audit import AuditResult


@runtime_checkable
class ReportFormatter(Protocol):
    format: str

    def render(self, result: AuditResult) -> str: ...
