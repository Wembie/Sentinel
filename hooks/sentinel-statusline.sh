#!/usr/bin/env bash
# SENTINEL statusline script for Claude Code.
# Reads the .sentinel-active flag and outputs a badge if active.
# Register in ~/.claude/settings.json under "statusLine".

CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
FLAG="$CLAUDE_DIR/.sentinel-active"

if [ -f "$FLAG" ] && [ ! -L "$FLAG" ]; then
  echo "🛡 SENTINEL"
fi
