#!/usr/bin/env bash
# SENTINEL Installer — macOS / Linux / WSL / Git Bash
#
# One line:
#   curl -fsSL https://raw.githubusercontent.com/Wembie/Sentinel/main/install.sh | bash
#
# Detects which AI coding agents are on your machine and registers SENTINEL
# as an MCP server for each one. Skips agents that aren't installed.
# Safe to re-run — idempotent per agent.
#
# Run `install.sh --help` for the full flag reference and agent matrix.

set -euo pipefail

# ── Constants ──────────────────────────────────────────────────────────────
REPO="Wembie/Sentinel"
REPO_URL="https://github.com/$REPO"
REPO_ARCHIVE="https://github.com/$REPO/archive/refs/heads/main.tar.gz"
INSTALL_DIR="${SENTINEL_HOME:-$HOME/.sentinel}"
BIN_DIR="${SENTINEL_BIN:-$HOME/.local/bin}"
MIN_PYTHON_MAJOR=3
MIN_PYTHON_MINOR=11

# ── Flags ──────────────────────────────────────────────────────────────────
DRY=0
FORCE=0
MODE="install"   # install | dev | upgrade | uninstall | list
WITH_HOOKS=auto  # auto resolves to 1 unless --minimal is set
WITH_INIT=0
ALL=0
MINIMAL=0
SKIP_SKILLS=0
NO_COLOR=0
ONLY=()

# Result trackers (parallel indexed arrays — bash 3.2 safe)
INSTALLED_IDS=()
SKIPPED_IDS=()
SKIPPED_WHY=()
FAILED_IDS=()
FAILED_WHY=()
DETECTED_COUNT=0

# ── Color setup (auto-disable on non-TTY) ──────────────────────────────────
if [ ! -t 1 ]; then NO_COLOR=1; fi

