"""SENTINEL MCP Server — Production Runtime.

Editor-agnostic, provider-agnostic, cross-platform MCP server that exposes
SENTINEL as native tools in any MCP-compatible AI coding environment.

Supported environments:
    Claude Code, Cursor, Windsurf, VS Code (Copilot MCP), JetBrains,
    OpenHands, terminal agents, CI/CD pipelines, autonomous agents.

Entrypoints:
    uv run python -m sentinel.mcp        # from project root (local dev)
    python -m sentinel.mcp               # if installed via pip
    sentinel-mcp                         # if entry-point script is on PATH

Configuration via environment variables (no hardcoded paths):
    SENTINEL_LLM_PROVIDER       claude | openai | none  (default: none)
    SENTINEL_LLM_API_KEY        API key for the active LLM provider
    SENTINEL_LLM_MODEL          Model identifier
    SENTINEL_LOG_LEVEL          DEBUG | INFO | WARNING   (default: INFO)
    SENTINEL_MAX_FILE_SIZE_KB   Max KB per file          (default: 512)
    SENTINEL_MAX_FILES_PER_AUDIT  File cap per audit     (default: 1000)
    SENTINEL_RULES_DIRS         Extra rule dirs, colon-separated
    SENTINEL_PLUGIN_DIRS        Extra plugin dirs, colon-separated
"""

from __future__ import annotations

import asyncio
import os
import re
import subprocess
from pathlib import Path
from typing import Any

import structlog
from mcp.server.fastmcp import FastMCP

from sentinel.config import get_settings
from sentinel.logging import configure_logging
from sentinel.models.audit import AuditRequest, AuditScope

configure_logging(os.getenv("SENTINEL_LOG_LEVEL", "INFO"))
log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# MCP instance
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "SENTINEL",
    instructions=(
        "AI-powered contextual security auditing platform. "
        "sentinel_audit: full deep audit. "
        "sentinel_surface: fast attack surface map. "
        "sentinel_trace: taint flow analysis (user input → sensitive sinks). "
        "sentinel_attack_graph: trust boundary / privilege escalation graph. "
        "sentinel_logic: business logic and auth flaw analysis. "
        "sentinel_review: deep security review of a single file. "
        "sentinel_verify: confirm or dismiss a specific finding. "
        "sentinel_diff: security impact of git changes (PR/commit audit). "
        "sentinel_harden: hardening checklist from codebase scan. "
        "sentinel_exploit_chain: full exploitation path for a finding. "
        "sentinel_hunt: fast category-focused scan (injection/auth/secrets). "
        "sentinel_rules: list all registered detection rules. "
        "sentinel_report: retrieve stored audit in markdown/json/sarif."
    ),
)

# ---------------------------------------------------------------------------
# Session store
# Tuple: (AuditResult, AuditRequest | None)
# Keyed by str(AuditResult.id)
# ---------------------------------------------------------------------------

_store: dict[str, tuple[Any, Any]] = {}


def _store_result(result: Any, request: Any = None) -> str:
    audit_id = str(result.id)
    _store[audit_id] = (result, request)
    return audit_id


def _get_stored(audit_id: str) -> tuple[Any, Any] | None:
    return _store.get(audit_id)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_EXT_TO_LANG: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rb": "ruby",
    ".java": "java",
    ".rs": "rust",
    ".php": "php",
    ".cs": "csharp",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".c": "c",
    ".sh": "shell",
    ".bash": "shell",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".toml": "toml",
    ".tf": "terraform",
    ".kt": "kotlin",
    ".scala": "scala",
    ".swift": "swift",
}

_LANG_TO_EXTS: dict[str, list[str]] = {
    "python": [".py"],
    "javascript": [".js", ".mjs"],
    "typescript": [".ts", ".tsx"],
    "go": [".go"],
    "ruby": [".rb"],
    "java": [".java"],
    "rust": [".rs"],
    "php": [".php"],
    "csharp": [".cs"],
    "cpp": [".cpp", ".cc"],
}


def _detect_language(path: Path) -> str:
    return _EXT_TO_LANG.get(path.suffix.lower(), "unknown")


async def _build_context(
    target: str,
    languages: str = "",
) -> tuple[Any, Any, Any]:
    """Ingest files, parse ASTs, build graph. Returns (ctx, settings, request)."""
    from sentinel.core.context import AuditContext
    from sentinel.graph.builder import GraphBuilder
    from sentinel.parsers.project import ProjectParser
    from sentinel.parsers.treesitter import TreeSitterParser

    settings = get_settings()
    request = AuditRequest(
        target=Path(target).resolve(),
        scope=AuditScope(languages=[lang.strip() for lang in languages.split(",") if lang.strip()]),
        llm_enabled=False,
    )
    ctx = AuditContext(request)

    await ProjectParser(settings).ingest(ctx)

    ts = TreeSitterParser()
    parse_tasks = [
        _parse_one(ts, path, content, ctx)
        for path, content in ctx.file_contents.items()
        if ts.can_parse(Path(path))
    ]
    if parse_tasks:
        await asyncio.gather(*parse_tasks)

    await GraphBuilder().build(ctx)

    return ctx, settings, request


async def _parse_one(ts: Any, path: str, content: str, ctx: Any) -> None:
    try:
        ctx.parsed_files[path] = await ts.parse(Path(path), content)
    except Exception as exc:  # noqa: BLE001
        log.debug("parse_skip", path=path, reason=str(exc))


async def _run_rules_on_ctx(ctx: Any, tag_filter: str = "") -> list[Any]:
    from sentinel.rules.loader import RuleLoader

    loader = RuleLoader()
    loader.load_builtin()

    rules = loader.rules
    if tag_filter:
        rules = [r for r in rules if tag_filter.lower() in r.metadata.tags] or rules

    results = await asyncio.gather(*[rule.match(ctx) for rule in rules], return_exceptions=True)
    findings: list[Any] = []
    for result in results:
        if not isinstance(result, BaseException):
            findings.extend(result)
    return findings


# ---------------------------------------------------------------------------
# TOOL: sentinel_audit
# ---------------------------------------------------------------------------


