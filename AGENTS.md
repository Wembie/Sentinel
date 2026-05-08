# SENTINEL — AI Security Auditing Runtime

SENTINEL is a security analysis platform exposed via MCP (Model Context Protocol).
It provides offensive-minded static analysis, taint flow tracing, attack graph generation,
and AI-enriched findings. No API key required for structural analysis.

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

## Installation

```bash
# macOS / Linux / WSL
curl -fsSL https://raw.githubusercontent.com/Wembie/Sentinel/main/install.sh | bash

# Windows PowerShell
irm https://raw.githubusercontent.com/Wembie/Sentinel/main/install.ps1 | iex

# Skills CLI — works with Cursor, Windsurf, Cline, Continue, Roo, and 30+ agents
npx -y skills add https://github.com/Wembie/Sentinel

# Claude Code plugin marketplace
claude plugin marketplace add sentinel

# Gemini CLI extension
gemini extensions install https://github.com/Wembie/Sentinel

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

Local dev (from project root):
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

## Agent Coverage

SENTINEL works across all major AI coding environments:

| Agent | Integration |
|-------|------------|
| Claude Code | Plugin marketplace, MCP auto-registration, session hooks |
| Gemini CLI | Extension install (`gemini extensions install`) |
| Codex CLI | MCP config + `.codex/config.toml` hooks |
| Cursor | `.cursor/rules/sentinel.mdc` (always-on) + skills |
| Windsurf | `.windsurf/rules/sentinel.md` (manual) + skills |
| Cline | `.clinerules/sentinel.md` (always-on) + skills |
| Continue | MCP config + skills |
| Roo | MCP config + skills |
| GitHub Copilot | `.github/copilot-instructions.md` |
| VS Code | MCP config |
| JetBrains | MCP config |
| OpenHands | MCP config |
| Any agent | `npx -y skills add https://github.com/Wembie/Sentinel` |

## Supported Languages

Python, JavaScript, TypeScript, Go, Ruby, Java, Rust, PHP, C#, C/C++, Shell, YAML, Terraform.
Language auto-detected from file extensions. Filter via `languages` parameter.

## Configuration

All configuration via environment variables — no `.env` file required.

| Variable | Default | Purpose |
|----------|---------|---------|
| `SENTINEL_LLM_PROVIDER` | `none` | `claude` \| `openai` \| `none` |
| `SENTINEL_LLM_API_KEY` | — | API key (optional, for LLM enrichment) |
| `SENTINEL_MAX_FILE_SIZE_KB` | `512` | Per-file size cap |
| `SENTINEL_MAX_FILES_PER_AUDIT` | `1000` | File count cap |
| `SENTINEL_RULES_DIRS` | — | Extra rule directories |
| `SENTINEL_PLUGIN_DIRS` | — | Extra plugin directories |

Optional config file (takes priority over env vars):
`~/.config/sentinel/config.json` or `~/.sentinel/config.json`
