# SENTINEL — AI Security Auditing Runtime

SENTINEL is a security analysis platform exposed via MCP (Model Context Protocol).
It provides offensive-minded static analysis, taint flow tracing, attack graph generation,
and AI-enriched findings.

## MCP Tool Reference

When SENTINEL is configured as an MCP server, these tools are available:

```
sentinel_audit(target, languages?)         Full security audit of a path
sentinel_surface(target, languages?)       Attack surface analysis
sentinel_trace(audit_id)                   Taint flow: input → sinks
sentinel_attack_graph(audit_id)            Trust boundary / privilege escalation graph
sentinel_logic(audit_id)                   IDOR, BAC, business logic flaw detection
sentinel_review(file_path)                 Deep security review of a single file
sentinel_verify(audit_id, finding_id)      Confirm or dismiss a specific finding
sentinel_diff(repo_path, base, head?)      Git diff security audit
sentinel_harden(target)                    Hardening checklist from codebase scan
sentinel_exploit_chain(audit_id,           Full exploitation chain narrative
                       finding_id)
sentinel_hunt(target, tags?)               Tag-focused scan: injection/auth/secrets
sentinel_rules()                           List all detection rules
sentinel_report(audit_id, format?)         Get audit report (markdown/json/sarif)
```

## Setup

```bash
# macOS / Linux / WSL
curl -fsSL https://raw.githubusercontent.com/Wembie/Sentinel/main/install.sh | bash

# Windows PowerShell
irm https://raw.githubusercontent.com/Wembie/Sentinel/main/install.ps1 | iex

# From source (uv required)
uv run python -m sentinel.mcp
```

## MCP Configuration (stdio transport)

```json
{
  "mcpServers": {
    "sentinel": {
      "command": "uv",
      "args": ["run", "--project", "~/.sentinel", "python", "-m", "sentinel.mcp"]
    }
  }
}
```

Or from project root (local dev):
```json
{
  "mcpServers": {
    "sentinel": {
      "command": "uv",
      "args": ["run", "python", "-m", "sentinel.mcp"]
    }
  }
}
```

## Security Analysis Workflow

1. **Discover** — `sentinel_audit` or `sentinel_surface` to map the codebase
2. **Trace** — `sentinel_trace` to follow user input to dangerous sinks
3. **Graph** — `sentinel_attack_graph` to visualize trust boundaries
4. **Exploit** — `sentinel_exploit_chain` to build the full attack narrative
5. **Export** — `sentinel_report(format="sarif")` for CI/CD integration

## Supported Languages

Python, JavaScript, TypeScript, Go, Ruby, Java, Rust, PHP, C#, C/C++, Shell, YAML, Terraform.
Language auto-detected from file extensions. Filter via `languages` parameter.