@mcp.tool()
async def sentinel_audit(
    target: str,
    no_llm: bool = True,
    languages: str = "",
    top_n: int = 20,
) -> str:
    """Run a full deep contextual security audit on a target directory.

    Executes the complete SENTINEL pipeline: file ingestion, AST parsing,
    context graph construction, concurrent rule matching, and optional LLM
    enrichment. Returns a Markdown report sorted by risk score.

    Args:
        target: Absolute or relative path to the directory to audit.
        no_llm: Disable LLM enrichment (faster, no API cost). Default True.
        languages: Comma-separated language filter, e.g. 'python,go'. Empty = all.
        top_n: Max findings in this response (rest retrievable via sentinel_report).
    """
    from sentinel.core.engine import AuditEngine

    settings = get_settings()
    request = AuditRequest(
        target=Path(target).resolve(),
        scope=AuditScope(languages=[lang.strip() for lang in languages.split(",") if lang.strip()]),
        llm_enabled=not no_llm,
    )

    engine = AuditEngine(settings)
    await engine.initialize()
    result = await engine.run(request)

    audit_id = _store_result(result, request)

    top_findings = result.findings[:top_n]
    trimmed = result.model_copy(update={"findings": top_findings})
    report = engine.generate_report(trimmed, "markdown")

    if result.summary.total_findings > top_n:
        report += (
            f"\n\n> **Note:** Showing top {top_n} of "
            f"{result.summary.total_findings} findings. "
            f"Full report: `sentinel_report(audit_id='{audit_id}')`"
        )
    return report


# ---------------------------------------------------------------------------
# TOOL: sentinel_surface
# ---------------------------------------------------------------------------


@mcp.tool()
async def sentinel_surface(target: str, languages: str = "") -> str:
    """Map the attack surface of a codebase without running a full audit.

    Fast operation — ingests files and returns total file/line counts, language
    breakdown, and security-relevant file paths (auth, DB, config, APIs, etc.).

    Args:
        target: Absolute or relative path to the directory to map.
        languages: Comma-separated language filter. Empty = all.
    """
    ctx, _, _ = await _build_context(target, languages)

    lang_counts: dict[str, int] = {}
    for meta in ctx.file_metadata.values():
        lang = meta.get("language") or "unknown"
        lang_counts[lang] = lang_counts.get(lang, 0) + 1

    _SECURITY_KEYWORDS = [
        "auth",
        "login",
        "password",
        "token",
        "secret",
        "key",
        "credential",
        "admin",
        "user",
        "payment",
        "upload",
        "execute",
        "query",
        "eval",
        "config",
        "settings",
        "database",
        "db",
        "sql",
        "shell",
        "subprocess",
        "webhook",
        "api",
        "route",
        "endpoint",
        "middleware",
        "deserializ",
        "serialize",
        "pickle",
        "yaml",
        "jwt",
        "session",
        "cookie",
        "csrf",
        "permission",
        "role",
        "acl",
        "rbac",
        "oauth",
        "saml",
        "signature",
        "encrypt",
        "decrypt",
        "hash",
        "sign",
        "verify",
        "certificate",
        "tls",
    ]

    notable = sorted(
        p for p in ctx.file_contents if any(kw in p.lower() for kw in _SECURITY_KEYWORDS)
    )

    lines = [
        f"# Attack Surface — `{target}`",
        "",
        f"**Files:** {ctx.files_analyzed}  ",
        f"**Lines:** {ctx.lines_analyzed:,}  ",
        "",
        "## Language Breakdown",
        "",
    ]
    for lang, count in sorted(lang_counts.items(), key=lambda x: -x[1]):
        lines.append(f"- `{lang}`: {count} files")

    lines += ["", "## Security-Relevant Files", ""]
    for path in notable[:50]:
        meta = ctx.file_metadata.get(path, {})
        lines.append(f"- `{path}` ({meta.get('language', '?')}, {meta.get('lines', 0)} lines)")
    if not notable:
        lines.append("_No notably named files detected._")

    lines += ["", "## All Files", ""]
    for path in sorted(ctx.file_contents)[:100]:
        meta = ctx.file_metadata.get(path, {})
        lines.append(f"- `{path}` ({meta.get('language', '?')})")
    if ctx.files_analyzed > 100:
        lines.append(f"- _...and {ctx.files_analyzed - 100} more_")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# TOOL: sentinel_trace
# ---------------------------------------------------------------------------