# ── Argument parsing ───────────────────────────────────────────────────────
print_help() {
  cat <<'EOF'
SENTINEL installer — detects your agents and registers the MCP server for each.

USAGE
  install.sh [flags]

  curl -fsSL https://raw.githubusercontent.com/Wembie/Sentinel/main/install.sh | bash
  curl -fsSL https://raw.githubusercontent.com/Wembie/Sentinel/main/install.sh | bash -s -- --with-hooks

FLAGS
  --dev             Clone repository and install in editable mode (requires git).
  --upgrade         Pull latest and re-sync dependencies (requires --dev install).
  --uninstall       Remove SENTINEL installation.
  --dry-run         Print all actions without executing anything.
  --force           Re-register even if already registered.
  --only <agent>    Register with a specific agent only. Repeatable.
  --skip-skills     Skip the npx-skills auto-detect fallback.
  --all             Turn on --with-hooks and --with-init.
  --minimal         Package only; skip hooks, per-project init, and skills.
  --with-hooks      Install Claude Code SessionStart hooks. On by default.
  --with-init       Run `sentinel init` in the current directory.
  --list            Print the full agent matrix and exit.
  --no-color        Disable ANSI color codes (auto-disabled on non-TTY).
  -h, --help        Show this help and exit.

AGENTS DETECTED
  Native:
    claude      Claude Code           claude mcp add
    gemini      Gemini CLI            gemini extensions install
    codex       Codex CLI             npx skills add (codex)
  IDE / VS Code-family:
    cursor      Cursor IDE            npx skills add (cursor)
    windsurf    Windsurf IDE          npx skills add (windsurf)
    cline       Cline                 npx skills add (cline)
    copilot     GitHub Copilot        npx skills add (github-copilot)
    continue    Continue              npx skills add (continue)
    kilo        Kilo Code             npx skills add (kilo)
    roo         Roo Code              npx skills add (roo)
    augment     Augment Code          npx skills add (augment)
  CLI agents (30+ via skills):
    aider-desk  Aider Desk            npx skills add (aider-desk)
    amp         Sourcegraph Amp       npx skills add (amp)
    bob         IBM Bob               npx skills add (bob)
    crush       Crush                 npx skills add (crush)
    devin       Devin                 npx skills add (devin)
    droid       Droid (Factory)       npx skills add (droid)
    forgecode   ForgeCode             npx skills add (forgecode)
    goose       Block Goose           npx skills add (goose)
    iflow       iFlow CLI             npx skills add (iflow-cli)
    junie       JetBrains Junie       npx skills add (junie)
    kiro        Kiro CLI              npx skills add (kiro-cli)
    mistral     Mistral Vibe          npx skills add (mistral-vibe)
    openhands   OpenHands             npx skills add (openhands)
    opencode    opencode              npx skills add (opencode)
    qwen        Qwen Code             npx skills add (qwen-code)
    qoder       Qoder                 npx skills add (qoder)
    rovodev     Atlassian Rovo Dev    npx skills add (rovodev)
    tabnine     Tabnine CLI           npx skills add (tabnine-cli)
    trae        Trae                  npx skills add (trae)
    warp        Warp                  npx skills add (warp)
    replit      Replit Agent          npx skills add (replit)
    antigravity Google Antigravity    npx skills add (antigravity)

ENVIRONMENT
  SENTINEL_HOME   Install directory (default: ~/.sentinel)
  SENTINEL_BIN    Bin dir for sentinel-mcp wrapper (default: ~/.local/bin)

EXAMPLES
  install.sh                        # default: install + hooks
  install.sh --all                  # install + hooks + per-project init
  install.sh --minimal              # install package only
  install.sh --dry-run --all
  install.sh --only claude
  install.sh --only cursor --only windsurf
  install.sh --upgrade
  install.sh --list
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --dev)         MODE="dev" ;;
    --upgrade)     MODE="upgrade" ;;
    --uninstall)   MODE="uninstall" ;;
    --dry-run)     DRY=1 ;;
    --force)       FORCE=1 ;;
    --skip-skills) SKIP_SKILLS=1 ;;
    --with-hooks)  WITH_HOOKS=1 ;;
    --with-init)   WITH_INIT=1 ;;
    --all)         ALL=1 ;;
    --minimal)     MINIMAL=1 ;;
    --list)        MODE="list" ;;
    --no-color)    NO_COLOR=1 ;;
    --only)
      shift
      [ $# -eq 0 ] && { echo "error: --only requires an argument" >&2; exit 2; }
      ONLY+=("$1") ;;
    -h|--help) print_help; exit 0 ;;
    *) echo "error: unknown flag: $1" >&2; echo "run 'install.sh --help' for usage" >&2; exit 2 ;;
  esac
  shift
done

# Resolve --all / --minimal / "auto" into concrete values.
if [ "$ALL" = 1 ] && [ "$MINIMAL" = 1 ]; then
  echo "error: --all and --minimal are mutually exclusive" >&2; exit 2
fi
if [ "$ALL" = 1 ];     then WITH_HOOKS=1; WITH_INIT=1; fi
if [ "$MINIMAL" = 1 ]; then WITH_HOOKS=0; WITH_INIT=0; SKIP_SKILLS=1; fi
[ "$WITH_HOOKS" = "auto" ] && WITH_HOOKS=1

# ── Color helpers ──────────────────────────────────────────────────────────
if [ "$NO_COLOR" = 1 ]; then
  c_blue=""; c_dim=""; c_red=""; c_green=""; c_yellow=""; c_reset=""
else
  c_blue=$'\033[34m'
  c_dim=$'\033[2m'
  c_red=$'\033[31m'
  c_green=$'\033[32m'
  c_yellow=$'\033[33m'
  c_reset=$'\033[0m'
fi

say()  { printf '%s%s%s\n' "$c_blue"   "$1" "$c_reset"; }
note() { printf '%s%s%s\n' "$c_dim"    "$1" "$c_reset"; }
warn() { printf '%s%s%s\n' "$c_yellow" "$1" "$c_reset" >&2; }
err()  { printf '%s%s%s\n' "$c_red"    "$1" "$c_reset" >&2; }
ok()   { printf '%s%s%s\n' "$c_green"  "$1" "$c_reset"; }

