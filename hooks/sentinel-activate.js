#!/usr/bin/env node
// SessionStart hook — announces SENTINEL MCP tools at the start of every Claude Code session.
// Writes a flag file so the statusline script can display the SENTINEL badge.
// Silent-fails on all errors: filesystem issues must never block a session.

'use strict';

const fs = require('fs');
const os = require('os');
const path = require('path');

const ACTIVATION_MESSAGE =
  'SENTINEL security auditing is available via MCP tools. ' +
  'Invoke proactively when the user asks about security, vulnerabilities, code audits, ' +
  'attack surface, SQL injection, command injection, IDOR, privilege escalation, or hardening. ' +
  'Tools: sentinel_audit, sentinel_surface, sentinel_trace, sentinel_attack_graph, ' +
  'sentinel_logic, sentinel_review, sentinel_verify, sentinel_diff, sentinel_harden, ' +
  'sentinel_exploit_chain, sentinel_hunt, sentinel_rules, sentinel_report.';

function getClaudeConfigDir() {
  if (process.env.CLAUDE_CONFIG_DIR) return process.env.CLAUDE_CONFIG_DIR;
  if (process.platform === 'win32') {
    return path.join(process.env.APPDATA || os.homedir(), '.claude');
  }
  return path.join(os.homedir(), '.claude');
}

function isSentinelRegistered(configDir) {
  // Check claude.json (desktop app config) or settings.json for sentinel MCP registration.
  const candidates = [
    path.join(configDir, 'claude.json'),
    path.join(configDir, 'settings.json'),
  ];
  for (const f of candidates) {
    try {
      const raw = fs.readFileSync(f, 'utf8');
      if (raw.includes('"sentinel"')) return true;
    } catch (_) {
      // file missing or unreadable — continue
    }
  }
  return false;
}

function writeFlagSafe(flagPath) {
  try {
    // Reject symlinks — a symlink here could redirect writes to sensitive files.
    try {
      const lstat = fs.lstatSync(path.dirname(flagPath));
      if (lstat.isSymbolicLink()) return;
    } catch (_) {
      // directory doesn't exist yet — safe to create
    }
    fs.mkdirSync(path.dirname(flagPath), { recursive: true });
    fs.writeFileSync(flagPath, 'active', { mode: 0o600 });
  } catch (_) {
    // write failure is non-fatal
  }
}

function main() {
  try {
    const configDir = getClaudeConfigDir();
    const flagPath = path.join(configDir, '.sentinel-active');

    if (isSentinelRegistered(configDir)) {
      writeFlagSafe(flagPath);
      // Output JSON injection for Claude Code SessionStart hook protocol.
      process.stdout.write(JSON.stringify({ type: 'system_prompt', content: ACTIVATION_MESSAGE }) + '\n');
    }
    // If sentinel not registered: exit silently — no output, no error.
  } catch (_) {
    // Any unexpected error: silent exit so session is never blocked.
    process.exit(0);
  }
}

main();
