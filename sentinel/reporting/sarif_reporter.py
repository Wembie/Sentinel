from __future__ import annotations

import json
from typing import Any

from sentinel.models.audit import AuditResult
from sentinel.models.finding import Finding

_SEVERITY_LEVEL = {
    "critical": "error",
    "high": "error",
    "medium": "warning",
    "low": "note",
    "info": "none",
}


class SARIFReporter:
    """SARIF 2.1.0 output — compatible with GitHub Code Scanning and VS Code SARIF Viewer."""

    format = "sarif"

    def render(self, result: AuditResult) -> str:
        rules = self._build_rules(result.findings)
        results = [self._finding_to_result(f) for f in result.findings]

        sarif: dict[str, Any] = {
            "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": "SENTINEL",
                            "version": "0.1.0",
                            "informationUri": "https://github.com/your-org/sentinel",
                            "rules": rules,
                        }
                    },
                    "results": results,
                }
            ],
        }
        return json.dumps(sarif, indent=2)

    def _build_rules(self, findings: list[Finding]) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rules = []
        for f in findings:
            rule_id = f.rule_id or str(f.id)
            if rule_id in seen:
                continue
            seen.add(rule_id)
            rules.append(
                {
                    "id": rule_id,
                    "name": f.title,
                    "shortDescription": {"text": f.title},
                    "fullDescription": {"text": f.technical_explanation},
                    "defaultConfiguration": {
                        "level": _SEVERITY_LEVEL.get(f.severity.value, "warning")
                    },
                    "properties": {"tags": f.tags, "cwe": f.cwe_ids},
                }
            )
        return rules

    def _finding_to_result(self, f: Finding) -> dict[str, Any]:
        locations = []
        for loc in f.locations:
            if loc.file and loc.line_start:
                locations.append(
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": loc.file.replace("\\", "/")},
                            "region": {"startLine": loc.line_start},
                        }
                    }
                )

        return {
            "ruleId": f.rule_id or str(f.id),
            "level": _SEVERITY_LEVEL.get(f.severity.value, "warning"),
            "message": {"text": f.technical_explanation},
            "locations": locations or [{"physicalLocation": {"artifactLocation": {"uri": "unknown"}}}],
        }
