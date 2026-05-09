from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from pathlib import Path

import structlog

from sentinel.config import Settings
from sentinel.core.context import AuditContext
from sentinel.core.pipeline import AuditPipeline
from sentinel.graph.builder import GraphBuilder
from sentinel.llm.base import LLMProvider
from sentinel.llm.router import build_provider
from sentinel.models.audit import AuditRequest, AuditResult, AuditStatus, AuditSummary
from sentinel.parsers.project import ProjectParser
from sentinel.parsers.treesitter import TreeSitterParser
from sentinel.reporting.base import ReportFormatter
from sentinel.reporting.json_reporter import JSONReporter
from sentinel.reporting.markdown_reporter import MarkdownReporter
from sentinel.reporting.sarif_reporter import SARIFReporter
from sentinel.rules.loader import RuleLoader
from sentinel.tracing.tracer import AuditTracer

log = structlog.get_logger()


class AuditEngine:
    """Top-level orchestrator.

    Wires all subsystems together and drives the audit pipeline.
    One instance per process; call ``initialize()`` once before ``run()``.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._llm: LLMProvider | None = None
        self._project_parser = ProjectParser(settings)
        self._ts_parser = TreeSitterParser()
        self._graph_builder = GraphBuilder()
        self._rule_loader = RuleLoader()
        self._reporters: dict[str, ReportFormatter] = {
            "json": JSONReporter(),
            "markdown": MarkdownReporter(),
            "sarif": SARIFReporter(),
        }
        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized:
            return

        self._llm = build_provider(self._settings)

        self._rule_loader.load_builtin()
        for path in self._settings.rules_dirs:
            self._rule_loader.load_from_directory(path)

        self._initialized = True
        log.info(
            "engine_initialized",
            rules=len(self._rule_loader.rules),
            llm=self._settings.llm_provider,
        )

    async def run(self, request: AuditRequest) -> AuditResult:
        await self.initialize()

        result = AuditResult(
            request_id=request.id,
            status=AuditStatus.RUNNING,
            started_at=datetime.now(UTC),
        )

        ctx = AuditContext(request)
        tracer = AuditTracer(str(request.id))
        t0 = time.monotonic()

        try:
            pipeline = self._build_pipeline(request)
            await pipeline.run(ctx, tracer)
            result.status = AuditStatus.COMPLETED
        except Exception as exc:
            log.error("audit_failed", error=str(exc), request_id=str(request.id))
            result.status = AuditStatus.FAILED
            ctx.add_error(f"Audit failed: {exc}")
        finally:
            elapsed = time.monotonic() - t0
            result.completed_at = datetime.now(UTC)
            result.findings = sorted(ctx.findings, key=lambda f: f.risk_score, reverse=True)
            result.errors = ctx.errors
            result.summary = AuditSummary.from_findings(
                result.findings,
                elapsed,
                ctx.files_analyzed,
                ctx.lines_analyzed,
            )

        log.info(
            "audit_complete",
            request_id=str(request.id),
            findings=len(result.findings),
            files=result.summary.files_analyzed,
            elapsed_ms=round((time.monotonic() - t0) * 1000),
        )
        return result

    def generate_report(self, result: AuditResult, fmt: str = "markdown") -> str:
        reporter = self._reporters.get(fmt)
        if not reporter:
            raise ValueError(f"Unknown report format: {fmt!r}. Available: {list(self._reporters)}")
        return reporter.render(result)

    # --- pipeline stages ---

    def _build_pipeline(self, request: AuditRequest) -> AuditPipeline:
        pipeline = AuditPipeline()
        pipeline.add_stage("ingest", self._project_parser.ingest)
        pipeline.add_stage("parse_ast", self._stage_parse_ast)
        pipeline.add_stage("build_graph", self._graph_builder.build)
        pipeline.add_stage("run_rules", self._stage_run_rules)

        if request.llm_enabled and self._llm is not None:
            pipeline.add_stage("llm_enrich", self._stage_llm_enrich)

        return pipeline

    async def _stage_parse_ast(self, ctx: AuditContext) -> None:
        tasks = [
            self._parse_one(rel_path, content, ctx)
            for rel_path, content in ctx.file_contents.items()
            if self._ts_parser.can_parse(Path(rel_path))
        ]
        await asyncio.gather(*tasks)

    async def _parse_one(self, rel_path: str, content: str, ctx: AuditContext) -> None:
        try:
            ctx.parsed_files[rel_path] = await self._ts_parser.parse(Path(rel_path), content)
        except Exception as exc:
            ctx.add_error(f"AST parse failed for {rel_path}: {exc}")

    async def _stage_run_rules(self, ctx: AuditContext) -> None:
        results = await asyncio.gather(
            *[rule.match(ctx) for rule in self._rule_loader.rules],
            return_exceptions=True,
        )
        for rule, result in zip(self._rule_loader.rules, results, strict=True):
            if isinstance(result, BaseException):
                ctx.add_error(f"Rule {rule.metadata.id} raised: {result}")
            else:
                for finding in result:
                    ctx.add_finding(finding)

    async def _stage_llm_enrich(self, ctx: AuditContext) -> None:
        """LLM contextual enrichment — placeholder for chained reasoning over top findings."""
        if not self._llm or not ctx.findings:
            return
        top = ctx.top_findings(5)
        log.info("llm_enrich_start", count=len(top))
        # TODO: implement chain-of-thought exploit chain expansion, false-positive filtering
