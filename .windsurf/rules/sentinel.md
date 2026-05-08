---
trigger: manual
description: SENTINEL security auditing — MCP tool reference and usage patterns
---

# SENTINEL Security Auditing

SENTINEL is available via MCP. Use these tools for any security analysis or code review task.

## Tools

| Tool | Purpose |
|------|---------|
| `sentinel_audit(target)` | Full security audit of a path |
| `sentinel_surface(target)` | Attack surface analysis |
| `sentinel_trace(audit_id)` | Taint flow (user input → sinks) |
| `sentinel_attack_graph(audit_id)` | Trust boundaries / privilege escalation |
| `sentinel_logic(audit_id)` | IDOR, BAC, logic flaws |
| `sentinel_review(file_path)` | Single file deep review |
| `sentinel_verify(audit_id, finding_id)` | Verify or dismiss a finding |
| `sentinel_diff(repo_path, base)` | Git diff security audit |
| `sentinel_harden(target)` | Hardening checklist |
| `sentinel_exploit_chain(audit_id, finding_id)` | Exploitation chain narrative |
| `sentinel_hunt(target, tags?)` | Tag-focused scan |
| `sentinel_rules()` | List all rules |
| `sentinel_report(audit_id, format?)` | Get report (markdown/json/sarif) |

## Typical Flow

```
# Audit → trace → exploit → export
sentinel_audit(target="./")
sentinel_trace(audit_id="<id>")
sentinel_exploit_chain(audit_id="<id>", finding_id="<id>")
sentinel_report(audit_id="<id>", format="sarif")
```

## Triggers

Use SENTINEL when the user mentions: security review, vulnerability scan, audit, penetration test, attack surface, SQL injection, command injection, IDOR, authorization bypass, privilege escalation, hardening, CVE, exploit, or similar security topics.
