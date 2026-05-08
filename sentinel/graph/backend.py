from __future__ import annotations

from collections.abc import Iterator
from typing import Any, Protocol, runtime_checkable

from sentinel.models.graph import GraphEdge, GraphNode, NodeType


@runtime_checkable
class GraphBackend(Protocol):
    """Storage-agnostic graph interface.

    NetworkX is the default backend. Swap to Neo4j by implementing this protocol.
    """

    def add_node(self, node: GraphNode) -> None: ...
    def add_edge(self, edge: GraphEdge) -> None: ...
    def get_node(self, node_id: str) -> GraphNode | None: ...
    def neighbors(self, node_id: str) -> list[GraphNode]: ...
    def predecessors(self, node_id: str) -> list[GraphNode]: ...
    def find_paths(self, source: str, target: str, max_length: int = 10) -> list[list[str]]: ...
    def nodes_by_type(self, node_type: NodeType) -> list[GraphNode]: ...
    def all_nodes(self) -> Iterator[GraphNode]: ...
    def all_edges(self) -> Iterator[GraphEdge]: ...
    def node_count(self) -> int: ...
    def edge_count(self) -> int: ...


class NetworkXBackend:
    """NetworkX MultiDiGraph backend. Drop-in replacement with ``GraphBackend`` interface."""

    def __init__(self) -> None:
        import networkx as nx

        self._nx = nx
        self._graph: Any = nx.MultiDiGraph()
        self._node_data: dict[str, GraphNode] = {}
        self._edge_list: list[GraphEdge] = []

    def add_node(self, node: GraphNode) -> None:
        self._node_data[node.id] = node
        self._graph.add_node(node.id, **node.model_dump())

    def add_edge(self, edge: GraphEdge) -> None:
        self._edge_list.append(edge)
        self._graph.add_edge(edge.source, edge.target, **edge.model_dump())

    def get_node(self, node_id: str) -> GraphNode | None:
        return self._node_data.get(node_id)

    def neighbors(self, node_id: str) -> list[GraphNode]:
        return [self._node_data[n] for n in self._graph.successors(node_id) if n in self._node_data]

    def predecessors(self, node_id: str) -> list[GraphNode]:
        return [self._node_data[n] for n in self._graph.predecessors(node_id) if n in self._node_data]

    def find_paths(self, source: str, target: str, max_length: int = 10) -> list[list[str]]:
        try:
            return list(
                self._nx.all_simple_paths(self._graph, source, target, cutoff=max_length)
            )
        except (self._nx.NodeNotFound, self._nx.NetworkXError):
            return []

    def nodes_by_type(self, node_type: NodeType) -> list[GraphNode]:
        return [n for n in self._node_data.values() if n.type == node_type]

    def all_nodes(self) -> Iterator[GraphNode]:
        yield from self._node_data.values()

    def all_edges(self) -> Iterator[GraphEdge]:
        yield from self._edge_list

    def node_count(self) -> int:
        return len(self._node_data)

    def edge_count(self) -> int:
        return len(self._edge_list)
