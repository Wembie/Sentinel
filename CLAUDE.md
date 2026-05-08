# SENTINEL — AI Security Auditing Platform

SENTINEL is an AI-powered contextual security auditing platform running as an MCP server.
It thinks like a red team operator, not a basic linter.

## MCP Tools

| Tool | Purpose |
|------|---------|
| `sentinel_audit` | Full deep audit — ingest, parse ASTs, build call graph, run all detection rules |
| `sentinel_surface` | Fast attack surface map: endpoints, auth entry points, data exposure |
| `sentinel_trace` | Taint flow: user input → dangerous sinks (SQLi, RCE, SSRF paths) |
| `sentinel_attack_graph` | Trust boundary and privilege escalation graph, rendered as Mermaid |
| `sentinel_logic` | IDOR, BAC, unvalidated redirects, business logic flaws |
| `sentinel_review` | Deep single-file security review |
| `sentinel_verify` | Confirm or dismiss a specific finding from a previous audit |
| `sentinel_diff` | Security impact of a git diff — PR and commit auditing |
| `sentinel_harden` | Hardening checklist generated from live codebase scan |
| `sentinel_exploit_chain` | Full exploitation chain narrative for a specific finding |
| `sentinel_hunt` | Fast category-focused scan: injection / auth / secrets |
| `sentinel_rules` | List all registered detection rules with metadata |
| `sentinel_report` | Retrieve a stored audit as markdown / json / sarif |

## When to Invoke SENTINEL Tools

Invoke proactively when the user:
- Asks for a security review, audit, or vulnerability scan → `sentinel_audit`
- Asks about attack surface, exposed endpoints, or entry points → `sentinel_surface`
- Asks about SQL injection, command injection, or data flow → `sentinel_trace`
- Asks about privilege escalation or trust boundaries → `sentinel_attack_graph`
- Asks about IDOR, authorization bypass, or logic flaws → `sentinel_logic`
- Wants a specific file reviewed for security → `sentinel_review`
- Shares a git diff or PR for security review → `sentinel_diff`
- Asks for hardening recommendations → `sentinel_harden`
- Wants to understand how a finding could be exploited → `sentinel_exploit_chain`
- Wants to scan for a specific vulnerability class → `sentinel_hunt`
- Wants to re-check a dismissed or unresolved finding → `sentinel_verify`

## Typical Workflows

### Full project audit
```
sentinel_audit(target="./")
sentinel_trace(audit_id="<id from above>")
sentinel_exploit_chain(audit_id="<id>", finding_id="<top finding>")
sentinel_report(audit_id="<id>", format="sarif")
```

### PR security review
```
sentinel_diff(repo_path="./", base="main")
sentinel_verify(audit_id="<id>", finding_id="<finding>")
```

### Targeted hunt
```
sentinel_hunt(target="./", tags="injection,sqli")
sentinel_logic(audit_id="<id>")
sentinel_attack_graph(audit_id="<id>")
```

## Configuration

All configuration via environment variables — no `.env` file required:

| Variable | Default | Purpose |
|----------|---------|---------|
| `SENTINEL_LLM_PROVIDER` | `none` | `claude` \| `openai` \| `none` |
| `SENTINEL_LLM_API_KEY` | — | API key for LLM enrichment (optional) |
| `SENTINEL_LLM_MODEL` | `claude-sonnet-4-6` | Model identifier |
| `SENTINEL_LOG_LEVEL` | `INFO` | `DEBUG` \| `INFO` \| `WARNING` |
| `SENTINEL_MAX_FILE_SIZE_KB` | `512` | Per-file size cap |
| `SENTINEL_MAX_FILES_PER_AUDIT` | `1000` | File count cap |
| `SENTINEL_RULES_DIRS` | — | Extra rule directories (colon-separated) |
| `SENTINEL_PLUGIN_DIRS` | — | Extra plugin directories |

Config file (optional, higher priority than env vars):
`~/.config/sentinel/config.json` or `~/.sentinel/config.json`

## Installation

```bash
# macOS / Linux / WSL
curl -fsSL https://raw.githubusercontent.com/Wembie/Sentinel/main/install.sh | bash

# Windows PowerShell
irm https://raw.githubusercontent.com/Wembie/Sentinel/main/install.ps1 | iex

# With Claude Code hooks (auto-activates SENTINEL at session start)
bash install.sh --with-hooks

# Via Claude Code plugin marketplace
claude plugin marketplace add sentinel

# Via skills CLI (works with Cursor, Windsurf, Cline, and 30+ agents)
npx -y skills add https://github.com/Wembie/Sentinel
```

## Claude Code Hooks

SENTINEL ships a SessionStart hook that auto-injects tool availability context at session start.
Install once — active in every future session:

```bash
bash ~/.sentinel/hooks/install.sh
# or on Windows:
& "$HOME\.sentinel\hooks\install.ps1"
```

The hook:
- Checks if `sentinel` is registered as an MCP server
- Injects a reminder listing available tools into the system prompt
- Shows `🛡 SENTINEL` badge in the statusline

Uninstall: `bash ~/.sentinel/hooks/uninstall.sh`

## Per-Project Setup

Run `sentinel init` from any project root to write SENTINEL agent rules:
```bash
uv run sentinel init
# or, after global install:
sentinel init
```

Writes: `.cursor/rules/sentinel.mdc`, `.windsurf/rules/sentinel.md`, `.clinerules/sentinel.md`,
appends to `AGENTS.md` and `.github/copilot-instructions.md`.
