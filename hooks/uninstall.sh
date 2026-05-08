#!/usr/bin/env bash
# SENTINEL Claude Code hooks uninstaller
#
# Usage:
#   bash hooks/uninstall.sh [--dry-run]

set -euo pipefail

DRY_RUN=false
for arg in "$@"; do
  case "$arg" in --dry-run) DRY_RUN=true ;; esac
done

CYAN='\033[0;36m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RESET='\033[0m'
ok()   { echo -e "${GREEN}  ✓${RESET} $*"; }
warn() { echo -e "${YELLOW}  !${RESET} $*"; }

run() {
  if $DRY_RUN; then echo -e "${YELLOW}  [dry-run]${RESET} $*"; else eval "$@"; fi
}

CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
HOOKS_DST="$CLAUDE_DIR/hooks"
SETTINGS="$CLAUDE_DIR/settings.json"
FLAG="$CLAUDE_DIR/.sentinel-active"

echo -e "\n${CYAN}SENTINEL${RESET} hooks uninstaller\n"

# Remove flag file
[ -f "$FLAG" ] && run "rm -f '$FLAG'" && ok "Removed .sentinel-active flag"

# Remove hook and statusline scripts
for f in sentinel-activate.js sentinel-statusline.sh; do
  p="$HOOKS_DST/$f"
  [ -f "$p" ] && run "rm -f '$p'" && ok "Removed $p"
done

# Remove hook entries from settings.json
UNREGISTER_PY=$(cat <<PYEOF
import json, sys, os

settings_path = sys.argv[1]
if not os.path.exists(settings_path):
    print('no-settings')
    sys.exit(0)

with open(settings_path, 'r') as f:
    try: data = json.load(f)
    except json.JSONDecodeError:
        print('invalid-json')
        sys.exit(0)

changed = False
hooks = data.get('hooks', {})
session_hooks = hooks.get('SessionStart', [])
new_hooks = [h for h in session_hooks if 'sentinel' not in str(h)]
if len(new_hooks) != len(session_hooks):
    hooks['SessionStart'] = new_hooks
    if not new_hooks:
        del hooks['SessionStart']
    changed = True

if 'sentinel' in str(data.get('statusLine', '')):
    del data['statusLine']
    changed = True

if changed:
    with open(settings_path, 'w') as f:
        json.dump(data, f, indent=2)
    print('ok')
else:
    print('nothing-to-remove')
PYEOF
)

if $DRY_RUN; then
  warn "[dry-run] Would remove sentinel hook entries from $SETTINGS"
else
  RESULT=$(python3 - "$SETTINGS" <<< "$UNREGISTER_PY" 2>&1 || true)
  case "$RESULT" in
    ok)               ok "Removed sentinel entries from $SETTINGS" ;;
    nothing-to-remove) warn "No sentinel entries found in $SETTINGS" ;;
    no-settings)      warn "$SETTINGS not found — nothing to clean" ;;
    *)                warn "Could not update $SETTINGS: $RESULT" ;;
  esac
fi

echo -e "\n${GREEN}Done.${RESET}\n"
$DRY_RUN && echo -e "${YELLOW}Dry-run: no files removed.${RESET}\n"
