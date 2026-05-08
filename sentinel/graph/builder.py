from __future__ import annotations

from typing import Any

import structlog

from sentinel.core.context import AuditContext
from sentinel.graph.backend import NetworkXBackend
from sentinel.models.graph import EdgeType, GraphEdge, GraphNode, NodeType, TrustLevel

log = structlog.get_logger()


class GraphBuilder:
    """Builds the context graph from ingested project data.

    Runs after the ingest and parse stages. Populates the NetworkX backend
    with file/function/class nodes and call/import edges. The resulting
    backend is stored in ``ctx`` under the key ``"graph_backend"`` for
    downstream analyzers and query stages to use.
    """

    def __init__(self) -> None:
        self._backend = NetworkXBackend()

    @property
    def backend(self) -> NetworkXBackend:
        return self._backend

    async def build(self, ctx: AuditContext) -> None:
        for rel_path, metadata in ctx.file_metadata.items():
            self._add_file_node(rel_path, metadata)

        for rel_path, parsed in ctx.parsed_files.items():
            if isinstance(parsed, dict) and "root" in parsed:
                content = ctx.file_contents.get(rel_path, "")
                self._extract_python_nodes(rel_path, parsed["root"], content)

        ctx.set("graph_backend", self._backend)
        log.info(
            "graph_built",
            nodes=self._backend.node_count(),
            edges=self._backend.edge_count(),
        )

    def _add_file_node(self, rel_path: str, metadata: dict[str, Any]) -> None:
        node = GraphNode(
            id=f"file:{rel_path}",
            type=NodeType.FILE,
            label=rel_path,
            file=rel_path,
            trust_level=TrustLevel.SEMI_TRUSTED,
            metadata=metadata,
        )
        self._backend.add_node(node)

    def _extract_python_nodes(self, rel_path: str, ast_root: dict[str, Any], content: str) -> None:
        lines = content.splitlines()
        self._walk_ast(rel_path, ast_root, lines, parent_id=f"file:{rel_path}")

    def _walk_ast(
        self,
        rel_path: str,
        node: dict[str, Any],
        lines: list[str],
        parent_id: str,
        depth: int = 0,
    ) -> None:
        if depth > 15 or node.get("truncated"):
            return

        node_type = node.get("type", "")

        if node_type == "function_definition":
            name = self._first_child_text(node, "identifier")
            if name:
                start_line = node["start"][0]
                fn_id = f"fn:{rel_path}:{name}:{start_line}"
                self._backend.add_node(
                    GraphNode(
                        id=fn_id,
                        type=NodeType.FUNCTION,
                        label=name,
                        file=rel_path,
                        line=start_line + 1,
                    )
                )
                self._backend.add_edge(GraphEdge(source=parent_id, target=fn_id, type=EdgeType.CALLS))
                parent_id = fn_id

        elif node_type == "class_definition":
            name = self._first_child_text(node, "identifier")
            if name:
                start_line = node["start"][0]
                cls_id = f"cls:{rel_path}:{name}:{start_line}"
                self._backend.add_node(
                    GraphNode(
                        id=cls_id,
                        type=NodeType.CLASS,
                        label=name,
                        file=rel_path,
                        line=start_line + 1,
                    )
                )
                self._backend.add_edge(
                    GraphEdge(source=parent_id, target=cls_id, type=EdgeType.CALLS)
                )
                parent_id = cls_id

        for child in node.get("children", []):
            self._walk_ast(rel_path, child, lines, parent_id, depth + 1)

    def _first_child_text(self, node: dict[str, Any], child_type: str) -> str | None:
        for child in node.get("children", []):
            if child.get("type") == child_type:
                return child.get("text")
        return None
