from __future__ import annotations

from sentinel.graph.backend import GraphBackend
from sentinel.models.graph import EdgeType, GraphEdge, GraphNode, NodeType, TrustLevel


class GraphQueries:
    """Reusable graph traversal queries for security analysis.

    Instantiate with any ``GraphBackend`` implementation. Call methods to
    locate trust boundary crossings, taint flows, and privilege escalation paths.
    """

    def __init__(self, backend: GraphBackend) -> None:
        self._g = backend

    def trust_boundary_crossings(self) -> list[tuple[GraphNode, GraphNode, GraphEdge]]:
        """Edges that cross from untrusted into trusted or privileged nodes."""
        results = []
        for edge in self._g.all_edges():
            src = self._g.get_node(edge.source)
            dst = self._g.get_node(edge.target)
            if src and dst:
                if src.trust_level == TrustLevel.UNTRUSTED and dst.trust_level in (
                    TrustLevel.TRUSTED,
                    TrustLevel.PRIVILEGED,
                ):
                    results.append((src, dst, edge))
        return results

    def user_input_to_sink_paths(
        self,
        sink_types: list[NodeType] | None = None,
    ) -> list[list[str]]:
        """Paths from USER_INPUT nodes to sensitive sinks (DB, output, secrets)."""
        sink_types = sink_types or [NodeType.DATABASE, NodeType.OUTPUT, NodeType.SECRET]
        sources = [n.id for n in self._g.nodes_by_type(NodeType.USER_INPUT)]
        sinks = [n.id for nt in sink_types for n in self._g.nodes_by_type(nt)]
        paths: list[list[str]] = []
        for src in sources:
            for sink in sinks:
                paths.extend(self._g.find_paths(src, sink))
        return paths

    def privileged_reachable_from_endpoints(self) -> list[tuple[str, str]]:
        """(endpoint_id, privileged_id) pairs reachable within 5 hops."""
        endpoints = [n.id for n in self._g.nodes_by_type(NodeType.ENDPOINT)]
        privileged = [n.id for n in self._g.all_nodes() if n.trust_level == TrustLevel.PRIVILEGED]
        return [
            (ep, priv)
            for ep in endpoints
            for priv in privileged
            if self._g.find_paths(ep, priv, max_length=5)
        ]

    def tainted_edges(self) -> list[GraphEdge]:
        return [e for e in self._g.all_edges() if e.tainted]

    def db_query_edges(self) -> list[GraphEdge]:
        return [e for e in self._g.all_edges() if e.type == EdgeType.DB_QUERY]