@mcp.tool()
async def sentinel_trace(
    target: str,
    sink_type: str = "all",
    languages: str = "",
) -> str:
    """Trace taint flows from user-controlled sources to sensitive sinks.

    Builds the context graph and runs data-flow analysis to surface paths from
    untrusted inputs to sensitive operations (DB queries, command execution,
    output rendering, secret access).

    Args:
        target: Path to the directory to analyze.
        sink_type: Sink filter — database | output | secret | all (default: all).
        languages: Comma-separated language filter.
    """
    from sentinel.graph.queries import GraphQueries
    from sentinel.models.graph import NodeType

    ctx, _, _ = await _build_context(target, languages)
    backend = ctx.get("graph_backend")

    _SINK_MAP: dict[str, list[NodeType]] = {
        "database": [NodeType.DATABASE],
        "output": [NodeType.OUTPUT],
        "secret": [NodeType.SECRET],
        "all": [NodeType.DATABASE, NodeType.OUTPUT, NodeType.SECRET],
    }
    sink_types = _SINK_MAP.get(
        sink_type.lower(), [NodeType.DATABASE, NodeType.OUTPUT, NodeType.SECRET]
    )

    header = [
        f"# Taint Flow Analysis — `{target}`",
        "",
        f"**Files:** {ctx.files_analyzed}  ",
        f"**Lines:** {ctx.lines_analyzed:,}",
        "",
    ]

    if not backend or backend.node_count() == 0:
        return "\n".join(header) + (
            "_Graph has no nodes. AST-based graph nodes require parseable source "
            "files (Python via tree-sitter). Other languages produce empty graphs "
            "until their parsers are added._"
        )

    q = GraphQueries(backend)
    paths = q.user_input_to_sink_paths(sink_types)
    crossings = q.trust_boundary_crossings()
    tainted = q.tainted_edges()

    lines = header + [
        f"**Graph nodes:** {backend.node_count()}  ",
        f"**Graph edges:** {backend.edge_count()}  ",
        f"**Trust boundary crossings:** {len(crossings)}  ",
        f"**Tainted edges:** {len(tainted)}  ",
        f"**User-input → sink paths:** {len(paths)}",
        "",
    ]

    if crossings:
        lines += ["## Trust Boundary Crossings", ""]
        for src, dst, edge in crossings[:25]:
            lines.append(
                f"- **`{src.label}`** `[{src.trust_level.value}]` → "
                f"**`{dst.label}`** `[{dst.trust_level.value}]` "
                f"via `{edge.type.value}`"
            )
        if len(crossings) > 25:
            lines.append(f"_...and {len(crossings) - 25} more crossings_")
        lines.append("")

    if paths:
        lines += ["## Taint Paths (User Input → Sink)", ""]
        for i, path in enumerate(paths[:15], 1):
            nodes = " → ".join(f"`{n}`" for n in path)
            lines.append(f"{i}. {nodes}")
        if len(paths) > 15:
            lines.append(f"_...and {len(paths) - 15} more paths_")
        lines.append("")

    if tainted:
        lines += ["## Tainted Edges", ""]
        for edge in tainted[:20]:
            lines.append(f"- `{edge.source}` → `{edge.target}` (`{edge.type.value}`)")
        lines.append("")

    if not crossings and not paths and not tainted:
        lines.append(
            "_No taint flows detected. The graph may lack USER_INPUT-typed nodes "
            "or the codebase has clean data-flow boundaries._"
        )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# TOOL: sentinel_attack_graph
# ---------------------------------------------------------------------------


@mcp.tool()
async def sentinel_attack_graph(
    target: str,
    fmt: str = "mermaid",
    languages: str = "",
) -> str:
    """Generate an attack graph visualizing trust boundaries and privilege paths.

    Maps endpoint-to-privileged-operation reachability, trust boundary
    crossings, and DB query exposure. Output renders as a Mermaid flowchart
    (paste into any Mermaid renderer, GitHub markdown, Obsidian, etc.)
    or as plain text.

    Args:
        target: Path to the directory to analyze.
        fmt: Output format — mermaid | text (default: mermaid).
        languages: Comma-separated language filter.
    """
    from sentinel.graph.queries import GraphQueries

    ctx, _, _ = await _build_context(target, languages)
    backend = ctx.get("graph_backend")

    header = [
        f"# Attack Graph — `{target}`",
        "",
        f"**Files:** {ctx.files_analyzed}  ",
        f"**Lines:** {ctx.lines_analyzed:,}",
        "",
    ]

    if not backend or backend.node_count() == 0:
        return "\n".join(header) + (
            "_No graph nodes extracted. Tree-sitter AST parsing currently supports "
            "Python; other languages yield empty graphs until parsers are added._"
        )

    q = GraphQueries(backend)
    crossings = q.trust_boundary_crossings()
    priv_pairs = q.privileged_reachable_from_endpoints()
    db_edges = q.db_query_edges()

    stats = header + [
        f"**Nodes:** {backend.node_count()}  ",
        f"**Edges:** {backend.edge_count()}  ",
        f"**Trust boundary crossings:** {len(crossings)}  ",
        f"**Endpoint → Privileged paths:** {len(priv_pairs)}  ",
        f"**DB query edges:** {len(db_edges)}",
        "",
    ]

    if fmt == "mermaid":
        mermaid: list[str] = ["```mermaid", "flowchart TD"]
        seen: set[str] = set()

        def _safe_id(node_id: str) -> str:
            return re.sub(r"[^a-zA-Z0-9_]", "_", node_id)

        def _emit_node(node: Any) -> None:
            nid = _safe_id(node.id)
            if node.id not in seen:
                label = node.label[:30].replace('"', "'")
                mermaid.append(f'    {nid}["{label}"]')
                seen.add(node.id)

        for src, dst, _ in crossings[:30]:
            _emit_node(src)
            _emit_node(dst)
            mermaid.append(f"    {_safe_id(src.id)} -->|trust crossing| {_safe_id(dst.id)}")

        for ep_id, priv_id in priv_pairs[:20]:
            ep = backend.get_node(ep_id)
            priv = backend.get_node(priv_id)
            if ep:
                _emit_node(ep)
            if priv:
                _emit_node(priv)
            if ep and priv:
                mermaid.append(f"    {_safe_id(ep_id)} -.->|reachable| {_safe_id(priv_id)}")

        if len(mermaid) <= 2:
            mermaid.append('    A["No inter-trust edges detected"]')

        mermaid += [
            "    classDef untrusted fill:#ff6b6b,stroke:#c92a2a,color:#fff",
            "    classDef trusted fill:#51cf66,stroke:#2f9e44,color:#fff",
            "    classDef privileged fill:#f59f00,stroke:#e67700,color:#fff",
            "```",
        ]
        return "\n".join(stats + mermaid)

    # Plain text
    text: list[str] = list(stats)
    if crossings:
        text += ["## Trust Boundary Crossings", ""]
        for src, dst, edge in crossings:
            text.append(
                f"  [{src.trust_level.value.upper()}] {src.label} "
                f"--({edge.type.value})--> "
                f"[{dst.trust_level.value.upper()}] {dst.label}"
            )
        text.append("")
    if priv_pairs:
        text += ["## Endpoint → Privileged Paths", ""]
        for ep_id, priv_id in priv_pairs:
            ep = backend.get_node(ep_id)
            priv = backend.get_node(priv_id)
            text.append(
                f"  ENDPOINT:{ep.label if ep else ep_id} "
                f"→ PRIVILEGED:{priv.label if priv else priv_id}"
            )
        text.append("")

    return "\n".join(text)


# ---------------------------------------------------------------------------
# TOOL: sentinel_logic
# ---------------------------------------------------------------------------

