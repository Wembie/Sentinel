from __future__ import annotations

from sentinel.models.audit import AuditResult


class JSONReporter:
    format = "json"

    def render(self, result: AuditResult) -> str:
        return result.model_dump_json(indent=2)
