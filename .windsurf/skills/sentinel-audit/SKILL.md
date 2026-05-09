---
name: sentinel-audit
description: Full deep security audit of a codebase — AST parse, call graph, all detection rules, optional LLM enrichment
trigger: /sentinel-audit
mcp_tool: sentinel_audit
---

# sentinel-audit

Full contextual security audit: ingest all source files, parse ASTs, build a call graph, run every detection rule (injection, auth, secrets, logic), optionally enrich top findings with LLM analysis.

## When to Use

- User requests a security review or vulnerability scan of a project
- Starting a new audit engagement on a codebase
- Pre-release security check
- Onboarding a codebase into continuous security monitoring

## MCP Tool

```
sentinel_audit(target: str, languages?: str) -> AuditResult
```

### Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `target` | yes | Absolute or relative path to the directory to audit |
| `languages` | no | Comma-separated language filter, e.g. `"python,go"` |

### Returns

```json
{
  "audit_id": "uuid",
  "target": "/path/to/project",
  "findings": [...],
  "summary": {
    "total_findings": 12,
    "by_severity": {"critical": 1, "high": 3, "medium": 5, "low": 3}
  },
  "stats": {"files_scanned": 42, "nodes": 1800, "edges": 3200}
}
```

## Example

```
sentinel_audit(target="./")
sentinel_audit(target="/home/user/myapp", languages="python,javascript")
```

## Next Steps After Audit

- `sentinel_trace(audit_id)` — trace taint flows for injection findings
- `sentinel_attack_graph(audit_id)` — visualize privilege escalation paths
- `sentinel_exploit_chain(audit_id, finding_id)` — build exploitation narrative
- `sentinel_report(audit_id, format="sarif")` — export for CI/CD
