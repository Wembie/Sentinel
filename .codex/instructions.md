# SENTINEL Security Auditing

SENTINEL exposes security analysis capabilities via MCP. When asked about security, use these tools.

## MCP Tools

```
sentinel_audit(target)                   Full codebase security audit
sentinel_surface(target)                 Attack surface map
sentinel_trace(audit_id)                 Taint flow analysis
sentinel_attack_graph(audit_id)          Trust boundary graph (Mermaid)
sentinel_logic(audit_id)                 IDOR/BAC/logic flaw detection
sentinel_review(file_path)               Single file security review
sentinel_verify(audit_id, finding_id)    Verify or dismiss finding
sentinel_diff(repo_path, base)           Git diff security audit
sentinel_harden(target)                  Hardening checklist
sentinel_exploit_chain(audit_id,         Exploitation chain narrative
                       finding_id)
sentinel_hunt(target, tags?)             Category-focused vulnerability scan
sentinel_rules()                         List detection rules
sentinel_report(audit_id, format?)       Export report (markdown/json/sarif)
```

## Quick Pattern

```python
# Audit codebase
result = sentinel_audit(target="./")
audit_id = result["audit_id"]

# Trace user input flows
sentinel_trace(audit_id=audit_id)

# Build exploit chain for top finding
sentinel_exploit_chain(audit_id=audit_id, finding_id=result["findings"][0]["id"])

# Export for CI
sentinel_report(audit_id=audit_id, format="sarif")
```
