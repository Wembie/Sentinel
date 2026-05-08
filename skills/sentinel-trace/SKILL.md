---
name: sentinel-trace
description: Taint flow analysis — trace user-controlled input to dangerous sinks (SQLi, RCE, SSRF)
trigger: /sentinel-trace
mcp_tool: sentinel_trace
---

# sentinel-trace

Taint flow analysis: follows user-controlled data from entry points (HTTP params, form fields, env vars) to dangerous sinks (SQL queries, shell commands, file writes, network calls). Surfaces complete path chains.

## When to Use

- Investigating SQL injection or command injection findings
- Understanding how user input reaches sensitive operations
- Verifying that sanitization actually breaks the taint chain
- Building evidence for a specific injection finding

## MCP Tool

```
sentinel_trace(audit_id: str) -> TraceResult
```

### Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `audit_id` | yes | UUID from a previous `sentinel_audit` or `sentinel_surface` call |

### Returns

Taint paths with source → sanitizer chain → sink details, confidence scores, and affected code locations.

## Example

```
# First audit, then trace
result = sentinel_audit(target="./")
sentinel_trace(audit_id=result["audit_id"])
```

## Taint Sources Tracked

- HTTP request parameters, headers, cookies
- Environment variables (`os.environ`, `process.env`)
- File system reads (`open()`, `fs.readFile`)
- Database query results fed back into further queries
- Deserialized user data

## Dangerous Sinks Tracked

- SQL query execution (`execute()`, `query()`, raw f-strings in DB calls)
- Shell command execution (`subprocess`, `exec`, `eval`)
- File path operations with user data
- Network requests with user-controlled URLs (SSRF)
- Template rendering with unescaped user data (SSTI)
