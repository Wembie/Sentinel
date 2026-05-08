# SENTINEL

AI-powered contextual security auditing platform. Detects realistic vulnerabilities, exploit chains, and insecure architectural patterns through deep offensive-minded analysis.

## Architecture

```
sentinel/
├── core/
│   ├── engine.py       # Top-level orchestrator; wires everything, drives pipeline
│   ├── pipeline.py     # Composable async stage runner (Callable-based, not class hierarchy)
│   ├── context.py      # AuditContext — mutable accumulation bus flowing through all stages
│   └── registry.py     # Generic plugin/component registry with @register decorator
├── models/
│   ├── finding.py      # Finding, Severity, Confidence, Location, ExploitChainStep
│   ├── audit.py        # AuditRequest, AuditResult, AuditSummary, AuditStatus
│   └── graph.py        # GraphNode, GraphEdge, NodeType, EdgeType, TrustLevel
├── analyzers/
│   └── base.py         # Analyzer Protocol — structural typing, no inheritance required
├── graph/
│   ├── backend.py      # GraphBackend Protocol + NetworkXBackend (Neo4j-ready)
│   ├── builder.py      # Builds context graph from parsed ASTs
│   └── queries.py      # Trust boundary crossings, taint paths, privilege reachability
├── llm/
│   ├── base.py         # LLMProvider Protocol (provider-agnostic)
│   ├── claude.py       # Anthropic Claude — prompt caching enabled
│   ├── openai.py       # OpenAI backend
│   └── router.py       # Provider instantiation from config
├── parsers/
│   ├── base.py         # Parser Protocol + language extension map
│   ├── project.py      # File ingestion stage (async, respects limits)
│   └── treesitter.py   # Tree-sitter AST extraction (graceful fallback)
├── rules/
│   ├── base.py         # Rule Protocol + RuleMetadata dataclass
│   ├── loader.py       # Builtin + directory-based rule discovery
│   └── builtin/
│       ├── injection.py  # INJ-001 SQL injection, INJ-002 command injection
│       └── auth.py       # AUTH-001 hardcoded secrets, AUTH-002 TLS disabled
├── reporting/
│   ├── markdown_reporter.py  # Human-readable findings report
│   ├── json_reporter.py      # Machine-readable full result
│   └── sarif_reporter.py     # SARIF 2.1.0 — GitHub Code Scanning compatible
├── api/
│   ├── main.py               # FastAPI app with lifespan engine init
│   └── routes/audit.py       # POST /audit, GET /audit/{id}, GET /audit/{id}/report
├── tracing/tracer.py   # AuditTracer with async span context manager
├── plugins/loader.py   # External plugin discovery from directories
├── logging.py          # structlog configuration (JSON in CI, console in TTY)
├── config.py           # pydantic-settings — all config via SENTINEL_* env vars
└── cli.py              # Typer CLI: sentinel audit, sentinel serve, sentinel rules
```

## Key Design Decisions

**Protocol-based interfaces** — every subsystem boundary (Analyzer, Rule, Parser, LLMProvider, GraphBackend, ReportFormatter) is a `Protocol`. Plugins and third-party analyzers implement the interface structurally — no imports from sentinel base classes required.

**AuditContext as accumulation bus** — a single mutable object flows through every pipeline stage. Stages are independent callables that read from and write to it. No shared state via class fields; no threading issues since the pipeline is sequential.

**Pipeline as composed callables** — stages are `async def stage(ctx: AuditContext) -> None`. Adding a stage is `pipeline.add_stage("name", fn)`. No subclassing, no lifecycle hooks, no framework magic.

**LLM as oracle, not driver** — structural analysis (AST + regex rules) pre-filters candidates first. LLM is invoked only at the enrichment stage for contextual reasoning over the top findings. Keeps costs predictable and analysis fast for LLM-disabled runs.

**Graph as first-class citizen** — every function, class, endpoint, and data flow is a node. Trust levels annotate nodes. Edges carry taint markers. GraphQueries exposes traversal primitives for trust boundary analysis and user-input-to-sink path detection.

**Flat config via pydantic-settings** — `SENTINEL_LLM_PROVIDER=claude`, `SENTINEL_LLM_API_KEY=...`. No nested delimiter complexity. Works cleanly in Docker, k8s, and `.env` files.

## Quickstart

```bash
# Install with uv
uv sync

# Run audit on a local codebase (no LLM)
uv run sentinel audit ./my-project --no-llm

# Run with Claude LLM enrichment
SENTINEL_LLM_API_KEY=your-key uv run sentinel audit ./my-project

# Output as SARIF (GitHub Code Scanning)
uv run sentinel audit ./my-project -f sarif -o results.sarif

# Start API server
uv run sentinel serve

# List available rules
uv run sentinel rules

# Run tests
uv run pytest
```

## Adding Rules

Create a Python file in `sentinel/rules/builtin/` or any directory in `SENTINEL_RULES_DIRS`:

```python
from sentinel.rules.base import BaseRule, RuleMetadata
from sentinel.models.finding import Finding, Severity, Confidence

class MyRule(BaseRule):
    metadata = RuleMetadata(
        id="CUSTOM-001",
        title="My Custom Rule",
        severity="high",
        confidence="medium",
        cwe_ids=["CWE-XXX"],
        languages=["python"],
    )

    async def match(self, ctx):
        findings = []
        # inspect ctx.file_contents, ctx.parsed_files, ctx.graph_nodes
        return findings
```

## Adding Analyzers

Implement the `Analyzer` protocol and register via the engine's registry:

```python
from sentinel.analyzers.base import BaseAnalyzer

class MyAnalyzer(BaseAnalyzer):
    name = "my-analyzer"
    description = "Does X"
    supported_languages = ["python"]

    async def analyze(self, ctx):
        # write findings to ctx.add_finding(...)
        pass
```

## Audit Pipeline Stages

| Stage | Description |
|---|---|
| `ingest` | Reads all source files into `ctx.file_contents` |
| `parse_ast` | Runs tree-sitter on supported files, stores ASTs in `ctx.parsed_files` |
| `build_graph` | Builds context graph of files/functions/classes in NetworkX |
| `run_rules` | Runs all registered rules concurrently, collects findings |
| `llm_enrich` | (optional) LLM contextual reasoning over top findings |

## SENTINEL Commands (API / CLI)

| Command | Description |
|---|---|
| `sentinel audit` | Full audit pipeline |
| `sentinel serve` | REST API server |
| `sentinel rules` | List registered rules |
| `POST /audit/` | Submit audit request |
| `GET /audit/{id}` | Get audit result |
| `GET /audit/{id}/report?fmt=sarif` | Formatted report |

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `SENTINEL_LLM_PROVIDER` | `claude` | `claude` / `openai` / `none` |
| `SENTINEL_LLM_MODEL` | `claude-sonnet-4-6` | Model name |
| `SENTINEL_LLM_API_KEY` | — | Provider API key |
| `SENTINEL_GRAPH_BACKEND` | `networkx` | `networkx` / `neo4j` |
| `SENTINEL_MAX_FILE_SIZE_KB` | `512` | Skip files larger than this |
| `SENTINEL_MAX_FILES_PER_AUDIT` | `1000` | Audit file cap |
| `SENTINEL_LOG_LEVEL` | `INFO` | Log level |
| `SENTINEL_SERVER_PORT` | `8000` | API server port |
