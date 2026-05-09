# SENTINEL

**AI-powered contextual security auditing platform. Thinks like a red team operator, not a linter.**

[![CI](https://github.com/Wembie/Sentinel/actions/workflows/ci.yml/badge.svg)](https://github.com/Wembie/Sentinel/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![MCP](https://img.shields.io/badge/MCP-compatible-purple.svg)](https://modelcontextprotocol.io)

---

SENTINEL is a security auditing engine that combines AST analysis, taint flow tracking, call graph traversal, and LLM-powered contextual reasoning to surface realistic vulnerabilities and exploit chains — not just grep hits.

**Basic SAST finds `eval(user_input)`. SENTINEL finds the full path: HTTP param → deserialization → `eval` → RCE, explains why it's exploitable, and shows the attack chain.**

---

## Install

```bash
# macOS / Linux / WSL / Git Bash
curl -fsSL https://raw.githubusercontent.com/Wembie/Sentinel/main/install.sh | bash

# Windows (PowerShell)
irm https://raw.githubusercontent.com/Wembie/Sentinel/main/install.ps1 | iex
```

Detects 30+ agents and registers for each automatically. One-line install, no manual config.

**Install flags:**

```bash
bash install.sh --all          # install + hooks + init
bash install.sh --with-hooks   # add Claude Code SessionStart hook
bash install.sh --with-init    # write agent rules to current project
bash install.sh --minimal      # plugin/skills only, no hooks
bash install.sh --dry-run      # preview without writing
bash install.sh --list         # show detected agents
```

**What gets installed:**
- SENTINEL as MCP server registered with your agents
- Agent rule files (`.cursor/rules/`, `.windsurf/rules/`, `.clinerules/`)
- Skills CLI entries for 30+ additional agents
- Claude Code hooks (with `--with-hooks`) for auto-activation at session start

**No API key required.** All structural analysis (AST, rules, graph) works offline. LLM enrichment is opt-in.

---

## Quick Start

```bash
# Audit a codebase — no configuration needed
sentinel audit ./my-project --no-llm

# With LLM enrichment (Claude)
SENTINEL_LLM_API_KEY=sk-ant-... sentinel audit ./my-project

# Output SARIF for GitHub Code Scanning
sentinel audit ./my-project -f sarif -o results.sarif

# Audit only the security diff on a PR
sentinel diff ./my-project --base main

# List all detection rules
sentinel rules
```

First run works with zero setup. No `.env` to copy, no config to write.

---

## MCP Integration

SENTINEL runs as an MCP server — a local process your agent connects to and invokes as tools. Once registered, your agent calls `sentinel_audit`, `sentinel_trace`, and the rest exactly like any built-in tool.

```bash
# Start the MCP server manually (usually handled by your agent)
sentinel-mcp

# Or via uv (development)
uv run python -m sentinel.mcp
```

**Automatic registration** — the installer writes the MCP server config for each detected agent. For Claude Code:

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

**Supported agents and runtimes:**

| Category | Agents |
|----------|--------|
| Claude family | Claude Code, Claude Desktop |
| IDE agents | Cursor, Windsurf, Cline, Continue, Roo |
| Terminal | Codex, Aider, Aider-Desk |
| Web | Copilot, Devin, OpenHands, v0 |
| Skills CLI | 30+ additional agents via `npx -y skills add` |

Configuration is portable — one install works across all agents without per-agent manual setup.

---

## MCP Tools

Thirteen tools covering the full offensive analysis lifecycle:

| Tool | Purpose |
|------|---------|
| `sentinel_audit` | Full deep audit — AST, call graph, all rules, LLM enrichment |
| `sentinel_surface` | Fast attack surface map: endpoints, auth entry points, exposed data |
| `sentinel_trace` | Taint flow: user input → dangerous sinks (SQLi, RCE, SSRF) |
| `sentinel_attack_graph` | Trust boundary and privilege escalation graph (Mermaid output) |
| `sentinel_logic` | IDOR, BAC, unvalidated redirects, business logic flaws |
| `sentinel_review` | Deep single-file security review |
| `sentinel_verify` | Confirm or dismiss a specific finding |
| `sentinel_diff` | Security impact of a git diff — PR and commit auditing |
| `sentinel_harden` | Hardening checklist generated from live codebase scan |
| `sentinel_exploit_chain` | Full exploitation chain narrative for a specific finding |
| `sentinel_hunt` | Tag-focused scan: `injection`, `auth`, `secrets` |
| `sentinel_rules` | List all registered detection rules with metadata |
| `sentinel_report` | Retrieve a stored audit as markdown / json / sarif |

**Typical workflows:**

```
# Full audit → taint trace → exploit chain → SARIF export
sentinel_audit(target="./")
sentinel_trace(audit_id="<id>")
sentinel_exploit_chain(audit_id="<id>", finding_id="<top finding>")
sentinel_report(audit_id="<id>", format="sarif")

# PR security review
sentinel_diff(repo_path="./", base="main")
sentinel_verify(audit_id="<id>", finding_id="<finding>")

# Targeted injection hunt
sentinel_hunt(target="./", tags="injection,sqli")
sentinel_logic(audit_id="<id>")
sentinel_attack_graph(audit_id="<id>")
```

---

## Skills

SENTINEL ships nine skills — structured prompts that give agents deep context on how to use each tool effectively.

| Skill | Trigger |
|-------|---------|
| `sentinel-audit` | Full codebase security audit workflow |
| `sentinel-surface` | Attack surface enumeration |
| `sentinel-trace` | Taint flow and injection path analysis |
| `sentinel-attack-graph` | Trust boundary and privilege escalation |
| `sentinel-logic` | IDOR, BAC, business logic analysis |
| `sentinel-review` | Single-file deep review |
| `sentinel-diff` | PR / git diff security review |
| `sentinel-exploit-chain` | Exploitation chain narrative |
| `sentinel-harden` | Hardening recommendations |

Skills are discovered automatically by the Skills CLI and compatible agents. Install via:

```bash
npx -y skills add https://github.com/Wembie/Sentinel
```

In agents that support slash commands, invoke as `/sentinel-audit`, `/sentinel-diff`, etc.

---

## Claude Code Hooks

SENTINEL ships a `SessionStart` hook that auto-injects tool availability context at the start of every session — no slash command needed.

```bash
# Install once
bash ~/.sentinel/hooks/install.sh

# Windows
& "$HOME\.sentinel\hooks\install.ps1"
```

The hook checks if SENTINEL is registered as an MCP server and injects a tool reminder into the system prompt. A `🛡 SENTINEL` badge appears in the statusline when active.

```bash
# Uninstall
bash ~/.sentinel/hooks/uninstall.sh
```

---

## Per-Project Setup

Write SENTINEL agent rules into any project root:

```bash
sentinel init
# or with uv:
uv run sentinel init
```

Writes:
- `.cursor/rules/sentinel.mdc`
- `.windsurf/rules/sentinel.md`
- `.clinerules/sentinel.md`
- Appends to `AGENTS.md`
- Appends to `.github/copilot-instructions.md`

Safe to re-run (idempotent). Use `--force` to overwrite existing files.

---

## Configuration

All config via environment variables — no config file required. Sensible defaults work out of the box.

| Variable | Default | Description |
|----------|---------|-------------|
| `SENTINEL_LLM_PROVIDER` | `none` | `claude` \| `openai` \| `none` |
| `SENTINEL_LLM_MODEL` | `claude-sonnet-4-6` | Model identifier |
| `SENTINEL_LLM_API_KEY` | — | API key (optional, LLM enrichment only) |
| `SENTINEL_LOG_LEVEL` | `INFO` | `DEBUG` \| `INFO` \| `WARNING` |
| `SENTINEL_MAX_FILE_SIZE_KB` | `512` | Per-file size cap |
| `SENTINEL_MAX_FILES_PER_AUDIT` | `1000` | File count cap per audit |
| `SENTINEL_RULES_DIRS` | — | Extra rule directories (colon-separated) |
| `SENTINEL_PLUGIN_DIRS` | — | Extra plugin directories |

**Config file** (optional, higher priority than env vars):
`~/.config/sentinel/config.json` or `~/.sentinel/config.json`

```json
{
  "llm_provider": "claude",
  "llm_api_key": "sk-ant-...",
  "log_level": "INFO"
}
```

---

## REST API

```bash
# Start server
sentinel serve --port 8000

# Submit audit
curl -X POST http://localhost:8000/audit/ \
  -H 'Content-Type: application/json' \
  -d '{"target": "/path/to/project", "llm_enabled": false}'

# Get result
curl http://localhost:8000/audit/{id}

# Get report
curl "http://localhost:8000/audit/{id}/report?fmt=sarif"
```

---

## Adding Rules

Drop a Python file in `sentinel/rules/builtin/` or any directory in `SENTINEL_RULES_DIRS`:

```python
from sentinel.rules.base import BaseRule, RuleMetadata
from sentinel.models.finding import Finding, Severity, Confidence

class MyRule(BaseRule):
    metadata = RuleMetadata(
        id="CUSTOM-001",
        title="Unsafe deserialization",
        severity="critical",
        confidence="high",
        cwe_ids=["CWE-502"],
        languages=["python"],
    )

    async def match(self, ctx):
        findings = []
        for path, content in ctx.file_contents.items():
            if "pickle.loads" in content:
                findings.append(Finding(...))
        return findings
```

Rules implement a `Protocol` — no imports from sentinel base classes required at runtime.

---

## Architecture

```
sentinel/
├── core/
│   ├── engine.py       # Orchestrator — wires subsystems, drives pipeline
│   ├── pipeline.py     # Composable async stage runner
│   ├── context.py      # AuditContext — accumulation bus across all stages
│   └── registry.py     # Generic plugin registry with @register decorator
├── models/             # Finding, AuditRequest/Result, GraphNode/Edge (Pydantic)
├── graph/              # NetworkX call graph — trust boundaries, taint paths
├── llm/                # LLMProvider Protocol + Claude and OpenAI backends
├── parsers/            # File ingestion + tree-sitter AST extraction
├── rules/              # Rule Protocol + builtin rules (injection, auth)
├── reporting/          # Markdown, JSON, SARIF 2.1.0 reporters
├── api/                # FastAPI REST API with lifespan engine init
├── tracing/            # AuditTracer with async span context manager
├── plugins/            # External plugin discovery from directories
└── mcp.py              # MCP server — all 13 tools exposed as MCP endpoints
```

**Design principles:**

- **Protocol-based interfaces** — every boundary (Rule, Parser, Analyzer, LLMProvider, ReportFormatter) is a structural `Protocol`. Plugins implement the interface without importing from sentinel.
- **AuditContext as accumulation bus** — single mutable object flows through every stage. No shared class state, no threading issues.
- **LLM as oracle, not driver** — AST + rule analysis pre-filters candidates first. LLM enrichment is opt-in and cost-predictable.
- **Graph as first-class citizen** — functions, classes, endpoints, and data flows are nodes. Trust levels annotate nodes. Edges carry taint markers.

---

## Audit Pipeline

| Stage | What happens |
|-------|-------------|
| `ingest` | Reads source files into `ctx.file_contents` |
| `parse_ast` | Runs tree-sitter, stores ASTs in `ctx.parsed_files` |
| `build_graph` | Builds call graph of files/functions/classes |
| `run_rules` | Runs all rules concurrently, collects findings |
| `llm_enrich` | (opt-in) LLM contextual reasoning over top findings |

---

## Development

```bash
# Clone and install with dev dependencies
git clone https://github.com/Wembie/Sentinel
cd Sentinel
uv sync --group dev

# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=sentinel

# Lint
uv run ruff check sentinel/
uv run black --check sentinel/
uv run mypy sentinel/

# List builtin rules
uv run sentinel rules
```

Python 3.11+ required. All tooling managed via [uv](https://docs.astral.sh/uv/).

---

## Contributing

1. Fork → branch → PR to `main`
2. New rules go in `sentinel/rules/builtin/` or as a documented pattern in the PR
3. New MCP tools: add to `sentinel/mcp.py` + add a corresponding `skills/<name>/SKILL.md`
4. CI runs ruff, mypy, black, and pytest on every PR

Issues and PRs welcome. Keep diffs small, findings clear, and test coverage honest.

---

## License

MIT — audit freely, ship securely.
