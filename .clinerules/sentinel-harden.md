---
name: sentinel-harden
description: Hardening checklist generated from live codebase scan — security headers, TLS, auth, secrets, deps
trigger: /sentinel-harden
mcp_tool: sentinel_harden
---

# sentinel-harden

Generates a hardening checklist from a live codebase scan. Checks for missing security headers, TLS misconfigurations, weak auth patterns, unsafe dependency usage, logging gaps, and other defensive posture issues.

## When to Use

- Pre-production security hardening review
- Security posture assessment
- Preparing a codebase for a penetration test
- Security-focused sprint planning (what to fix next)

## MCP Tool

```
sentinel_harden(target: str) -> HardeningResult
```

### Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `target` | yes | Absolute or relative path to the directory to scan |

### Returns

Categorized checklist: PASS / FAIL / WARN per check, with remediation guidance for each failure.

## Example

```
sentinel_harden(target="./")
```

## Hardening Categories

| Category | Checks |
|----------|--------|
| Security headers | HSTS, CSP, X-Frame-Options, CORS misconfiguration |
| TLS/SSL | Certificate validation disabled, weak cipher suites |
| Authentication | Password hashing (bcrypt/argon2), session management |
| Secrets | Hardcoded API keys, tokens, passwords |
| Logging | Sensitive data in logs, missing audit trails |
| Dependencies | Known vulnerable packages, deprecated APIs |
| Input validation | Missing validation at system boundaries |

## Output Format

```
[FAIL] TLS verification disabled in 2 locations
[WARN] Passwords hashed with MD5 (use bcrypt/argon2)
[PASS] No hardcoded secrets found
[FAIL] Missing Content-Security-Policy header
...
```
