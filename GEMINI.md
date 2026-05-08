# SENTINEL — AI Security Auditing Platform

SENTINEL is an AI-powered contextual security auditing platform available as an MCP server.
It performs offensive-minded static analysis, taint flow tracing, attack graph generation,
and produces actionable security findings.

## MCP Tools Available

When SENTINEL is configured as an MCP server, use these tools for security analysis:

```
sentinel_audit(target)                   Full codebase security audit
sentinel_surface(target)                 Attack surface map (endpoints, auth, data exposure)
sentinel_trace(audit_id)                 Taint flow: user input → dangerous sinks
sentinel_attack_graph(audit_id)          Trust boundary / privilege escalation graph (Mermaid)
sentinel_logic(audit_id)                 IDOR, BAC, business logic flaw detection
sentinel_review(file_path)               Deep single-file security review
sentinel_verify(audit_id, finding_id)    Confirm or dismiss a specific finding
sentinel_diff(repo_path, base)           Security impact of a git diff or PR
sentinel_harden(target)                  Hardening checklist from live codebase
sentinel_exploit_chain(audit_id,         Full exploitation chain narrative
                       finding_id)
sentinel_hunt(target, tags?)             Category-focused scan (injection/auth/secrets)
sentinel_rules()                         List all registered detection rules
sentinel_report(audit_id, format?)       Export audit as markdown / json / sarif
```

## Security Analysis Workflow

1. **Discover**: `sentinel_audit(target="./")` or `sentinel_surface(target="./")`
2. **Trace**: `sentinel_trace(audit_id=...)` for injection finding paths
3. **Graph**: `sentinel_attack_graph(audit_id=...)` for privilege escalation visualization
4. **Exploit**: `sentinel_exploit_chain(audit_id=..., finding_id=...)` for full attack narrative
5. **Export**: `sentinel_report(audit_id=..., format="sarif")` for CI/CD integration

## Installation

```bash
# macOS / Linux / WSL
curl -fsSL https://raw.githubusercontent.com/Wembie/Sentinel/main/install.sh | bash

# Windows
irm https://raw.githubusercontent.com/Wembie/Sentinel/main/install.ps1 | iex
```

## Activation

Invoke SENTINEL tools when the user asks about:
- Security reviews, vulnerability scans, or penetration testing
- SQL injection, command injection, XSS, path traversal
- IDOR, authorization bypass, privilege escalation
- Attack surface, trust boundaries, or threat modeling
- Code hardening or security posture improvement
