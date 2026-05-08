#!/usr/bin/env bash
# SENTINEL Claude Code hooks installer
# Copies sentinel-activate.js and registers it as a SessionStart hook.
# Also registers the statusline script.
#
# Usage:
#   bash hooks/install.sh [--dry-run] [--force]
#
# Run from the SENTINEL repo root (or set SENTINEL_SRC to the repo directory).

set -euo pipefail

DRY_RUN=false
FORCE=false

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=true ;;
    --force)   FORCE=true ;;
    *) echo "Unknown flag: $arg" >&2; exit 1 ;;
  esac
done

# ── Colors ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()  { echo -e "${CYAN}  →${RESET} $*"; }
ok()    { echo -e "${GREEN}  ✓${RESET} $*"; }
warn()  { echo -e "${YELLOW}  !${RESET} $*"; }
err()   { echo -e "${RED}  ✗${RESET} $*" >&2; }

run() {
  if $DRY_RUN; then
    echo -e "${YELLOW}  [dry-run]${RESET} $*"
  else
    eval "$@"
  fi
}

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SENTINEL_SRC="${SENTINEL_SRC:-$(dirname "$SCRIPT_DIR")}"
CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
HOOKS_DST="$CLAUDE_DIR/hooks"
SETTINGS="$CLAUDE_DIR/settings.json"

echo -e "\n${BOLD}${CYAN}SENTINEL${RESET} hooks installer\n"

# ── Pre-flight ────────────────────────────────────────────────────────────────
if [ ! -d "$CLAUDE_DIR" ]; then
  err "Claude Code config directory not found: $CLAUDE_DIR"
  err "Install Claude Code first, or set CLAUDE_CONFIG_DIR."
  exit 1
fi

if ! command -v node &>/dev/null; then
  err "Node.js required for hooks but not found on PATH."
  exit 1
fi

# ── Copy hook script ──────────────────────────────────────────────────────────
ACTIVATE_SRC="$SCRIPT_DIR/sentinel-activate.js"
ACTIVATE_DST="$HOOKS_DST/sentinel-activate.js"

if [ ! -f "$ACTIVATE_SRC" ]; then
  err "Hook source not found: $ACTIVATE_SRC"
  exit 1
fi

if [ -f "$ACTIVATE_DST" ] && ! $FORCE; then
  warn "Hook already installed: $ACTIVATE_DST  (use --force to overwrite)"
else
  run "mkdir -p '$HOOKS_DST'"
  run "cp '$ACTIVATE_SRC' '$ACTIVATE_DST'"
  run "chmod +x '$ACTIVATE_DST'"
  ok "Copied sentinel-activate.js → $ACTIVATE_DST"
fi

# ── Copy statusline script ────────────────────────────────────────────────────
STATUSLINE_SRC="$SCRIPT_DIR/sentinel-statusline.sh"
STATUSLINE_DST="$HOOKS_DST/sentinel-statusline.sh"

if [ -f "$STATUSLINE_SRC" ]; then
  if [ -f "$STATUSLINE_DST" ] && ! $FORCE; then
    warn "Statusline already installed: $STATUSLINE_DST"
  else
    run "cp '$STATUSLINE_SRC' '$STATUSLINE_DST'"
    run "chmod +x '$STATUSLINE_DST'"
    ok "Copied sentinel-statusline.sh → $STATUSLINE_DST"
  fi
fi

# ── Register in settings.json ─────────────────────────────────────────────────
# We use Python (required by SENTINEL itself) to safely update the JSON.
HOOK_ENTRY="node $ACTIVATE_DST"
STATUSLINE_ENTRY="bash $STATUSLINE_DST"

REGISTER_PY=$(cat <<PYEOF
import json, sys, os

settings_path = sys.argv[1]
hook_cmd      = sys.argv[2]
statusline_cmd= sys.argv[3]

data = {}
if os.path.exists(settings_path):
    with open(settings_path, 'r') as f:
        try: data = json.load(f)
        except json.JSONDecodeError: data = {}

# SessionStart hooks
hooks = data.setdefault('hooks', {})
session_hooks = hooks.setdefault('SessionStart', [])
already = any(hook_cmd in str(h) for h in session_hooks)
if not already:
    session_hooks.append({'matcher': '', 'hooks': [{'type': 'command', 'command': hook_cmd}]})

# Statusline
if statusline_cmd not in str(data.get('statusLine', '')):
    data['statusLine'] = statusline_cmd

with open(settings_path, 'w') as f:
    json.dump(data, f, indent=2)
print('ok')
PYEOF
)

if $DRY_RUN; then
  info "[dry-run] Would register SessionStart hook in $SETTINGS"
  info "[dry-run] Would register statusLine in $SETTINGS"
else
  RESULT=$(python3 - "$SETTINGS" "$HOOK_ENTRY" "$STATUSLINE_ENTRY" <<< "$REGISTER_PY" 2>&1 || true)
  if [ "$RESULT" = "ok" ]; then
    ok "Registered SessionStart hook in $SETTINGS"
    ok "Registered statusLine in $SETTINGS"
  else
    warn "Could not update $SETTINGS automatically: $RESULT"
    warn "Add manually:"
    warn '  "hooks": {"SessionStart": [{"matcher":"","hooks":[{"type":"command","command":"'"$HOOK_ENTRY"'"}]}]}'
    warn '  "statusLine": "'"$STATUSLINE_ENTRY"'"'
  fi
fi

echo -e "\n${GREEN}${BOLD}Hooks installed.${RESET} Restart Claude Code to activate.\n"
if $DRY_RUN; then
  echo -e "${YELLOW}Dry-run: no files written.${RESET}\n"
fi
