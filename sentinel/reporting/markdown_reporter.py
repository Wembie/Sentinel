from __future__ import annotations

from sentinel.models.audit import AuditResult
from sentinel.models.finding import Finding, Severity

_SEV_BADGE = {
    Severity.CRITICAL: "🔴 CRITICAL",
    Severity.HIGH: "🟠 HIGH",
    Severity.MEDIUM: "🟡 MEDIUM",
    Severity.LOW: "🔵 LOW",
    Severity.INFO: "⚪ INFO",
}


class MarkdownReporter:
    format = "markdown"

    def render(self, result: AuditResult) -> str:
        lines: list[str] = [
            "# SENTINEL Security Audit Report",
            "",
            f"**Audit ID:** `{result.id}`  ",
            f"**Status:** `{result.status.value}`  ",
            f"**Duration:** {result.summary.duration_seconds:.1f}s  ",
            f"**Files analyzed:** {result.summary.files_analyzed}  ",
            f"**Lines analyzed:** {result.summary.lines_analyzed:,}  ",
            "",
            "## Summary",
            "",
        ]

        sev_order = list(Severity)
        for sev in sev_order:
            count = result.summary.by_severity.get(sev.value, 0)
            if count:
                lines.append(f"- {_SEV_BADGE[sev]}: **{count}**")

        lines += ["", f"**Total findings:** {result.summary.total_findings}", ""]

        if result.errors:
            lines += ["## Errors", ""]
            for err in result.errors:
                lines.append(f"- `{err}`")
            lines.append("")

        if not result.findings:
            lines.append("_No findings._")
            return "\n".join(lines)

        lines.append("## Findings")
        sorted_findings = sorted(result.findings, key=lambda f: f.risk_score, reverse=True)
        for i, finding in enumerate(sorted_findings, 1):
            lines.extend(self._render_finding(i, finding))

        return "\n".join(lines)

    def _render_finding(self, index: int, f: Finding) -> list[str]:
        locs = (
            ", ".join(f"`{loc.file}:{loc.line_start}`" for loc in f.locations if loc.line_start)
            or "N/A"
        )
        badge = _SEV_BADGE.get(f.severity, f.severity.value)

        lines: list[str] = [
            "",
            "---",
            "",
            f"### {index}. {badge} — {f.title}",
            "",
            f"| | |",
            f"|---|---|",
            f"| **Confidence** | {f.confidence.value} |",
            f"| **Rule** | `{f.rule_id or 'N/A'}` |",
            f"| **CWE** | {', '.join(f.cwe_ids) or 'N/A'} |",
            f"| **Location** | {locs} |",
            f"| **Risk Score** | {f.risk_score:.1f} |",
            "",
            f"**Attack Surface:** {f.attack_surface}",
            "",
            f"**Technical Explanation:** {f.technical_explanation}",
            "",
            f"**Root Cause:** {f.root_cause}",
            "",
            f"**Attack Scenario:** {f.attack_scenario}",
            "",
        ]

        if f.exploit_chain:
            lines += ["**Exploit Chain:**", ""]
            for step in f.exploit_chain:
                lines.append(f"{step.step}. **{step.component}** — {step.action}")
            lines.append("")

        lines += [
            f"**Impact:** {f.potential_impact}",
            "",
            f"**Blast Radius:** {f.blast_radius}",
            "",
            f"**Detection Difficulty:** {f.detection_difficulty}",
            "",
            f"**Business Risk:** {f.business_risk}",
            "",
            f"**Mitigation:** {f.mitigation_strategy}",
            "",
        ]

        if f.secure_refactor_recommendations:
            lines += ["**Recommendations:**", ""]
            for rec in f.secure_refactor_recommendations:
                lines.append(f"- {rec}")
            lines.append("")

        if f.safer_architectural_alternative:
            lines += [f"**Architectural Alternative:** {f.safer_architectural_alternative}", ""]

        if f.verification_notes:
            lines += [f"**Verification:** {f.verification_notes}", ""]

        return lines