_LOGIC_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    (
        "Potential IDOR: user_id compared with request param",
        re.compile(r"user[._]?id\s*==\s*request\.", re.I),
        "Verify resource ownership server-side independent of request data.",
    ),
    (
        "Role/privilege sourced directly from request",
        re.compile(r"(role|is_admin|is_staff)\s*=\s*request\.(GET|POST|data|form|json)", re.I),
        "Never trust client-supplied role or privilege values.",
    ),
    (
        "Object retrieved without visible ownership check",
        re.compile(r"\.filter\(.*\)\.(first|get)\(\)", re.I),
        "Add owner-scoped queryset filter: .filter(user=request.user, ...)",
    ),
    (
        "Negated auth check — verify logic is correct",
        re.compile(r"if\s+not\s+(is_authenticated|authenticate\(|login_required)", re.I),
        "Confirm the negation is intentional and does not skip auth on error.",
    ),
    (
        "Access control from request body field",
        re.compile(r"(permission|access|scope)\s*=\s*request\.(data|json|POST|GET)\[", re.I),
        "Access control decisions must come from server-side session/token, not request payload.",
    ),
    (
        "eval() with potentially controlled input",
        re.compile(r"eval\s*\(\s*(request|input|data|param|query|user)", re.I),
        "Remove eval() — use safe parsing logic instead.",
    ),
    (
        "Unvalidated redirect target from request",
        re.compile(r"redirect\s*\(\s*(request\.|f['\"])", re.I),
        "Validate redirect targets against an allowlist to prevent open redirect.",
    ),
]


@mcp.tool()
async def sentinel_logic(
    target: str,
    no_llm: bool = True,
    languages: str = "",
) -> str:
    """Analyze business logic flaws and authorization weaknesses.

    Focuses on: broken access control, IDOR, privilege injection, missing
    ownership checks, auth bypass patterns, and unvalidated redirects.
    Combines existing auth rules with logic-specific pattern matching.

    Args:
        target: Path to the directory to analyze.
        no_llm: Disable LLM enrichment. Default True.
        languages: Comma-separated language filter.
    """
    from sentinel.core.context import AuditContext
    from sentinel.core.engine import AuditEngine
    from sentinel.models.audit import AuditResult, AuditStatus, AuditSummary
    from sentinel.models.finding import Confidence, Finding, Location, Severity
    from sentinel.parsers.project import ProjectParser

    settings = get_settings()
    request = AuditRequest(
        target=Path(target).resolve(),
        scope=AuditScope(languages=[lang.strip() for lang in languages.split(",") if lang.strip()]),
        llm_enabled=not no_llm,
    )
    ctx = AuditContext(request)
    await ProjectParser(settings).ingest(ctx)

    # Run existing rules (captures auth/credential findings)
    rule_findings = await _run_rules_on_ctx(ctx)
    for f in rule_findings:
        ctx.add_finding(f)

    # Logic-specific pattern scan
    for rel_path, content in ctx.file_contents.items():
        file_lines = content.splitlines()
        for line_num, line in enumerate(file_lines, 1):
            for description, pattern, mitigation in _LOGIC_PATTERNS:
                if pattern.search(line):
                    ctx.add_finding(
                        Finding(
                            title=f"Logic Flaw Pattern: {description}",
                            severity=Severity.MEDIUM,
                            confidence=Confidence.LOW,
                            affected_components=[rel_path],
                            locations=[Location(file=rel_path, line_start=line_num)],
                            attack_surface="Application logic / authorization layer",
                            exploitation_requirements="Understanding of application auth flow",
                            technical_explanation=description,
                            root_cause="Potential insufficient or bypassable authorization check",
                            attack_scenario=(
                                "Attacker manipulates request parameters or exploits "
                                "logic flaws to access unauthorized resources or escalate privileges."
                            ),
                            potential_impact="Unauthorized data access or privilege escalation",
                            blast_radius="Depends on exposed resource sensitivity",
                            detection_difficulty="medium",
                            business_risk="Unauthorized access to sensitive data or admin functions",
                            mitigation_strategy=mitigation,
                            secure_refactor_recommendations=[
                                "Always verify resource ownership server-side",
                                "Never trust client-supplied role or privilege values",
                                "Use framework-level authorization decorators consistently",
                                "Apply OWASP ASVS Level 2 access control requirements",
                            ],
                            analyzer="sentinel_logic",
                            rule_id="LOGIC-PATTERN",
                            tags=["logic", "auth", "idor", "access-control"],
                        )
                    )

    findings = sorted(ctx.findings, key=lambda f: f.risk_score, reverse=True)
    dummy = AuditResult(
        request_id=request.id,
        status=AuditStatus.COMPLETED,
        findings=findings,
        summary=AuditSummary.from_findings(findings, 0.0, ctx.files_analyzed, ctx.lines_analyzed),
    )
    _store_result(dummy, request)

    if not findings:
        return (
            f"# Business Logic Analysis — `{target}`\n\n"
            f"No logic flaws detected across {ctx.files_analyzed} files. "
            "Enable LLM enrichment (`no_llm=False`) for deeper semantic analysis."
        )

    engine = AuditEngine(settings)
    await engine.initialize()
    return engine.generate_report(dummy, "markdown")


# ---------------------------------------------------------------------------
# TOOL: sentinel_review
# ---------------------------------------------------------------------------


