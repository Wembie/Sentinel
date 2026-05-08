---
name: sentinel-surface
description: Fast attack surface mapping — endpoints, auth entry points, data exposure, no deep analysis
trigger: /sentinel-surface
mcp_tool: sentinel_surface
---

# sentinel-surface

Fast attack surface mapping: enumerate all HTTP endpoints, authentication entry points, file upload handlers, data export routes, and other user-facing surfaces. No deep rule analysis — designed for rapid reconnaissance before a full audit.

## When to Use

- Quick orientation on a new codebase before deep analysis
- Enumerating all entry points for a threat model
- Identifying which routes handle unauthenticated requests
- CI/CD surface-change detection (what new attack surface did this PR add?)

## MCP Tool

```
sentinel_surface(target: str, languages?: str) -> SurfaceResult
```

### Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `target` | yes | Absolute or relative path to the directory to scan |
| `languages` | no | Comma-separated language filter |

### Returns

Enumerated attack surface: routes, endpoints, auth patterns, exposed data handlers, file operations.

## Example

```
sentinel_surface(target="./")
sentinel_surface(target="./api", languages="python")
```

## Surface Categories

- HTTP endpoints (GET/POST/PUT/DELETE routes)
- Authentication handlers (login, token validation, OAuth callbacks)
- File upload and download endpoints
- Admin and privileged routes
- External API call sites
- Database query entry points
- Deserialization entry points

## After Surface Mapping

Use `sentinel_audit` for deep analysis, or `sentinel_trace` to follow specific entry points to dangerous sinks.
