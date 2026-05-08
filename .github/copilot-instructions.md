# SENTINEL Security Auditing

SENTINEL is an AI-powered security analysis platform available as an MCP server.

## When to Use

Use SENTINEL MCP tools when asked about: security reviews, vulnerability scans, penetration testing prep, attack surface analysis, SQL injection, command injection, authentication bypass, IDOR, privilege escalation, hardening, or code auditing.

## MCP Tools

- `sentinel_audit(target)` — full project security audit
- `sentinel_surface(target)` — attack surface mapping
- `sentinel_trace(audit_id)` — taint flow analysis (user input → dangerous sinks)
- `sentinel_attack_graph(audit_id)` — trust boundary and privilege escalation graph
- `sentinel_logic(audit_id)` — IDOR, BAC, and logic flaw detection
- `sentinel_review(file_path)` — single file deep security review
- `sentinel_verify(audit_id, finding_id)` — verify or dismiss a finding
- `sentinel_diff(repo_path, base)` — security review of a git diff or PR
- `sentinel_harden(target)` — hardening checklist from codebase
- `sentinel_exploit_chain(audit_id, finding_id)` — full exploitation chain
- `sentinel_hunt(target, tags?)` — targeted scan by category
- `sentinel_rules()` — list detection rules
- `sentinel_report(audit_id, format?)` — export as markdown/json/sarif

## Workflow

1. `sentinel_audit` or `sentinel_surface` → discover findings
2. `sentinel_trace` + `sentinel_attack_graph` → understand attack paths
3. `sentinel_exploit_chain` → build the full narrative
4. `sentinel_report(format="sarif")` → CI/CD integration
