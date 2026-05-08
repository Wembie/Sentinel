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
