#!/usr/bin/env bash
# SENTINEL Installer — macOS / Linux / WSL / Git Bash
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/Wembie/Sentinel/main/install.sh | bash
#   bash install.sh [OPTIONS]
#
# Options:
#   --dev        Clone repository and install in editable mode
#   --upgrade    Pull latest changes and re-sync dependencies
#   --uninstall  Remove SENTINEL installation
#   --dry-run    Print all actions without executing anything
#   --list       List detected agents and exit
#   --no-mcp     Skip MCP auto-registration
#   --all        Register with all detected agents (default: auto)
#   --only <id>  Register with a specific agent only (e.g. --only claude)
#
# Environment overrides:
#   SENTINEL_HOME   Install directory (default: ~/.sentinel)
#   SENTINEL_BIN    Bin directory for sentinel-mcp wrapper (default: ~/.local/bin)

set -euo pipefail

# ─── configuration ────────────────────────────────────────────────────────────

REPO_URL="https://github.com/Wembie/Sentinel"
REPO_ARCHIVE="https://github.com/Wembie/Sentinel/archive/refs/heads/main.tar.gz"
INSTALL_DIR="${SENTINEL_HOME:-$HOME/.sentinel}"
BIN_DIR="${SENTINEL_BIN:-$HOME/.local/bin}"
MIN_PYTHON_MAJOR=3
MIN_PYTHON_MINOR=11
BOLD="\033[1m"
GREEN="\033[32m"
YELLOW="\033[33m"
RED="\033[31m"
CYAN="\033[36m"
RESET="\033[0m"

# ─── flags ────────────────────────────────────────────────────────────────────

MODE="install"
DRY_RUN=false
NO_MCP=false
ONLY_AGENT=""

for arg in "$@"; do
  case "$arg" in
    --dev)       MODE="dev" ;;
    --upgrade)   MODE="upgrade" ;;
    --uninstall) MODE="uninstall" ;;
    --dry-run)   DRY_RUN=true ;;
    --list)      MODE="list" ;;
    --no-mcp)    NO_MCP=true ;;
    --only)      shift; ONLY_AGENT="$1" ;;
    --help|-h)
      echo "Usage: install.sh [--dev] [--upgrade] [--uninstall] [--dry-run] [--list] [--no-mcp] [--only <agent>]"
      exit 0
      ;;
  esac
done

# ─── helpers ──────────────────────────────────────────────────────────────────

info()    { echo -e "${GREEN}[SENTINEL]${RESET} $*"; }
warn()    { echo -e "${YELLOW}[SENTINEL]${RESET} $*"; }
error()   { echo -e "${RED}[SENTINEL ERROR]${RESET} $*" >&2; }
die()     { error "$*"; exit 1; }
bold()    { echo -e "${BOLD}$*${RESET}"; }
cyan()    { echo -e "${CYAN}$*${RESET}"; }

run_cmd() {
  if [[ "$DRY_RUN" == "true" ]]; then
    echo -e "  ${YELLOW}[dry-run]${RESET} $*"
  else
    eval "$@"
  fi
}

need_cmd() {
  command -v "$1" &>/dev/null
}

detect_os() {
  case "$(uname -s)" in
    Linux*)   echo "linux" ;;
    Darwin*)  echo "macos" ;;
    MINGW*|CYGWIN*|MSYS*) echo "windows" ;;
    *)        echo "unknown" ;;
  esac
}