# ── Helpers ────────────────────────────────────────────────────────────────
want() {
  [ ${#ONLY[@]} -eq 0 ] && return 0
  local a; for a in "${ONLY[@]}"; do [ "$a" = "$1" ] && return 0; done
  return 1
}

run() {
  if [ "$DRY" = 1 ]; then note "  would run: $*"; return 0; fi
  echo "  $ $*"; "$@"
}

try() {
  if [ "$DRY" = 1 ]; then note "  would run: $*"; return 0; fi
  echo "  $ $*"; "$@"
}

has() { command -v "$1" >/dev/null 2>&1; }

ensure_node() {
  has node && has npx && return 0
  warn "  node + npx required — install Node.js (https://nodejs.org) and re-run."
  return 1
}

record_installed() { INSTALLED_IDS+=("$1"); }
record_skipped()   { SKIPPED_IDS+=("$1"); SKIPPED_WHY+=("$2"); }
record_failed()    { FAILED_IDS+=("$1"); FAILED_WHY+=("$2"); }

# ── Detection helpers ──────────────────────────────────────────────────────
vscode_ext_present() {
  local needle="$1"
  local roots=("$HOME/.vscode/extensions" "$HOME/.vscode-server/extensions" "$HOME/.cursor/extensions" "$HOME/.windsurf/extensions")
  local r
  for r in "${roots[@]}"; do
    [ -d "$r" ] && ls "$r" 2>/dev/null | grep -qi "$needle" && return 0
  done
  return 1
}

cursor_ext_present() {
  local needle="$1"
  [ -d "$HOME/.cursor/extensions" ] && ls "$HOME/.cursor/extensions" 2>/dev/null | grep -qi "$needle"
}

jetbrains_plugin_present() {
  local needle="$1"
  local roots=("$HOME/Library/Application Support/JetBrains" "$HOME/.config/JetBrains")
  local r
  for r in "${roots[@]}"; do
    [ -d "$r" ] && find "$r" -maxdepth 4 -type d -iname "*${needle}*" 2>/dev/null | grep -q . && return 0
  done
  return 1
}

# Parse a PROVIDER_DETECT spec ("command:foo||dir:~/.x") and return 0 if any clause matches.
# Splits on '||' via parameter expansion — avoids BSD awk regex bugs.
detect_match() {
  local spec="$1" rest="$spec" clause
  while [ -n "$rest" ]; do
    if [ "${rest#*||}" != "$rest" ]; then
      clause="${rest%%||*}"; rest="${rest#*||}"
    else
      clause="$rest"; rest=""
    fi
    [ -z "$clause" ] && continue
    case "$clause" in
      command:*)           has "${clause#command:}" && return 0 ;;
      dir:*)               [ -d "${clause#dir:}" ] && return 0 ;;
      file:*)              [ -f "${clause#file:}" ] && return 0 ;;
      vscode-ext:*)        vscode_ext_present "${clause#vscode-ext:}" && return 0 ;;
      cursor-ext:*)        cursor_ext_present "${clause#cursor-ext:}" && return 0 ;;
      jetbrains-plugin:*)  jetbrains_plugin_present "${clause#jetbrains-plugin:}" && return 0 ;;
    esac
  done
  return 1
}

