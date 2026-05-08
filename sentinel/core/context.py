from __future__ import annotations

from typing import Any

from sentinel.models.audit import AuditRequest
from sentinel.models.finding import Finding
from sentinel.models.graph import GraphEdge, GraphNode


class AuditContext:
    """Mutable accumulation bus that flows through every pipeline stage.

    Stages read from and write to this object. The graph, raw findings,
    parsed ASTs, and LLM context all live here so stages stay decoupled.
    """

    def __init__(self, request: AuditRequest) -> None:
        self.request = request
        self.findings: list[Finding] = []
        self.errors: list[str] = []

        # path -> raw source
        self.file_contents: dict[str, str] = {}
        # path -> {language, lines, size_bytes, ...}
        self.file_metadata: dict[str, dict[str, Any]] = {}
        # path -> tree-sitter or other parsed AST
        self.parsed_files: dict[str, Any] = {}

        self.graph_nodes: dict[str, GraphNode] = {}
        self.graph_edges: list[GraphEdge] = []

        # accumulated context passed to LLM stages
        self.llm_context: list[dict[str, Any]] = []

        self._extra: dict[str, Any] = {}

    # --- accumulation helpers ---

    def add_finding(self, finding: Finding) -> None:
        self.findings.append(finding)

    def add_error(self, error: str) -> None:
        self.errors.append(error)

    def add_node(self, node: GraphNode) -> None:
        self.graph_nodes[node.id] = node

    def add_edge(self, edge: GraphEdge) -> None:
        self.graph_edges.append(edge)

    # --- arbitrary stage-to-stage state ---

    def set(self, key: str, value: Any) -> None:
        self._extra[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self._extra.get(key, default)

    # --- computed properties ---

    @property
    def files_analyzed(self) -> int:
        return len(self.file_contents)

    @property
    def lines_analyzed(self) -> int:
        return sum(c.count("\n") + 1 for c in self.file_contents.values())

    def top_findings(self, n: int = 10) -> list[Finding]:
        return sorted(self.findings, key=lambda f: f.risk_score, reverse=True)[:n]
