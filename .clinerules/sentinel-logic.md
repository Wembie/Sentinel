---
name: sentinel-logic
description: Business logic and authorization flaw detection — IDOR, BAC, privilege injection, unvalidated redirects
trigger: /sentinel-logic
mcp_tool: sentinel_logic
---

# sentinel-logic

Business logic flaw analysis: detects insecure direct object references (IDOR), broken access control (BAC), privilege injection, mass assignment, unvalidated redirects, and other authorization pattern flaws that static rules alone miss.

## When to Use

- User asks about authorization bypass or access control issues
- Investigating IDOR vulnerabilities (accessing other users' data)
- Checking whether privilege checks are consistently applied
- Reviewing multi-tenant applications for data isolation

## MCP Tool

```
sentinel_logic(audit_id: str) -> LogicResult
```

### Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `audit_id` | yes | UUID from a previous `sentinel_audit` call |

### Returns

Logic flaw findings with affected code paths, attack scenarios, and severity ratings.

## Patterns Detected

| Pattern | Description |
|---------|-------------|
| IDOR | Object IDs accessed without ownership verification |
| BAC | Missing or inconsistent authorization checks on routes/methods |
| Privilege injection | User-controlled data used in role/permission lookups |
| Mass assignment | Model attributes bound directly from request params without allowlist |
| Unvalidated redirect | `next`, `redirect_to`, `returnUrl` parameters not validated |
| Forced browsing | Direct URL access bypasses frontend guards |

## Example

```
result = sentinel_audit(target="./")
sentinel_logic(audit_id=result["audit_id"])
```