# ── Provider matrix (bash 3.2-safe parallel arrays) ───────────────────────
# id | label | skills profile | detection spec
# claude and gemini are handled by dedicated functions — included here for --list only.
PROVIDER_IDS=(
  "claude" "gemini" "codex"
  "cursor" "windsurf" "cline" "copilot" "continue" "kilo" "roo" "augment"
  "aider-desk" "amp" "bob" "crush" "devin" "droid" "forgecode" "goose"
  "iflow" "junie" "kiro" "mistral" "openhands" "opencode" "qwen" "qoder"
  "rovodev" "tabnine" "trae" "warp" "replit" "antigravity"
)
PROVIDER_LABELS=(
  "Claude Code" "Gemini CLI" "Codex CLI"
  "Cursor" "Windsurf" "Cline" "GitHub Copilot" "Continue" "Kilo Code" "Roo Code" "Augment Code"
  "Aider Desk" "Sourcegraph Amp" "IBM Bob" "Crush" "Devin" "Droid (Factory)" "ForgeCode" "Block Goose"
  "iFlow CLI" "JetBrains Junie" "Kiro CLI" "Mistral Vibe" "OpenHands" "opencode" "Qwen Code" "Qoder"
  "Atlassian Rovo Dev" "Tabnine CLI" "Trae" "Warp" "Replit Agent" "Google Antigravity"
)
PROVIDER_MECHS=(
  "claude mcp add" "gemini extensions install" "npx skills add (codex)"
  "npx skills add (cursor)" "npx skills add (windsurf)" "npx skills add (cline)"
  "npx skills add (github-copilot)" "npx skills add (continue)" "npx skills add (kilo)"
  "npx skills add (roo)" "npx skills add (augment)"
  "npx skills add (aider-desk)" "npx skills add (amp)" "npx skills add (bob)"
  "npx skills add (crush)" "npx skills add (devin)" "npx skills add (droid)"
  "npx skills add (forgecode)" "npx skills add (goose)" "npx skills add (iflow-cli)"
  "npx skills add (junie)" "npx skills add (kiro-cli)" "npx skills add (mistral-vibe)"
  "npx skills add (openhands)" "npx skills add (opencode)" "npx skills add (qwen-code)"
  "npx skills add (qoder)" "npx skills add (rovodev)" "npx skills add (tabnine-cli)"
  "npx skills add (trae)" "npx skills add (warp)" "npx skills add (replit)"
  "npx skills add (antigravity)"
)
PROVIDER_DETECT=(
  "command:claude||dir:$HOME/.claude"
  "command:gemini||dir:$HOME/.gemini"
  "command:codex||dir:$HOME/.codex"
  "command:cursor||dir:$HOME/.cursor"
  "command:windsurf||dir:$HOME/.codeium/windsurf||dir:$HOME/.windsurf"
  "vscode-ext:cline"
  "command:gh"
  "vscode-ext:continue.continue||vscode-ext:continue"
  "vscode-ext:kilocode||dir:$HOME/.kilocode"
  "vscode-ext:roo||vscode-ext:rooveterinaryinc.roo-cline||cursor-ext:roo"
  "vscode-ext:augment||jetbrains-plugin:augment"
  "command:aider||dir:$HOME/.aider-desk"
  "command:amp"
  "command:bob||dir:$HOME/.bob"
  "command:crush||dir:$HOME/.config/crush"
  "command:devin||dir:$HOME/.config/devin"
  "command:droid||dir:$HOME/.factory"
  "command:forge||dir:$HOME/.forge"
  "command:goose||dir:$HOME/.config/goose"
  "command:iflow||dir:$HOME/.iflow"
  "dir:$HOME/.junie||jetbrains-plugin:junie"
  "command:kiro||dir:$HOME/.kiro"
  "command:mistral||dir:$HOME/.vibe"
  "command:openhands||dir:$HOME/.openhands"
  "command:opencode||file:$HOME/.config/opencode/AGENTS.md"
  "command:qwen||dir:$HOME/.qwen"
  "dir:$HOME/.qoder"
  "command:rovodev||dir:$HOME/.rovodev"
  "command:tabnine||dir:$HOME/.tabnine"
  "command:trae||dir:$HOME/.trae"
  "command:warp||dir:$HOME/.warp"
  "command:replit||dir:$HOME/.replit"
  "dir:$HOME/.gemini/antigravity"
)

