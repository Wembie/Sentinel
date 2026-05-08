from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class Confidence(str, Enum):
    CONFIRMED = "confirmed"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    SPECULATIVE = "speculative"


class Location(BaseModel):
    file: str
    line_start: int | None = None
    line_end: int | None = None
    column_start: int | None = None
    column_end: int | None = None
    function: str | None = None
    class_name: str | None = None


class ExploitChainStep(BaseModel):
    step: int
    component: str
    action: str
    notes: str | None = None


class Finding(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    title: str
    severity: Severity
    confidence: Confidence

    affected_components: list[str] = Field(default_factory=list)
    locations: list[Location] = Field(default_factory=list)

    attack_surface: str
    exploitation_requirements: str
    technical_explanation: str
    root_cause: str
    attack_scenario: str

    exploit_chain: list[ExploitChainStep] = Field(default_factory=list)

    potential_impact: str
    blast_radius: str
    detection_difficulty: str
    business_risk: str

    mitigation_strategy: str
    secure_refactor_recommendations: list[str] = Field(default_factory=list)
    safer_architectural_alternative: str | None = None
    verification_notes: str | None = None

    tags: list[str] = Field(default_factory=list)
    cwe_ids: list[str] = Field(default_factory=list)
    cvss_score: float | None = None

    analyzer: str
    rule_id: str | None = None

    discovered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def risk_score(self) -> float:
        sev_weights = {
            Severity.CRITICAL: 10.0,
            Severity.HIGH: 7.5,
            Severity.MEDIUM: 5.0,
            Severity.LOW: 2.5,
            Severity.INFO: 0.5,
        }
        conf_weights = {
            Confidence.CONFIRMED: 1.0,
            Confidence.HIGH: 0.9,
            Confidence.MEDIUM: 0.7,
            Confidence.LOW: 0.5,
            Confidence.SPECULATIVE: 0.3,
        }
        return sev_weights[self.severity] * conf_weights[self.confidence]
