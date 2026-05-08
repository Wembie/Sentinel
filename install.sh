#!/usr/bin/env bash
# SENTINEL Installer — macOS / Linux / WSL / Git Bash
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/Wembie/Sentinel/main/install.sh | bash
#   bash install.sh [--dev] [--upgrade] [--uninstall]
#
# Options:
#   --dev        Clone repository and install in editable mode
#   --upgrade    Pull latest changes and re-sync dependencies
#   --uninstall  Remove SENTINEL installation
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
RESET="\033[0m"

# ─── flags ────────────────────────────────────────────────────────────────────

MODE="install"
for arg in "$@"; do
  case "$arg" in
    --dev)       MODE="dev" ;;
    --upgrade)   MODE="upgrade" ;;
    --uninstall) MODE="uninstall" ;;
    --help|-h)
      echo "Usage: install.sh [--dev] [--upgrade] [--uninstall]"
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

need_cmd() {
  if ! command -v "$1" &>/dev/null; then
    return 1
  fi
  return 0
}

detect_os() {
  case "$(uname -s)" in
    Linux*)   echo "linux" ;;
    Darwin*)  echo "macos" ;;
    MINGW*|CYGWIN*|MSYS*) echo "windows" ;;
    *)        echo "unknown" ;;
  esac
}

detect_arch() {
  case "$(uname -m)" in
    x86_64|amd64)  echo "x86_64" ;;
    aarch64|arm64) echo "aarch64" ;;
    *)             echo "unknown" ;;
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
  if need_cmd curl; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
  elif need_cmd wget; then
    wget -qO- https://astral.sh/uv/install.sh | sh
  else
    die "curl or wget required to install uv. Install one and retry."
  fi
  # Add uv to PATH for this session
  export PATH="$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
  if ! need_cmd uv; then
    die "uv installation succeeded but 'uv' not found on PATH. Add ~/.cargo/bin or ~/.local/bin to PATH."
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
  cat > "$wrapper" <<EOF
#!/usr/bin/env bash
exec uv run --project "$INSTALL_DIR" python -m sentinel.mcp "\$@"
EOF
  chmod +x "$wrapper"
  info "Wrapper written: $wrapper"
}

write_mcp_config() {
  local config_dir
  # Detect Claude Code config location
  if [[ -d "$HOME/.claude" ]]; then
    local example_path="$INSTALL_DIR/mcp.example.json"
    info "Claude Code detected. Add SENTINEL to your MCP config:"
    echo ""
    echo '  Global (~/.claude/settings.json → mcpServers section):'
    echo "    claude mcp add sentinel -- uv run --project \"$INSTALL_DIR\" python -m sentinel.mcp"
    echo ""
    echo '  Or project-level (.mcp.json in your repo root):'
    cat <<EOF
    {
      "mcpServers": {
        "sentinel": {
          "command": "uv",
          "args": ["run", "--project", "$INSTALL_DIR", "python", "-m", "sentinel.mcp"]
        }
      }
    }
EOF
    echo ""
  fi
}

validate_install() {
  info "Validating installation..."
  if uv run --project "$INSTALL_DIR" python -c "import sentinel; print('sentinel OK')" &>/dev/null; then
    info "Import check passed."
  else
    die "Import validation failed. Check 'uv run --project $INSTALL_DIR python -c \"import sentinel\"'"
  fi
}

# ─── uninstall ────────────────────────────────────────────────────────────────

do_uninstall() {
  bold "Uninstalling SENTINEL..."
  if [[ -d "$INSTALL_DIR" ]]; then
    rm -rf "$INSTALL_DIR"
    info "Removed $INSTALL_DIR"
  else
    warn "Installation directory not found: $INSTALL_DIR"
  fi
  local wrapper="$BIN_DIR/sentinel-mcp"
  if [[ -f "$wrapper" ]]; then
    rm -f "$wrapper"
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
  git -C "$INSTALL_DIR" pull --ff-only
  uv sync --project "$INSTALL_DIR"
  validate_install
  info "SENTINEL upgraded."
}

# ─── install ──────────────────────────────────────────────────────────────────

do_install() {
  local dev_mode="${1:-false}"
  bold "Installing SENTINEL..."

  local py_cmd
  py_cmd=$(check_python)
  info "Python: $("$py_cmd" --version)"

  install_uv

  if [[ "$dev_mode" == "true" ]]; then
    if need_cmd git; then
      if [[ -d "$INSTALL_DIR/.git" ]]; then
        warn "Git repo already exists at $INSTALL_DIR. Use --upgrade to update."
      else
        info "Cloning repository to $INSTALL_DIR..."
        git clone "$REPO_URL" "$INSTALL_DIR"
      fi
    else
      die "--dev mode requires git. Install git and retry."
    fi
  else
    if [[ -d "$INSTALL_DIR" ]]; then
      warn "Directory $INSTALL_DIR already exists. Use --upgrade or --uninstall first."
    else
      info "Downloading SENTINEL to $INSTALL_DIR..."
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

  info "Syncing dependencies..."
  uv sync --project "$INSTALL_DIR"

  ensure_bin_dir
  write_wrapper
  validate_install
  write_mcp_config

  echo ""
  bold "SENTINEL installed successfully!"
  echo ""
  echo "  Start MCP server:  sentinel-mcp"
  echo "  Run audit:         uv run --project \"$INSTALL_DIR\" sentinel audit ./my-project"
  echo "  List rules:        uv run --project \"$INSTALL_DIR\" sentinel rules"
  echo ""
}

# ─── dispatch ─────────────────────────────────────────────────────────────────

case "$MODE" in
  install)   do_install "false" ;;
  dev)       do_install "true" ;;
  upgrade)   do_upgrade ;;
  uninstall) do_uninstall ;;
esac
