from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from sentinel.models.finding import Finding, Severity


class AuditMode(str, Enum):
    FULL = "full"
    QUICK = "quick"
    TARGETED = "targeted"


class AuditScope(BaseModel):
    paths: list[Path] = Field(default_factory=list)
    exclude_patterns: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    max_depth: int | None = None
    include_tests: bool = False


class AuditRequest(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    target: Path
    scope: AuditScope = Field(default_factory=AuditScope)
    mode: AuditMode = AuditMode.FULL
    analyzers: list[str] = Field(default_factory=list)
    commands: list[str] = Field(default_factory=list)
    llm_enabled: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class AuditStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AuditSummary(BaseModel):
    total_findings: int = 0
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_analyzer: dict[str, int] = Field(default_factory=dict)
    files_analyzed: int = 0
    lines_analyzed: int = 0
    duration_seconds: float = 0.0

    @classmethod
    def from_findings(
        cls,
        findings: list[Finding],
        duration: float,
        files: int,
        lines: int,
    ) -> "AuditSummary":
        by_sev: dict[str, int] = {}
        by_analyzer: dict[str, int] = {}
        for f in findings:
            by_sev[f.severity.value] = by_sev.get(f.severity.value, 0) + 1
            by_analyzer[f.analyzer] = by_analyzer.get(f.analyzer, 0) + 1
        return cls(
            total_findings=len(findings),
            by_severity=by_sev,
            by_analyzer=by_analyzer,
            files_analyzed=files,
            lines_analyzed=lines,
            duration_seconds=duration,
        )


class AuditResult(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    request_id: UUID
    status: AuditStatus = AuditStatus.PENDING
    findings: list[Finding] = Field(default_factory=list)
    summary: AuditSummary = Field(default_factory=AuditSummary)
    errors: list[str] = Field(default_factory=list)
    started_at: datetime | None = None
    completed_at: datetime | None = None