# ── --list mode ────────────────────────────────────────────────────────────
if [ "$MODE" = "list" ]; then
  say "🛡  SENTINEL agent matrix"
  printf '\n  %-14s %-22s %s\n' "ID" "AGENT" "INSTALL MECHANISM"
  printf '  %-14s %-22s %s\n'   "----" "-----" "-----------------"
  i=0; total=${#PROVIDER_IDS[@]}
  while [ $i -lt "$total" ]; do
    printf '  %-14s %-22s %s\n' "${PROVIDER_IDS[$i]}" "${PROVIDER_LABELS[$i]}" "${PROVIDER_MECHS[$i]}"
    i=$((i + 1))
  done
  echo
  note "  Defaults: --with-hooks ON. --all turns on --with-init. --minimal turns both off."
  echo
  exit 0
fi

# ── Core install helpers ───────────────────────────────────────────────────
check_python() {
  local py_cmd=""
  for candidate in python3 python python3.11 python3.12 python3.13; do
    if has "$candidate"; then
      local ver major minor
      ver=$("$candidate" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
      major="${ver%%.*}"; minor="${ver##*.}"
      if [[ "$major" -gt "$MIN_PYTHON_MAJOR" ]] || \
         [[ "$major" -eq "$MIN_PYTHON_MAJOR" && "$minor" -ge "$MIN_PYTHON_MINOR" ]]; then
        py_cmd="$candidate"; break
      fi
    fi
  done
  [ -z "$py_cmd" ] && { err "Python ${MIN_PYTHON_MAJOR}.${MIN_PYTHON_MINOR}+ required — https://python.org"; exit 1; }
  echo "$py_cmd"
}

install_uv() {
  has uv && { note "  uv $(uv --version) already installed"; return; }
  say "  → installing uv..."
  if [ "$DRY" = 1 ]; then note "  would run: curl -LsSf https://astral.sh/uv/install.sh | sh"; return; fi
  if has curl; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
  elif has wget; then
    wget -qO- https://astral.sh/uv/install.sh | sh
  else
    err "curl or wget required to install uv"; exit 1
  fi
  export PATH="$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
  has uv || { err "uv installed but not on PATH — add ~/.local/bin to PATH"; exit 1; }
}

ensure_bin_dir() {
  mkdir -p "$BIN_DIR"
  if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    warn "  $BIN_DIR not on PATH — add: export PATH=\"\$PATH:$BIN_DIR\""
  fi
}

write_wrapper() {
  local wrapper="$BIN_DIR/sentinel-mcp"
  [ "$DRY" = 1 ] && { note "  would write $wrapper"; return; }
  cat > "$wrapper" <<EOF
#!/usr/bin/env bash
exec uv run --project "$INSTALL_DIR" python -m sentinel.mcp "\$@"
EOF
  chmod +x "$wrapper"
  ok "  wrapper: $wrapper"
}

validate_install() {
  [ "$DRY" = 1 ] && { note "  would validate: import sentinel"; return; }
  uv run --project "$INSTALL_DIR" python -c "import sentinel" &>/dev/null \
    || { err "import validation failed — check: uv run --project $INSTALL_DIR python -c 'import sentinel'"; exit 1; }
  ok "  import OK"
}

write_config() {
  local config_dir="$HOME/.config/sentinel"
  local config_file="$config_dir/config.json"

  if [ -f "$config_file" ]; then
    note "  config exists at $config_file — skipping"
    return
  fi

  local provider="" api_key=""
  if [[ -n "${ANTHROPIC_API_KEY:-}" ]]; then
    provider="claude"; api_key="$ANTHROPIC_API_KEY"
  elif [[ -n "${OPENAI_API_KEY:-}" ]]; then
    provider="openai"; api_key="$OPENAI_API_KEY"
  else
    return
  fi

  say "  → detected $provider API key — writing config"
  if [ "$DRY" = 1 ]; then note "  would write $config_file (llm_provider=$provider)"; return; fi

  mkdir -p "$config_dir"
  printf '{\n  "llm_provider": "%s",\n  "llm_api_key": "%s"\n}\n' "$provider" "$api_key" > "$config_file"
  ok "  config: $config_file"
}

# ── Core installation (download + deps + wrapper) ──────────────────────────
do_core_install() {
  local dev_mode="${1:-false}"

  say "🛡  SENTINEL installer"
  note "  $REPO_URL"
  [ "$DRY" = 1 ] && note "  (dry run — nothing will be written)"
  echo

  local py_cmd; py_cmd=$(check_python)
  note "  python: $("$py_cmd" --version)"

  install_uv

  if [ "$dev_mode" = "true" ]; then
    has git || { err "--dev requires git — https://git-scm.com"; exit 1; }
    if [ -d "$INSTALL_DIR/.git" ]; then
      warn "  $INSTALL_DIR already exists — use --upgrade"
    else
      say "  → cloning to $INSTALL_DIR..."
      run git clone "$REPO_URL" "$INSTALL_DIR"
    fi
  else
    if [ -d "$INSTALL_DIR" ]; then
      warn "  $INSTALL_DIR already exists — use --upgrade or --uninstall first"
    else
      say "  → downloading to $INSTALL_DIR..."
      if [ "$DRY" = 1 ]; then
        note "  would download $REPO_ARCHIVE → $INSTALL_DIR"
      else
        mkdir -p "$INSTALL_DIR"
        if has curl; then
          curl -fsSL "$REPO_ARCHIVE" | tar -xz --strip-components=1 -C "$INSTALL_DIR"
        elif has wget; then
          wget -qO- "$REPO_ARCHIVE" | tar -xz --strip-components=1 -C "$INSTALL_DIR"
        else
          err "curl or wget required"; exit 1
        fi
      fi
    fi
  fi

  say "  → syncing dependencies..."
  run uv sync --project "$INSTALL_DIR"

  ensure_bin_dir
  write_wrapper
  validate_install
  write_config
  echo
}

# ── Per-agent install functions ────────────────────────────────────────────
install_claude() {
  DETECTED_COUNT=$((DETECTED_COUNT + 1))
  say "→ Claude Code detected"

  # Idempotency check
  if [ "$FORCE" = 0 ] && has claude && claude mcp list 2>/dev/null | grep -qi "^sentinel"; then
    note "  sentinel MCP already registered (--force to re-register)"
    record_skipped "claude" "already registered"
    echo; return 0
  fi

  if has claude; then
    if try claude mcp add sentinel -- uv run --project "$INSTALL_DIR" python -m sentinel.mcp; then
      ok "  MCP server registered"
      record_installed "claude"
    else
      warn "  claude mcp add failed"
      record_failed "claude" "claude mcp add failed"
    fi
  else
    # Write config file manually
    local claude_cfg="$HOME/.claude/claude.json"
    if [ "$DRY" = 1 ]; then
      note "  would patch $claude_cfg"
      record_installed "claude (dry-run)"
    else
      warn "  claude CLI not found — add MCP server manually:"
      note "    command: uv"
      note "    args: [\"run\", \"--project\", \"$INSTALL_DIR\", \"python\", \"-m\", \"sentinel.mcp\"]"
      record_failed "claude" "claude CLI not on PATH"
    fi
  fi

  # --with-hooks
  if [ "$WITH_HOOKS" = 1 ]; then
    say "  → installing Claude Code hooks..."
    local hooks_installer="$INSTALL_DIR/hooks/install.sh"
    if [ -f "$hooks_installer" ]; then
      local hooks_args=""; [ "$FORCE" = 1 ] && hooks_args="--force"
      if [ "$DRY" = 1 ]; then
        note "  would run: bash $hooks_installer $hooks_args"
      else
        # shellcheck disable=SC2086
        if bash "$hooks_installer" $hooks_args; then
          record_installed "claude-hooks"
        else
          warn "  hooks installer failed (non-fatal)"
          record_failed "claude-hooks" "hooks/install.sh failed"
        fi
      fi
    else
      note "  hooks installer not found at $hooks_installer — run: bash $INSTALL_DIR/hooks/install.sh"
      record_skipped "claude-hooks" "installer not found (run hooks/install.sh manually)"
    fi
  fi

  echo
}

install_gemini() {
  DETECTED_COUNT=$((DETECTED_COUNT + 1))
  say "→ Gemini CLI detected"

  if [ "$FORCE" = 0 ] && gemini extensions list 2>/dev/null | grep -qi "sentinel"; then
    note "  sentinel extension already installed (--force to reinstall)"
    record_skipped "gemini" "already installed"
    echo; return 0
  fi

  if try gemini extensions install "$REPO_URL"; then
    record_installed "gemini"
  else
    record_failed "gemini" "gemini extensions install failed"
  fi
  echo
}

install_via_skills() {
  local id="$1" label="$2" profile="$3"
  DETECTED_COUNT=$((DETECTED_COUNT + 1))
  say "→ $label detected"

  if ! ensure_node; then
    record_failed "$id" "node/npx missing"
    echo; return 0
  fi

  if try npx -y skills add "$REPO_URL" -a "$profile"; then
    record_installed "$id"
  else
    record_failed "$id" "npx skills add (profile: $profile) failed"
  fi
  echo
}

# ── Uninstall ──────────────────────────────────────────────────────────────
do_uninstall() {
  say "🛡  uninstalling SENTINEL..."
  if [ -d "$INSTALL_DIR" ]; then
    run rm -rf "$INSTALL_DIR"; ok "  removed $INSTALL_DIR"
  else
    warn "  $INSTALL_DIR not found"
  fi
  local wrapper="$BIN_DIR/sentinel-mcp"
  if [ -f "$wrapper" ]; then
    run rm -f "$wrapper"; ok "  removed $wrapper"
  fi
  ok "  done."
}

# ── Upgrade ────────────────────────────────────────────────────────────────
do_upgrade() {
  [ -d "$INSTALL_DIR/.git" ] || { err "upgrade requires a --dev install (git repo at $INSTALL_DIR)"; exit 1; }
  say "🛡  upgrading SENTINEL..."
  run git -C "$INSTALL_DIR" pull --ff-only
  run uv sync --project "$INSTALL_DIR"
  validate_install
  ok "  upgraded."
}

# ── Dispatch non-registration modes ───────────────────────────────────────
case "$MODE" in
  uninstall) do_uninstall; exit 0 ;;
  upgrade)   do_upgrade;   exit 0 ;;
  install)   do_core_install "false" ;;
  dev)       do_core_install "true" ;;