@mcp.tool()
async def sentinel_review(
    file_path: str,
    focus: str = "",
    no_llm: bool = True,
) -> str:
    """Deep security review of a single file.

    Runs all SENTINEL detection rules against one file and returns a detailed
    report. Faster and more focused than a full directory audit.

    Args:
        file_path: Absolute or relative path to the file to review.
        focus: Optional tag filter — injection | auth | secrets | tls | logic.
        no_llm: Disable LLM enrichment. Default True.
    """
    from sentinel.core.context import AuditContext
    from sentinel.core.engine import AuditEngine
    from sentinel.models.audit import AuditResult, AuditStatus, AuditSummary

    resolved = Path(file_path).resolve()
    if not resolved.exists():
        return f"File not found: `{file_path}`"
    if not resolved.is_file():
        return f"`{file_path}` is a directory. Use `sentinel_audit` for directories."

    settings = get_settings()
    request = AuditRequest(
        target=resolved.parent,
        scope=AuditScope(),
        llm_enabled=not no_llm,
    )
    ctx = AuditContext(request)

    rel_path = resolved.name
    content = resolved.read_text(encoding="utf-8", errors="replace")
    ctx.file_contents[rel_path] = content
    ctx.file_metadata[rel_path] = {
        "language": _detect_language(resolved),
        "lines": content.count("\n") + 1,
        "size_bytes": len(content.encode()),
    }

    findings = await _run_rules_on_ctx(ctx, tag_filter=focus)
    for f in findings:
        ctx.add_finding(f)

    sorted_findings = sorted(ctx.findings, key=lambda f: f.risk_score, reverse=True)
    dummy = AuditResult(
        request_id=request.id,
        status=AuditStatus.COMPLETED,
        findings=sorted_findings,
        summary=AuditSummary.from_findings(sorted_findings, 0.0, 1, content.count("\n") + 1),
    )
    _store_result(dummy, request)

    if not sorted_findings:
        from sentinel.rules.loader import RuleLoader

        loader = RuleLoader()
        loader.load_builtin()
        rule_count = len(loader.rules)
        return (
            f"# File Review — `{resolved.name}`\n\n"
            f"No security issues detected.  \n"
            f"**Rules applied:** {rule_count}  \n"
            f"**Lines:** {content.count(chr(10)) + 1}"
        )

    engine = AuditEngine(settings)
    await engine.initialize()
    return engine.generate_report(dummy, "markdown")


# ---------------------------------------------------------------------------
# TOOL: sentinel_verify
# ---------------------------------------------------------------------------


