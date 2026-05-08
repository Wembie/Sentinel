---
name: sentinel-review
description: Deep security review of a single file — full rule set + context-aware analysis
trigger: /sentinel-review
mcp_tool: sentinel_review
---

# sentinel-review

Deep security review of a single source file. Runs the full detection rule set against the file, performs context-aware analysis (call patterns, data flow within the file), and optionally enriches findings with LLM analysis.

## When to Use

- User asks to review a specific file for security issues
- Focused review before merging a security-sensitive change
- Reviewing a newly added authentication or authorization module
- Quick check on a file that handles user input or database access

## MCP Tool

```
sentinel_review(file_path: str) -> ReviewResult
```

### Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `file_path` | yes | Absolute or relative path to the file to review |

### Returns

Findings specific to that file with code locations, severity, CWE references, and remediation guidance.

## Example

```
sentinel_review(file_path="./app/auth/login.py")
sentinel_review(file_path="./src/api/users.js")
sentinel_review(file_path="./controllers/payment.go")
```

## What Gets Checked

- Injection vectors (SQL, command, path traversal, SSTI)
- Authentication and authorization patterns
- Hardcoded secrets and credentials
- TLS/SSL misconfigurations
- Insecure deserialization patterns
- Race conditions in critical sections
- Unsafe use of cryptographic primitives