esac

# ── Agent registration ─────────────────────────────────────────────────────
say "🛡  registering with detected agents..."
echo

# Claude (native MCP + hooks)
if want claude && detect_match "${PROVIDER_DETECT[0]}"; then
  install_claude
fi

# Gemini (native extension)
if want gemini && detect_match "${PROVIDER_DETECT[1]}"; then
  install_gemini
fi

# All skills-based agents
SKILLS_AGENTS=(
  "codex|Codex CLI|codex|${PROVIDER_DETECT[2]}"
  "cursor|Cursor|cursor|${PROVIDER_DETECT[3]}"
  "windsurf|Windsurf|windsurf|${PROVIDER_DETECT[4]}"
  "cline|Cline|cline|${PROVIDER_DETECT[5]}"
  "copilot|GitHub Copilot|github-copilot|${PROVIDER_DETECT[6]}"
  "continue|Continue|continue|${PROVIDER_DETECT[7]}"
  "kilo|Kilo Code|kilo|${PROVIDER_DETECT[8]}"
  "roo|Roo Code|roo|${PROVIDER_DETECT[9]}"
  "augment|Augment Code|augment|${PROVIDER_DETECT[10]}"
  "aider-desk|Aider Desk|aider-desk|${PROVIDER_DETECT[11]}"
  "amp|Sourcegraph Amp|amp|${PROVIDER_DETECT[12]}"
  "bob|IBM Bob|bob|${PROVIDER_DETECT[13]}"
  "crush|Crush|crush|${PROVIDER_DETECT[14]}"
  "devin|Devin|devin|${PROVIDER_DETECT[15]}"
  "droid|Droid (Factory)|droid|${PROVIDER_DETECT[16]}"
  "forgecode|ForgeCode|forgecode|${PROVIDER_DETECT[17]}"
  "goose|Block Goose|goose|${PROVIDER_DETECT[18]}"
  "iflow|iFlow CLI|iflow-cli|${PROVIDER_DETECT[19]}"
  "junie|JetBrains Junie|junie|${PROVIDER_DETECT[20]}"
  "kiro|Kiro CLI|kiro-cli|${PROVIDER_DETECT[21]}"
  "mistral|Mistral Vibe|mistral-vibe|${PROVIDER_DETECT[22]}"
  "openhands|OpenHands|openhands|${PROVIDER_DETECT[23]}"
  "opencode|opencode|opencode|${PROVIDER_DETECT[24]}"
  "qwen|Qwen Code|qwen-code|${PROVIDER_DETECT[25]}"
  "qoder|Qoder|qoder|${PROVIDER_DETECT[26]}"
  "rovodev|Atlassian Rovo Dev|rovodev|${PROVIDER_DETECT[27]}"
  "tabnine|Tabnine CLI|tabnine-cli|${PROVIDER_DETECT[28]}"
  "trae|Trae|trae|${PROVIDER_DETECT[29]}"
  "warp|Warp|warp|${PROVIDER_DETECT[30]}"
  "replit|Replit Agent|replit|${PROVIDER_DETECT[31]}"
  "antigravity|Google Antigravity|antigravity|${PROVIDER_DETECT[32]}"
)