@mcp.tool()
async def sentinel_verify(
    audit_id: str,
    finding_index: int = 0,
) -> str:
    """Verify whether a specific finding is a true positive.

    Re-reads the source file at the reported location and checks if the
    vulnerable pattern still exists. Useful for CI/CD gating and triage.

    Args:
        audit_id: UUID from a previous sentinel_audit or sentinel_hunt run.
        finding_index: Zero-based index of the finding to verify (0 = highest risk).
    """
    entry = _get_stored(audit_id)
    if not entry:
        return f"Audit `{audit_id}` not found. Re-run the audit first."

    result, request = entry
    if not result.findings:
        return f"Audit `{audit_id}` has no findings."
    if finding_index >= len(result.findings):
        return (
            f"Index {finding_index} out of range. "
            f"Audit has {len(result.findings)} findings (0–{len(result.findings) - 1})."
        )

    finding = result.findings[finding_index]
    loc = finding.locations[0] if finding.locations else None

    lines = [
        "# Finding Verification",
        "",
        f"**Audit:** `{audit_id}`  ",
        f"**Finding #{finding_index}:** {finding.title}  ",
        f"**Severity:** `{finding.severity.value.upper()}`  ",
        f"**Confidence:** `{finding.confidence.value}`  ",
        f"**Rule:** `{finding.rule_id or 'N/A'}`",
        "",
    ]

    if not loc:
        lines.append("_No location information available for this finding._")
        return "\n".join(lines)

    # Resolve file path: try absolute, then relative to audit target, then CWD
    candidates: list[Path] = [Path(loc.file)]
    if request and hasattr(request, "target"):
        candidates.append(Path(request.target) / loc.file)
    candidates.append(Path.cwd() / loc.file)

    content: str | None = None
    used_path: Path | None = None
    for candidate in candidates:
        try:
            if candidate.exists():
                content = candidate.read_text(encoding="utf-8", errors="replace")
                used_path = candidate
                break
        except OSError:
            pass

    if content is None:
        lines += [
            f"**Location:** `{loc.file}`:{loc.line_start}  ",
            "",
            "> **Unverifiable** — source file not accessible from any resolved path.",
            "> Re-run the audit with an absolute target path to enable verification.",
        ]
        return "\n".join(lines)

    file_lines = content.splitlines()
    line_idx = (loc.line_start or 1) - 1
    start = max(0, line_idx - 3)
    end = min(len(file_lines), line_idx + 4)

    lines += [
        f"**Location:** `{used_path}`:{loc.line_start}",
        "",
        "## Source Context",
        "",
        "```",
    ]
    for i, code_line in enumerate(file_lines[start:end], start + 1):
        marker = " >>>" if i == (loc.line_start or 1) else "    "
        lines.append(f"{i:4d}{marker} {code_line}")
    lines += ["```", ""]

    target_line = file_lines[line_idx] if line_idx < len(file_lines) else ""
    _VULN_TOKENS = [
        'execute(f"',
        "execute(f'",
        "execute(%",
        ".execute(",
        "shell=True",
        "os.system(",
        "subprocess.",
        'password = "',
        "password = '",
        'secret = "',
        "secret = '",
        "verify=False",
        "ssl_verify=False",
        "eval(",
        "exec(",
    ]
    matched = [tok for tok in _VULN_TOKENS if tok in target_line]

    if matched:
        lines += [
            "## Verification Result",
            "",
            "**Status:** TRUE POSITIVE — pattern still present  ",
            f"**Matched:** {', '.join(f'`{m}`' for m in matched)}",
            "",
            f"**Mitigation:** {finding.mitigation_strategy}",
        ]
    else:
        lines += [
            "## Verification Result",
            "",
            "**Status:** INCONCLUSIVE — original pattern not found at this line.  ",
            "The finding may be a false positive or the code changed since the audit.  ",
            "Manual review recommended.",
        ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# TOOL: sentinel_diff
# ---------------------------------------------------------------------------


@mcp.tool()
async def sentinel_diff(
    target: str,
    base: str = "HEAD",
    head: str = "",
    languages: str = "",
) -> str:
    """Audit the security impact of code changes in a git diff.

    Runs SENTINEL rules only against files changed between two git refs.
    Ideal for PR security gates, commit reviews, and change-impact analysis.

    Args:
        target: Git repository root (absolute or relative path).
        base: Base ref (default: HEAD). Use 'main' or a commit SHA.
        head: Head ref (default: working tree / staged changes).
        languages: Comma-separated language filter.
    """
    from sentinel.core.context import AuditContext
    from sentinel.core.engine import AuditEngine
    from sentinel.models.audit import AuditResult, AuditStatus, AuditSummary

    settings = get_settings()
    repo_root = Path(target).resolve()

    # Discover changed files via git
    try:
        cmd = ["git", "-C", str(repo_root), "diff", "--name-only", base]
        if head:
            cmd.append(head)
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if proc.returncode != 0:
            return (
                f"# Diff Audit — `{target}`\n\n"
                f"**git diff failed:** `{proc.stderr.strip()}`  \n"
                "Ensure the target is a git repository and the refs are valid."
            )
        changed_files = [f.strip() for f in proc.stdout.strip().splitlines() if f.strip()]
    except FileNotFoundError:
        return "# Diff Audit\n\n`git` not found on PATH. Install git to use sentinel_diff."
    except subprocess.TimeoutExpired:
        return "# Diff Audit\n\n`git diff` timed out (>30s). Repository may be too large."

    head_label = head or "working tree"
    if not changed_files:
        return (
            f"# Diff Audit — `{target}`\n\n"
            f"No files changed between `{base}` and `{head_label}`."
        )

    # Optional language filter
    lang_filter = [lang.strip().lower() for lang in languages.split(",") if lang.strip()]
    if lang_filter:
        allowed_exts = {ext for lang in lang_filter for ext in _LANG_TO_EXTS.get(lang, [])}
        if allowed_exts:
            changed_files = [f for f in changed_files if Path(f).suffix.lower() in allowed_exts]

    request = AuditRequest(
        target=repo_root,
        scope=AuditScope(),
        llm_enabled=False,
    )
    ctx = AuditContext(request)

    ingested = 0
    for rel_path in changed_files:
        abs_path = repo_root / rel_path
        if abs_path.is_file():
            try:
                content = abs_path.read_text(encoding="utf-8", errors="replace")
                if len(content.encode()) / 1024 <= settings.max_file_size_kb:
                    ctx.file_contents[rel_path] = content
                    ctx.file_metadata[rel_path] = {
                        "language": _detect_language(abs_path),
                        "lines": content.count("\n") + 1,
                        "size_bytes": len(content.encode()),
                    }
                    ingested += 1
            except OSError:
                pass

    header = [
        f"# Diff Security Audit — `{target}`",
        "",
        f"**Refs:** `{base}` → `{head_label}`  ",
        f"**Changed files:** {len(changed_files)}  ",
        f"**Audited:** {ingested} files  ",
        "",
    ]

    if not ctx.file_contents:
        return "\n".join(header) + "No readable files found in the diff."

    findings = await _run_rules_on_ctx(ctx)
    findings.sort(key=lambda f: f.risk_score, reverse=True)

    dummy = AuditResult(
        request_id=request.id,
        status=AuditStatus.COMPLETED,
        findings=findings,
        summary=AuditSummary.from_findings(findings, 0.0, ingested, ctx.lines_analyzed),
    )
    _store_result(dummy, request)

    if not findings:
        return "\n".join(header) + "No security issues found in changed files."

    engine = AuditEngine(settings)
    await engine.initialize()
    report = engine.generate_report(dummy, "markdown")
    return "\n".join(header) + report


# ---------------------------------------------------------------------------
# TOOL: sentinel_harden
# ---------------------------------------------------------------------------

_HARDEN_CHECKS: list[tuple[str, str, re.Pattern[str], str]] = [
    (
        "Cryptography",
        "MD5 usage detected",
        re.compile(r"hashlib\.md5|MD5\(", re.I),
        "Replace MD5 with SHA-256 or bcrypt/argon2 for passwords",
    ),
    (
        "Cryptography",
        "SHA-1 usage detected",
        re.compile(r"hashlib\.sha1|SHA1\(", re.I),
        "Replace SHA-1 with SHA-256 or stronger",
    ),
    (
        "Secrets Management",
        "Potential hardcoded secret",
        re.compile(r'(secret|password|api_key|token)\s*=\s*["\'][^"\']{8,}["\']', re.I),
        "Move secrets to environment variables or a secrets manager (e.g., Vault, AWS Secrets Manager)",
    ),
    (
        "Debug / Information Disclosure",
        "Debug mode potentially enabled",
        re.compile(r"debug\s*=\s*True", re.I),
        "Set DEBUG=False in production; use environment-specific config",
    ),
    (
        "Debug / Information Disclosure",
        "Stack trace exposed to caller",
        re.compile(r"traceback\.print_exc\(\)|print_exception", re.I),
        "Log stack traces server-side; return generic error messages to clients",
    ),
    (
        "TLS / Transport",
        "TLS certificate verification disabled",
        re.compile(r"verify\s*=\s*False", re.I),
        "Enable TLS verification: verify=True or provide CA bundle path",
    ),
    (
        "TLS / Transport",
        "Non-HTTPS URL hardcoded for external service",
        re.compile(r"http://(?!localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\])", re.I),
        "Use HTTPS for all external service URLs",
    ),
    (
        "Input Validation",
        "eval() with potentially dynamic input",
        re.compile(r"\beval\s*\(", re.I),
        "Remove eval(); use explicit parsing or ast.literal_eval() for safe cases",
    ),
    (
        "Input Validation",
        "exec() usage detected",
        re.compile(r"\bexec\s*\(", re.I),
        "Avoid exec() with any user-influenced input",
    ),
    (
        "Session / Auth",
        "Cryptographically weak random for security context",
        re.compile(r"\brandom\.random\(\)|\brandom\.randint\(", re.I),
        "Use secrets.token_hex() or os.urandom() for tokens, nonces, and session IDs",
    ),
    (
        "Session / Auth",
        "Short or inline SECRET_KEY",
        re.compile(r"SECRET_KEY\s*=\s*['\"][^'\"]{1,30}['\"]", re.I),
        "Generate SECRET_KEY from os.urandom(32) and load it from environment",
    ),
    (
        "Serialization",
        "Pickle deserialization detected",
        re.compile(r"pickle\.loads?\(", re.I),
        "Avoid pickle for untrusted data; use JSON, protobuf, or msgpack instead",
    ),
    (
        "Serialization",
        "YAML unsafe load",
        re.compile(r"yaml\.load\s*\((?!.*Loader=yaml\.SafeLoader)", re.I),
        "Replace yaml.load() with yaml.safe_load()",
    ),
    (
        "File Operations",
        "File opened with path from request/user input",
        re.compile(r"open\s*\(\s*(request\.|f['\"])", re.I),
        "Validate and sandbox file paths; use pathlib.Path.resolve() + allowlist",
    ),
    (
        "Command Execution",
        "Shell=True in subprocess call",
        re.compile(r"shell\s*=\s*True", re.I),
        "Use shell=False and pass args as a list to prevent shell injection",
    ),
    (
        "Dependency / Supply Chain",
        "Unpinned dependency reference",
        re.compile(r"pip install\s+\w+(?![>=<!\s])", re.I),
        "Pin all dependencies with exact versions and use a lockfile (uv.lock, requirements.txt)",
    ),
]


@mcp.tool()
async def sentinel_harden(target: str, languages: str = "") -> str:
    """Generate a security hardening checklist for a codebase.

    Scans for missing controls, insecure defaults, and hardening opportunities.
    Output is an actionable checklist grouped by category.

    Args:
        target: Path to the directory to analyze.
        languages: Comma-separated language filter.
    """
    ctx, _, _ = await _build_context(target, languages)

    # category -> list of (issue, file, context_snippet)
    findings_by_cat: dict[str, list[tuple[str, str, str]]] = {}

    for rel_path, content in ctx.file_contents.items():
        file_lines = content.splitlines()
        for category, issue, pattern, _ in _HARDEN_CHECKS:
            for line_num, line in enumerate(file_lines, 1):
                if pattern.search(line):
                    findings_by_cat.setdefault(category, []).append(
                        (issue, rel_path, f":{line_num}: `{line.strip()[:80]}`")
                    )
                    break  # one match per file per check

    # Build recommendation map
    rec_map = {issue: rec for _, issue, _, rec in _HARDEN_CHECKS}

    output = [
        f"# Security Hardening Checklist — `{target}`",
        "",
        f"**Files scanned:** {ctx.files_analyzed}  ",
        f"**Issues found:** {sum(len(v) for v in findings_by_cat.values())}",
        "",
    ]

    if not findings_by_cat:
        output += [
            "_No common hardening issues detected._",
            "_For deeper analysis, run `sentinel_audit` with the full rule set._",
        ]
        return "\n".join(output)

    for category in sorted(findings_by_cat):
        output += [f"## {category}", ""]
        seen_issues: set[str] = set()
        for issue, path, context in findings_by_cat[category]:
            if issue not in seen_issues:
                rec = rec_map.get(issue, "")
                output.append(f"- [ ] **{issue}**")
                if rec:
                    output.append(f"  > {rec}")
                seen_issues.add(issue)
            output.append(f"  - `{path}`{context}")
        output.append("")

    output += [
        "## General Recommendations",
        "",
        "- [ ] Run `sentinel_audit` for full vulnerability scan",
        "- [ ] Enable `sentinel_diff` on every PR for change-level security gating",
        "- [ ] Run dependency audit: `pip-audit` / `uv run safety check`",
        "- [ ] Review OWASP Top 10 and ASVS Level 2 checklist",
        "- [ ] Implement structured security logging and alerting",
        "- [ ] Set up SBOM generation for supply chain visibility",
    ]

    return "\n".join(output)


# ---------------------------------------------------------------------------
# TOOL: sentinel_exploit_chain
# ---------------------------------------------------------------------------


@mcp.tool()
async def sentinel_exploit_chain(
    audit_id: str,
    finding_index: int = 0,
    target: str = "",
) -> str:
    """Trace and expand the full exploitation chain for a specific finding.

    Retrieves a finding from a past audit, narrates the exploitation path,
    and optionally uses the context graph to surface privilege escalation,
    lateral movement, and data exfiltration opportunities.

    Args:
        audit_id: UUID from a previous sentinel_audit run.
        finding_index: Finding to expand (0 = highest risk, default).
        target: Optional — rebuild graph for richer path analysis.
    """
    entry = _get_stored(audit_id)
    if not entry:
        return f"Audit `{audit_id}` not found. Re-run sentinel_audit first."

    result, _ = entry
    if not result.findings:
        return f"Audit `{audit_id}` has no findings."
    if finding_index >= len(result.findings):
        return f"Index {finding_index} out of range ({len(result.findings)} findings)."

    finding = result.findings[finding_index]
    loc = finding.locations[0] if finding.locations else None

    lines = [
        "# Exploit Chain Analysis",
        "",
        f"**Finding:** {finding.title}  ",
        f"**Severity:** `{finding.severity.value.upper()}`  ",
        f"**Confidence:** `{finding.confidence.value}`  ",
        f"**Rule:** `{finding.rule_id or 'manual'}`",
        "",
        "## Vulnerability Summary",
        "",
        f"**Root Cause:** {finding.root_cause}  ",
        f"**Attack Surface:** {finding.attack_surface}  ",
        f"**Exploitation Requirements:** {finding.exploitation_requirements}  ",
        f"**Technical:** {finding.technical_explanation}",
        "",
        "## Exploit Chain",
        "",
    ]

    if finding.exploit_chain:
        for step in finding.exploit_chain:
            lines += [
                f"**Step {step.step} — {step.component}**",
                f"> {step.action}",
            ]
            if step.notes:
                lines.append(f"> _{step.notes}_")
            lines.append("")
    else:
        loc_str = f"`{loc.file}:{loc.line_start}`" if loc else "vulnerable code path"
        lines += [
            "**Step 1 — Reconnaissance**",
            f"> Identify the vulnerability at {loc_str}",
            "",
            "**Step 2 — Trigger**",
            f"> {finding.attack_scenario}",
            "",
            "**Step 3 — Impact**",
            f"> {finding.potential_impact}",
            "",
            "**Step 4 — Blast Radius**",
            f"> {finding.blast_radius}",
            "",
        ]

    # Extend with live graph analysis when target is provided
    if target:
        try:
            ctx, _, _ = await _build_context(target)
            backend = ctx.get("graph_backend")
            if backend and backend.node_count() > 0:
                from sentinel.graph.queries import GraphQueries

                q = GraphQueries(backend)
                crossings = q.trust_boundary_crossings()
                priv_pairs = q.privileged_reachable_from_endpoints()

                if crossings or priv_pairs:
                    lines += ["## Graph-Derived Attack Extensions", ""]
                    if crossings:
                        lines.append("**Available trust boundary pivots:**")
                        for src, dst, _ in crossings[:6]:
                            lines.append(
                                f"- `{src.label}` `[{src.trust_level.value}]` → "
                                f"`{dst.label}` `[{dst.trust_level.value}]`"
                            )
                        lines.append("")
                    if priv_pairs:
                        lines.append("**Privileged operations reachable from endpoints:**")
                        for ep_id, priv_id in priv_pairs[:6]:
                            ep = backend.get_node(ep_id)
                            priv = backend.get_node(priv_id)
                            lines.append(
                                f"- `{ep.label if ep else ep_id}` → "
                                f"`{priv.label if priv else priv_id}`"
                            )
                        lines.append("")
        except Exception as exc:
            lines += [f"_Graph analysis failed: {exc}_", ""]

    lines += [
        "## Impact & Detection",
        "",
        f"**Blast Radius:** {finding.blast_radius}  ",
        f"**Detection Difficulty:** {finding.detection_difficulty}  ",
        f"**Business Risk:** {finding.business_risk}",
        "",
        "## Remediation",
        "",
        f"**Strategy:** {finding.mitigation_strategy}",
        "",
    ]
    for rec in finding.secure_refactor_recommendations:
        lines.append(f"- {rec}")
    if finding.safer_architectural_alternative:
        lines += ["", f"**Architectural Alternative:** {finding.safer_architectural_alternative}"]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# TOOL: sentinel_hunt
# ---------------------------------------------------------------------------


@mcp.tool()
async def sentinel_hunt(target: str, category: str) -> str:
    """Run a focused hunt for a specific vulnerability category.

    Faster than a full audit — runs only rules matching the given category tag.
    Use sentinel_rules to discover available category tags.

    Args:
        target: Path to the directory to scan.
        category: Rule tag to filter on, e.g. injection | auth | secrets | tls | sql | command.
    """
    from sentinel.core.context import AuditContext
    from sentinel.core.engine import AuditEngine
    from sentinel.models.audit import AuditResult, AuditStatus, AuditSummary
    from sentinel.parsers.project import ProjectParser
    from sentinel.rules.loader import RuleLoader

    settings = get_settings()
    request = AuditRequest(
        target=Path(target).resolve(),
        scope=AuditScope(),
        llm_enabled=False,
    )
    ctx = AuditContext(request)
    await ProjectParser(settings).ingest(ctx)

    loader = RuleLoader()
    loader.load_builtin()

    matching = [r for r in loader.rules if category.lower() in r.metadata.tags]
    if not matching:
        available = sorted({tag for r in loader.rules for tag in r.metadata.tags})
        return (
            f"No rules for category `{category}`.  \n"
            f"Available tags: {', '.join(f'`{t}`' for t in available)}"
        )

    results = await asyncio.gather(*[rule.match(ctx) for rule in matching], return_exceptions=True)
    findings: list[Any] = []
    for result in results:
        if not isinstance(result, BaseException):
            findings.extend(result)
    findings.sort(key=lambda f: f.risk_score, reverse=True)

    if not findings:
        return (
            f"No `{category}` findings in `{target}`.  \n"
            f"{ctx.files_analyzed} files scanned with {len(matching)} rules."
        )

    dummy = AuditResult(
        request_id=request.id,
        status=AuditStatus.COMPLETED,
        findings=findings,
        summary=AuditSummary.from_findings(findings, 0.0, ctx.files_analyzed, ctx.lines_analyzed),
    )
    _store_result(dummy, request)

    engine = AuditEngine(settings)
    await engine.initialize()
    return engine.generate_report(dummy, "markdown")


# ---------------------------------------------------------------------------
# TOOL: sentinel_rules
# ---------------------------------------------------------------------------


@mcp.tool()
async def sentinel_rules() -> str:
    """List all registered SENTINEL detection rules with full metadata."""
    from sentinel.rules.loader import RuleLoader

    loader = RuleLoader()
    loader.load_builtin()

    lines = ["# SENTINEL Detection Rules", ""]
    for rule in loader.rules:
        m = rule.metadata
        lines += [
            f"## {m.id} — {m.title}",
            f"- **Severity:** `{m.severity.upper()}`",
            f"- **Confidence:** `{m.confidence}`",
            f"- **Languages:** {', '.join(m.languages) or 'all'}",
            f"- **CWE:** {', '.join(m.cwe_ids) or '—'}",
            f"- **Tags:** {', '.join(m.tags) or '—'}",
            f"- {m.description}",
            "",
        ]
    lines.append(f"_Total: {len(loader.rules)} rules_")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# TOOL: sentinel_report
# ---------------------------------------------------------------------------


@mcp.tool()
async def sentinel_report(audit_id: str, fmt: str = "markdown") -> str:
    """Retrieve the full report from a previous audit in any supported format.

    Args:
        audit_id: UUID from a previous sentinel_audit, sentinel_hunt, or sentinel_diff run.
        fmt: Output format — markdown | json | sarif (default: markdown).
    """
    entry = _get_stored(audit_id)
    if not entry:
        return (
            f"Audit `{audit_id}` not found in this session. "
            "Re-run the audit to generate a fresh result."
        )

    result, _ = entry
    from sentinel.core.engine import AuditEngine

    settings = get_settings()
    engine = AuditEngine(settings)
    await engine.initialize()
    return engine.generate_report(result, fmt)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def run() -> None:
    """Start the SENTINEL MCP server. Used by the sentinel-mcp entry-point script."""
    log.info("sentinel_mcp_starting")
    mcp.run()


if __name__ == "__main__":
    run()
