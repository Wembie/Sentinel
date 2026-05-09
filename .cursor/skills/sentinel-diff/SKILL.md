---
name: sentinel-diff
description: Security impact analysis of a git diff — PR auditing, commit security review
trigger: /sentinel-diff
mcp_tool: sentinel_diff
---

# sentinel-diff

Security audit scoped to a git diff. Identifies which files changed between two refs and runs the full detection rule set only on those files. Designed for PR-time security gates and commit auditing.

## When to Use

- Reviewing a PR for security issues before merge
- Auditing a specific commit for security regressions
- CI/CD pre-merge security gate
- Focused review of a security-sensitive change

## MCP Tool

```
sentinel_diff(repo_path: str, base: str, head?: str) -> DiffAuditResult
```

### Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `repo_path` | yes | Absolute or relative path to the git repository root |
| `base` | yes | Base ref (branch, tag, or commit SHA) to diff against |
| `head` | no | Head ref (default: current HEAD / working tree) |

### Returns

Security findings scoped to changed files, with the same structure as `sentinel_audit`.

## Example

```
# PR review (compare feature branch against main)
sentinel_diff(repo_path="./", base="main")

# Specific commit range
sentinel_diff(repo_path="./", base="v1.2.0", head="v1.3.0")

# Review staged changes
sentinel_diff(repo_path="./", base="HEAD")
```

## Safety Note

`base` and `head` are passed as git ref arguments (not shell-interpolated). Safe to use with arbitrary ref names, branches, and commit SHAs.

## CI/CD Integration

```yaml
# GitHub Actions
- name: SENTINEL Security Gate
  run: |
    sentinel_diff --repo . --base ${{ github.base_ref }} --format sarif > sentinel.sarif
    
- name: Upload SARIF
  uses: github/codeql-action/upload-sarif@v3
  with:
    sarif_file: sentinel.sarif
```
