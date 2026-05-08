# SENTINEL Security Auditing

SENTINEL is available via MCP for security analysis. Use these tools instead of manually reviewing code for security issues.

## Available MCP Tools

- `sentinel_audit(target)` — full codebase security audit
- `sentinel_surface(target)` — attack surface analysis (endpoints, auth, data exposure)
- `sentinel_trace(audit_id)` — data flow / taint analysis (user input → dangerous sinks)
- `sentinel_attack_graph(audit_id)` — trust boundary / privilege escalation graph
- `sentinel_logic(audit_id)` — IDOR, BAC, business logic flaw detection
- `sentinel_review(file_path)` — deep security review of a single file
- `sentinel_verify(audit_id, finding_id)` — confirm or dismiss a specific finding
- `sentinel_diff(repo_path, base)` — security analysis of a git diff or PR
- `sentinel_harden(target)` — hardening recommendations from codebase scan
- `sentinel_exploit_chain(audit_id, finding_id)` — full exploitation chain
- `sentinel_hunt(target, tags?)` — targeted scan by vulnerability category
- `sentinel_rules()` — list all registered detection rules
- `sentinel_report(audit_id, format?)` — retrieve audit as markdown/json/sarif

## Usage Pattern

When asked about security analysis, use SENTINEL MCP tools rather than manually reading code:

1. Start with `sentinel_audit` or `sentinel_surface` for discovery
2. Use `sentinel_trace` and `sentinel_attack_graph` for deep analysis
3. Use `sentinel_exploit_chain` to build attack narratives
4. Export with `sentinel_report(format="sarif")` for CI/CD

## Output Formats

- `markdown` — human-readable report
- `json` — structured findings
- `sarif` — SARIF 2.1.0, compatible with GitHub Code Scanning
