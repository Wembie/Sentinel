---
name: sentinel-attack-graph
description: Trust boundary and privilege escalation graph — rendered as Mermaid flowchart
trigger: /sentinel-attack-graph
mcp_tool: sentinel_attack_graph
---

# sentinel-attack-graph

Generates a trust boundary and privilege escalation graph from the call graph built during auditing. Surfaces paths where low-privilege code can reach high-privilege operations. Output is a Mermaid flowchart renderable in any Markdown viewer.

## When to Use

- Visualizing privilege escalation paths in a codebase
- Understanding trust boundary crossings
- Identifying where unprivileged user paths reach admin or system operations
- Building threat model documentation from live code

## MCP Tool

```
sentinel_attack_graph(audit_id: str) -> AttackGraphResult
```

### Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `audit_id` | yes | UUID from a previous `sentinel_audit` call |

### Returns

```
{
  "mermaid": "flowchart TD\n  A[UserInput] -->|crosses boundary| B[AdminOp]\n  ...",
  "trust_crossings": [...],
  "privileged_reachable": [...],
  "node_count": 42,
  "edge_count": 87
}
```

## Example

```
result = sentinel_audit(target="./")
graph = sentinel_attack_graph(audit_id=result["audit_id"])
# graph["mermaid"] is a Mermaid flowchart — paste into any Markdown viewer
```

## Graph Elements

- **Nodes**: functions, endpoints, system calls, database operations
- **Edges**: call relationships, data flow
- **Trust boundaries**: color-coded by privilege level
- **High-risk paths**: highlighted where user input can reach privileged operations
