from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from sentinel.config import get_settings
from sentinel.logging import configure_logging
from sentinel.models.audit import AuditRequest, AuditScope

app = typer.Typer(
    name="sentinel",
    help="SENTINEL — AI-powered contextual security auditing platform",
    add_completion=False,
    no_args_is_help=True,
)
console = Console()


@app.command("audit")
def audit(
    target: Path = typer.Argument(..., help="Target directory to audit"),
    fmt: str = typer.Option("markdown", "--format", "-f", help="Output format: json|markdown|sarif"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Write report to file"),
    no_llm: bool = typer.Option(False, "--no-llm", help="Disable LLM enrichment stage"),
    languages: Optional[str] = typer.Option(
        None, "--languages", "-l", help="Comma-separated language filter (e.g. python,go)"
    ),
) -> None:
    """Deep contextual security audit of a codebase."""
    if not target.exists():
        console.print(f"[red]Target not found:[/red] {target}")
        raise typer.Exit(1)

    settings = get_settings()
    configure_logging(settings.log_level)

    request = AuditRequest(
        target=target.resolve(),
        scope=AuditScope(languages=languages.split(",") if languages else []),
        llm_enabled=not no_llm,
    )

    console.print(
        Panel.fit(
            f"[bold cyan]SENTINEL[/bold cyan] auditing [yellow]{target.resolve()}[/yellow]",
            border_style="cyan",
        )
    )

    result, engine = asyncio.run(_do_audit(settings, request))
    report = engine.generate_report(result, fmt)

    if output:
        output.write_text(report, encoding="utf-8")
        console.print(f"[green]Report written to {output}[/green]")
    else:
        console.print(report)

    _print_summary(result)
    raise typer.Exit(0 if not result.errors else 1)


@app.command("serve")
def serve(
    host: str = typer.Option("0.0.0.0", "--host"),
    port: int = typer.Option(8000, "--port"),
    reload: bool = typer.Option(False, "--reload"),
) -> None:
    """Start the SENTINEL REST API server."""
    import uvicorn

    uvicorn.run("sentinel.api.main:app", host=host, port=port, reload=reload)


@app.command("init")
def init(
    target: Path = typer.Argument(Path("."), help="Target project directory (default: current dir)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print actions without writing files"),
    force: bool = typer.Option(False, "--force", help="Overwrite existing rule files"),
) -> None:
    """Drop SENTINEL agent rule files into any project directory.

    Writes editor-specific rule files so agents in that project know
    SENTINEL MCP tools are available. Safe to re-run (idempotent).
    """
    if not target.exists():
        console.print(f"[red]Directory not found:[/red] {target}")
        raise typer.Exit(1)

    target = target.resolve()

    _SENTINEL_TAG = "<!-- sentinel-init -->"

    _CURSOR_RULE = """\
---
description: SENTINEL security auditing MCP tools
globs: []
alwaysApply: false
---

# SENTINEL Security Auditing

Use SENTINEL MCP tools for security analysis. Invoke when the user asks about security, vulnerabilities, or code auditing.

## Tools
- `sentinel_audit(target)` — full codebase audit
- `sentinel_surface(target)` — attack surface map
- `sentinel_trace(audit_id)` — taint flow (user input → sinks)
- `sentinel_attack_graph(audit_id)` — trust boundary / privilege escalation graph
- `sentinel_logic(audit_id)` — IDOR, BAC, business logic flaws
- `sentinel_review(file_path)` — single file security review
- `sentinel_verify(audit_id, finding_id)` — confirm or dismiss a finding
- `sentinel_diff(repo_path, base)` — git diff security audit
- `sentinel_harden(target)` — hardening checklist
- `sentinel_exploit_chain(audit_id, finding_id)` — exploitation chain
- `sentinel_hunt(target, tags?)` — tag-focused scan
- `sentinel_rules()` — list detection rules
- `sentinel_report(audit_id, format?)` — get report (markdown/json/sarif)
"""

    _WINDSURF_RULE = """\
---
trigger: manual
description: SENTINEL security auditing MCP tools
---

# SENTINEL Security Auditing

Use SENTINEL MCP tools for security analysis.

## Tools
- `sentinel_audit(target)` — full codebase audit
- `sentinel_surface(target)` — attack surface map
- `sentinel_trace(audit_id)` — taint flow analysis
- `sentinel_attack_graph(audit_id)` — trust boundary graph
- `sentinel_logic(audit_id)` — IDOR/BAC/logic flaws
- `sentinel_review(file_path)` — single file review
- `sentinel_diff(repo_path, base)` — git diff audit
- `sentinel_harden(target)` — hardening checklist
- `sentinel_exploit_chain(audit_id, finding_id)` — exploitation chain
- `sentinel_report(audit_id, format?)` — export (markdown/json/sarif)
"""

    _CLINE_RULE = """\
# SENTINEL Security Auditing

SENTINEL is available via MCP. Use these tools for security analysis instead of manually reviewing code.

## Tools
- `sentinel_audit(target)` — full security audit
- `sentinel_surface(target)` — attack surface analysis
- `sentinel_trace(audit_id)` — taint flow
- `sentinel_attack_graph(audit_id)` — privilege escalation graph
- `sentinel_logic(audit_id)` — IDOR/BAC detection
- `sentinel_review(file_path)` — single file review
- `sentinel_diff(repo_path, base)` — PR security audit
- `sentinel_harden(target)` — hardening checklist
- `sentinel_exploit_chain(audit_id, finding_id)` — exploit chain
- `sentinel_report(audit_id, format?)` — markdown/json/sarif
"""

    _AGENTS_SNIPPET = f"""\

{_SENTINEL_TAG}
## SENTINEL Security Auditing

SENTINEL MCP tools are available for security analysis in this project.

- `sentinel_audit(target)` — full audit
- `sentinel_surface(target)` — attack surface
- `sentinel_trace(audit_id)` — taint flow
- `sentinel_review(file_path)` — single file review
- `sentinel_diff(repo_path, base)` — PR security audit
- `sentinel_report(audit_id, format?)` — markdown/json/sarif
"""

    _COPILOT_SNIPPET = f"""\

{_SENTINEL_TAG}
## SENTINEL Security Auditing

Use SENTINEL MCP tools when asked about security: `sentinel_audit`, `sentinel_surface`,
`sentinel_trace`, `sentinel_attack_graph`, `sentinel_logic`, `sentinel_review`,
`sentinel_diff`, `sentinel_harden`, `sentinel_exploit_chain`, `sentinel_report`.
"""

    files: list[tuple[Path, str, bool]] = [
        (target / ".cursor" / "rules" / "sentinel.mdc",    _CURSOR_RULE,    False),
        (target / ".windsurf" / "rules" / "sentinel.md",   _WINDSURF_RULE,  False),
        (target / ".clinerules" / "sentinel.md",            _CLINE_RULE,     False),
        (target / "AGENTS.md",                              _AGENTS_SNIPPET, True),
        (target / ".github" / "copilot-instructions.md",    _COPILOT_SNIPPET, True),
    ]

    written = []
    skipped = []

    for file_path, content, append_mode in files:
        rel = file_path.relative_to(target)

        if append_mode:
            existing = file_path.read_text(encoding="utf-8") if file_path.exists() else ""
            if _SENTINEL_TAG in existing and not force:
                skipped.append(str(rel))
                continue
            if dry_run:
                console.print(f"  [cyan]append[/cyan] {rel}")
                written.append(str(rel))
                continue
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with file_path.open("a", encoding="utf-8") as fh:
                fh.write(content)
        else:
            if file_path.exists() and not force:
                skipped.append(str(rel))
                continue
            if dry_run:
                console.print(f"  [cyan]write [/cyan] {rel}")
                written.append(str(rel))
                continue
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")

        written.append(str(rel))

    console.print(
        Panel.fit(
            f"[bold cyan]SENTINEL init[/bold cyan] — {target}",
            border_style="cyan",
        )
    )

    if written:
        console.print("[green]Written:[/green]")
        for f in written:
            console.print(f"  ✓ {f}")

    if skipped:
        console.print("[yellow]Skipped (already exist — use --force to overwrite):[/yellow]")
        for f in skipped:
            console.print(f"  - {f}")

    if dry_run:
        console.print("[yellow]Dry-run: no files written.[/yellow]")


@app.command("rules")
def list_rules() -> None:
    """List all registered security rules."""
    from sentinel.rules.loader import RuleLoader

    loader = RuleLoader()
    loader.load_builtin()

    table = Table(title="SENTINEL Rules", show_lines=True)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Title")
    table.add_column("Severity", style="bold red")
    table.add_column("Confidence")
    table.add_column("Languages")
    table.add_column("CWE")

    for rule in loader.rules:
        m = rule.metadata
        table.add_row(
            m.id,
            m.title,
            m.severity.upper(),
            m.confidence,
            ", ".join(m.languages) or "all",
            ", ".join(m.cwe_ids) or "—",
        )

    console.print(table)


def _print_summary(result: AuditResult) -> None:  # type: ignore[name-defined]
    from sentinel.models.finding import Severity

    sev_styles = {
        "critical": "bold red",
        "high": "red",
        "medium": "yellow",
        "low": "blue",
        "info": "white",
    }

    table = Table(title="Audit Summary")
    table.add_column("Severity")
    table.add_column("Count", justify="right")

    for sev in Severity:
        count = result.summary.by_severity.get(sev.value, 0)
        if count > 0:
            style = sev_styles[sev.value]
            table.add_row(f"[{style}]{sev.value.upper()}[/{style}]", str(count))

    table.add_row("[bold]TOTAL[/bold]", f"[bold]{result.summary.total_findings}[/bold]")
    console.print(table)


async def _do_audit(settings, request):  # type: ignore[no-untyped-def]
    from sentinel.core.engine import AuditEngine

    engine = AuditEngine(settings)
    await engine.initialize()
    result = await engine.run(request)
    return result, engine


# support `python -m sentinel`
if __name__ == "__main__":
    app()