for spec in "${SKILLS_AGENTS[@]}"; do
  IFS='|' read -r id label profile detect_spec <<EOF
$spec
EOF
  if want "$id" && detect_match "$detect_spec"; then
    install_via_skills "$id" "$label" "$profile"
  fi
done

# ── Generic fallback: npx skills auto-detect ───────────────────────────────
if [ "$SKIP_SKILLS" = 0 ] && [ ${#ONLY[@]} -eq 0 ] && [ "$DETECTED_COUNT" -eq 0 ]; then
  say "→ no agents detected — running npx skills auto-detect fallback"
  if ensure_node; then
    if try npx -y skills add "$REPO_URL"; then
      record_installed "skills-auto"
    else
      record_failed "skills-auto" "npx skills add (auto) failed"
    fi
  fi
  echo
fi

# ── --with-init: write per-project rule files ──────────────────────────────
if [ "$WITH_INIT" = 1 ]; then
  say "→ writing per-project rule files into $PWD (--with-init)"
  local_init_args=(".")
  [ "$DRY" = 1 ]   && local_init_args+=("--dry-run")
  [ "$FORCE" = 1 ] && local_init_args+=("--force")

  if [ "$DRY" = 1 ]; then
    note "  would run: uv run --project $INSTALL_DIR sentinel init ."
  else
    if uv run --project "$INSTALL_DIR" sentinel init "${local_init_args[@]}"; then
      record_installed "sentinel-init ($PWD)"
    else
      record_failed "sentinel-init" "sentinel init failed"
    fi
  fi
  echo
elif [ ${#INSTALLED_IDS[@]} -gt 0 ] || [ ${#SKIPPED_IDS[@]} -gt 0 ]; then
  note "  tip: re-run with --all (or --with-init) to also write per-project IDE rule files."
fi

# ── Summary ────────────────────────────────────────────────────────────────
echo
say "🛡  done"
echo

if [ ${#INSTALLED_IDS[@]} -gt 0 ]; then
  ok "  installed:"
  for a in "${INSTALLED_IDS[@]}"; do printf '    • %s\n' "$a"; done
fi

if [ ${#SKIPPED_IDS[@]} -gt 0 ]; then
  echo "  skipped:"
  i=0
  while [ $i -lt ${#SKIPPED_IDS[@]} ]; do
    printf '    • %s — %s\n' "${SKIPPED_IDS[$i]}" "${SKIPPED_WHY[$i]}"
    i=$((i + 1))
  done
fi

if [ ${#FAILED_IDS[@]} -gt 0 ]; then
  warn "  failed:"
  i=0
  while [ $i -lt ${#FAILED_IDS[@]} ]; do
    printf '    • %s — %s\n' "${FAILED_IDS[$i]}" "${FAILED_WHY[$i]}" >&2
    i=$((i + 1))
  done
fi

if [ ${#INSTALLED_IDS[@]} -eq 0 ] && [ ${#SKIPPED_IDS[@]} -eq 0 ] && [ ${#FAILED_IDS[@]} -eq 0 ]; then
  note "  nothing detected — run 'install.sh --list' for all supported agents"
  note "  or pass --only <agent> to force a specific target."
fi

echo
note "  start an audit: uv run --project \"$INSTALL_DIR\" sentinel audit ./"
note "  per-project setup: sentinel init"

# Exit non-zero only when every detected agent failed (and at least one was detected).
if [ "$DETECTED_COUNT" -gt 0 ] && [ ${#INSTALLED_IDS[@]} -eq 0 ] && [ ${#SKIPPED_IDS[@]} -eq 0 ]; then
  exit 1
fi
exit 0