check_python() {
  local py_cmd=""
  for candidate in python3 python python3.11 python3.12 python3.13; do
    if need_cmd "$candidate"; then
      local ver
      ver=$("$candidate" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
      local major="${ver%%.*}"
      local minor="${ver##*.}"
      if [[ "$major" -gt "$MIN_PYTHON_MAJOR" ]] || \
         [[ "$major" -eq "$MIN_PYTHON_MAJOR" && "$minor" -ge "$MIN_PYTHON_MINOR" ]]; then
        py_cmd="$candidate"
        break
      fi
    fi
  done
  if [[ -z "$py_cmd" ]]; then
    die "Python ${MIN_PYTHON_MAJOR}.${MIN_PYTHON_MINOR}+ required. Install from https://python.org"
  fi
  echo "$py_cmd"
}

install_uv() {
  if need_cmd uv; then
    info "uv already installed: $(uv --version)"
    return
  fi
  info "Installing uv (Python package manager)..."
  if [[ "$DRY_RUN" == "true" ]]; then
    echo "  [dry-run] curl -LsSf https://astral.sh/uv/install.sh | sh"
    return
  fi
  if need_cmd curl; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
  elif need_cmd wget; then
    wget -qO- https://astral.sh/uv/install.sh | sh
  else
    die "curl or wget required to install uv. Install one and retry."
  fi
  export PATH="$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
  if ! need_cmd uv; then
    die "uv installed but not found on PATH. Add ~/.cargo/bin or ~/.local/bin to PATH."
  fi
  info "uv installed: $(uv --version)"
}

ensure_bin_dir() {
  mkdir -p "$BIN_DIR"
  if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    warn "$BIN_DIR is not on PATH. Add this to your shell profile:"
    echo "  export PATH=\"\$PATH:$BIN_DIR\""
  fi
}

write_wrapper() {
  local wrapper="$BIN_DIR/sentinel-mcp"
  if [[ "$DRY_RUN" == "true" ]]; then
    echo "  [dry-run] write $wrapper"
    return
  fi
  cat > "$wrapper" <<EOF
#!/usr/bin/env bash
exec uv run --project "$INSTALL_DIR" python -m sentinel.mcp "\$@"
EOF
  chmod +x "$wrapper"
  info "Wrapper written: $wrapper"
}

validate_install() {
  info "Validating installation..."
  if [[ "$DRY_RUN" == "true" ]]; then
    echo "  [dry-run] uv run --project $INSTALL_DIR python -c 'import sentinel'"
    return
  fi
  if uv run --project "$INSTALL_DIR" python -c "import sentinel; print('sentinel OK')" &>/dev/null; then
    info "Import check passed."
  else
    die "Import validation failed. Check: uv run --project $INSTALL_DIR python -c \"import sentinel\""
  fi
}

# ─── agent detection ──────────────────────────────────────────────────────────

DETECTED_AGENTS=()

detect_agents() {
  info "Scanning for AI coding agents..."
  DETECTED_AGENTS=()

  # Claude Code
  if need_cmd claude || [[ -d "$HOME/.claude" ]]; then
    DETECTED_AGENTS+=("claude:Claude Code")
  fi

  # Cursor
  if need_cmd cursor || [[ -d "$HOME/.cursor" ]]; then
    DETECTED_AGENTS+=("cursor:Cursor")
  fi

  # Windsurf
  if [[ -d "$HOME/.codeium/windsurf" ]] || [[ -d "$HOME/.windsurf" ]] || need_cmd windsurf; then
    DETECTED_AGENTS+=("windsurf:Windsurf")
  fi

  # VS Code
  if need_cmd code; then
    DETECTED_AGENTS+=("vscode:VS Code")
  fi

  # JetBrains (any IDE)
  local jb_roots=(
    "$HOME/.config/JetBrains"
    "$HOME/Library/Application Support/JetBrains"
    "${APPDATA:-}/JetBrains"
  )
  for jb_root in "${jb_roots[@]}"; do
    if [[ -d "$jb_root" ]]; then
      DETECTED_AGENTS+=("jetbrains:JetBrains")
      break
    fi
  done

  # Cline (VS Code extension)
  local ext_dirs=("$HOME/.vscode/extensions" "$HOME/.cursor/extensions" "$HOME/.windsurf/extensions")
  for ext_dir in "${ext_dirs[@]}"; do
    if [[ -d "$ext_dir" ]] && ls "$ext_dir" 2>/dev/null | grep -q "saoudrizwan.claude-dev"; then
      DETECTED_AGENTS+=("cline:Cline")
      break
    fi
  done

  # Continue (VS Code extension)
  for ext_dir in "${ext_dirs[@]}"; do
    if [[ -d "$ext_dir" ]] && ls "$ext_dir" 2>/dev/null | grep -q "continue.continue"; then
      DETECTED_AGENTS+=("continue:Continue")
      break
    fi
  done

  # Roo / Roo Cline
  for ext_dir in "${ext_dirs[@]}"; do
    if [[ -d "$ext_dir" ]] && ls "$ext_dir" 2>/dev/null | grep -q "rooveterinaryinc.roo-cline"; then
      DETECTED_AGENTS+=("roo:Roo")
      break
    fi
  done

  # OpenHands
  if need_cmd openhands || [[ -d "$HOME/.openhands" ]]; then
    DETECTED_AGENTS+=("openhands:OpenHands")
  fi

  # Codex CLI
  if need_cmd codex || [[ -d "$HOME/.codex" ]]; then
    DETECTED_AGENTS+=("codex:Codex")
  fi

  if [[ ${#DETECTED_AGENTS[@]} -eq 0 ]]; then
    warn "No AI coding agents detected. Configure MCP manually — see $INSTALL_DIR/mcp.example.json"
    return
  fi

  info "Detected agents:"
  for entry in "${DETECTED_AGENTS[@]}"; do
    echo "    ✓ ${entry##*:}"
  done
}

# ─── list mode ────────────────────────────────────────────────────────────────

do_list() {
  bold "SENTINEL — Agent Detection"
  echo ""
  detect_agents
  echo ""
  echo "Supported agents: Claude Code, Cursor, Windsurf, VS Code, JetBrains, Cline, Continue, Roo, OpenHands, Codex"
  echo "MCP config examples: $INSTALL_DIR/mcp.example.json (after install)"
}

# ─── MCP registration ─────────────────────────────────────────────────────────

register_mcp() {
  local install_dir="$1"
  [[ "$NO_MCP" == "true" ]] && return
  [[ ${#DETECTED_AGENTS[@]} -eq 0 ]] && { detect_agents; }

  local registered=()
  local manual_agents=()

  for entry in "${DETECTED_AGENTS[@]}"; do
    local agent_id="${entry%%:*}"
    local agent_label="${entry##*:}"

    # Filter to --only target if specified
    [[ -n "$ONLY_AGENT" && "$agent_id" != "$ONLY_AGENT" ]] && continue

    case "$agent_id" in
      claude)
        if need_cmd claude; then
          if [[ "$DRY_RUN" == "true" ]]; then
            echo "  [dry-run] claude mcp add sentinel -- uv run --project \"$install_dir\" python -m sentinel.mcp"
            registered+=("$agent_label (dry-run)")
          elif claude mcp add sentinel -- uv run --project "$install_dir" python -m sentinel.mcp 2>/dev/null; then
            info "Claude Code: MCP server registered."
            registered+=("$agent_label")
          else
            warn "Claude Code: auto-registration failed."
            manual_agents+=("$agent_label")
          fi
        else
          manual_agents+=("$agent_label")
        fi
        ;;
      *)
        manual_agents+=("$agent_label")
        ;;
    esac
  done

  if [[ ${#registered[@]} -gt 0 ]]; then
    echo ""
    info "Auto-registered: ${registered[*]}"
  fi

  if [[ ${#manual_agents[@]} -gt 0 ]]; then
    echo ""
    cyan "Manual MCP config needed for: ${manual_agents[*]}"
    echo ""
    echo "  Add to your editor's MCP server settings:"
    echo "  {"
    echo "    \"command\": \"uv\","
    echo "    \"args\": [\"run\", \"--project\", \"$install_dir\", \"python\", \"-m\", \"sentinel.mcp\"]"
    echo "  }"
    echo ""
    echo "  See $install_dir/mcp.example.json for editor-specific examples."
    echo "  Or run: sentinel init  (in any project root) to drop rule files for all detected editors."
  fi
}

# ─── uninstall ────────────────────────────────────────────────────────────────

do_uninstall() {
  bold "Uninstalling SENTINEL..."
  if [[ -d "$INSTALL_DIR" ]]; then
    run_cmd rm -rf "$INSTALL_DIR"
    info "Removed $INSTALL_DIR"
  else
    warn "Installation directory not found: $INSTALL_DIR"
  fi
  local wrapper="$BIN_DIR/sentinel-mcp"
  if [[ -f "$wrapper" ]]; then
    run_cmd rm -f "$wrapper"
    info "Removed $wrapper"
  fi
  info "SENTINEL uninstalled."
}

# ─── upgrade ──────────────────────────────────────────────────────────────────

do_upgrade() {
  if [[ ! -d "$INSTALL_DIR/.git" ]]; then
    die "Upgrade requires a git-cloned install (--dev). Use --uninstall then re-run installer."
  fi
  bold "Upgrading SENTINEL..."
  run_cmd git -C "$INSTALL_DIR" pull --ff-only
  run_cmd uv sync --project "$INSTALL_DIR"
  validate_install
  info "SENTINEL upgraded."
}

# ─── install ──────────────────────────────────────────────────────────────────

do_install() {
  local dev_mode="${1:-false}"
  bold "Installing SENTINEL..."
  [[ "$DRY_RUN" == "true" ]] && warn "Dry-run mode — no changes will be made."
  echo ""

  local py_cmd
  py_cmd=$(check_python)
  info "Python: $("$py_cmd" --version)"

  install_uv

  if [[ "$dev_mode" == "true" ]]; then
    if ! need_cmd git; then
      die "--dev mode requires git. Install git and retry."
    fi
    if [[ -d "$INSTALL_DIR/.git" ]]; then
      warn "Git repo already exists at $INSTALL_DIR. Use --upgrade to update."
    else
      info "Cloning repository to $INSTALL_DIR..."
      run_cmd git clone "$REPO_URL" "$INSTALL_DIR"
    fi
  else
    if [[ -d "$INSTALL_DIR" ]]; then
      warn "Directory $INSTALL_DIR already exists. Use --upgrade or --uninstall first."
    else
      info "Downloading SENTINEL to $INSTALL_DIR..."
      if [[ "$DRY_RUN" == "true" ]]; then
        echo "  [dry-run] download $REPO_ARCHIVE → $INSTALL_DIR"
      else
        mkdir -p "$INSTALL_DIR"
        if need_cmd curl; then
          curl -fsSL "$REPO_ARCHIVE" | tar -xz --strip-components=1 -C "$INSTALL_DIR"
        elif need_cmd wget; then
          wget -qO- "$REPO_ARCHIVE" | tar -xz --strip-components=1 -C "$INSTALL_DIR"
        else
          die "curl or wget required."
        fi
      fi
    fi
  fi

  info "Syncing dependencies..."
  run_cmd uv sync --project "$INSTALL_DIR"

  ensure_bin_dir
  write_wrapper
  validate_install

  detect_agents
  register_mcp "$INSTALL_DIR"

  echo ""
  bold "SENTINEL installed successfully!"
  echo ""
  echo -e "  ${GREEN}Start MCP server:${RESET}  sentinel-mcp"
  echo -e "  ${GREEN}Run audit:        ${RESET}  uv run --project \"$INSTALL_DIR\" sentinel audit ./my-project"
  echo -e "  ${GREEN}List rules:       ${RESET}  uv run --project \"$INSTALL_DIR\" sentinel rules"
  echo -e "  ${GREEN}Per-project setup:${RESET}  uv run --project \"$INSTALL_DIR\" sentinel init"
  echo ""
}

# ─── dispatch ─────────────────────────────────────────────────────────────────

case "$MODE" in
  install)   do_install "false" ;;
  dev)       do_install "true" ;;
  upgrade)   do_upgrade ;;
  uninstall) do_uninstall ;;
  list)      do_list ;;
esac
