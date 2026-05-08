# SENTINEL Installer — Windows (PowerShell 5.1+)
# Usage:
#   irm https://raw.githubusercontent.com/Wembie/Sentinel/main/install.ps1 | iex
#   .\install.ps1 [-Dev] [-Upgrade] [-Uninstall]
#
# Options:
#   -Dev        Clone repository and install in editable mode (requires git)
#   -Upgrade    Pull latest changes and re-sync dependencies
#   -Uninstall  Remove SENTINEL installation
#
# Environment overrides:
#   $env:SENTINEL_HOME   Install directory (default: $HOME\.sentinel)
#   $env:SENTINEL_BIN    Bin directory      (default: $HOME\.local\bin)

param(
    [switch]$Dev,
    [switch]$Upgrade,
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"

# ─── configuration ────────────────────────────────────────────────────────────

$RepoUrl      = "https://github.com/Wembie/Sentinel"
$RepoArchive  = "https://github.com/Wembie/Sentinel/archive/refs/heads/main.zip"
$InstallDir   = if ($env:SENTINEL_HOME) { $env:SENTINEL_HOME } else { Join-Path $HOME ".sentinel" }
$BinDir       = if ($env:SENTINEL_BIN)  { $env:SENTINEL_BIN  } else { Join-Path $HOME ".local\bin" }
$MinPyMajor   = 3
$MinPyMinor   = 11

# ─── helpers ──────────────────────────────────────────────────────────────────

function Write-Info  { param([string]$Msg) Write-Host "[SENTINEL] $Msg" -ForegroundColor Green  }
function Write-Warn  { param([string]$Msg) Write-Host "[SENTINEL] $Msg" -ForegroundColor Yellow }
function Write-Err   { param([string]$Msg) Write-Host "[SENTINEL ERROR] $Msg" -ForegroundColor Red }
function Fail        { param([string]$Msg) Write-Err $Msg; exit 1 }

function Test-Command {
    param([string]$Cmd)
    $null = Get-Command $Cmd -ErrorAction SilentlyContinue
    return $?
}

function Get-PythonCmd {
    $candidates = @("python", "python3", "py")
    foreach ($candidate in $candidates) {
        if (Test-Command $candidate) {
            $ver = & $candidate -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
            if ($ver -match "^(\d+)\.(\d+)$") {
                $major = [int]$Matches[1]
                $minor = [int]$Matches[2]
                if ($major -gt $MinPyMajor -or ($major -eq $MinPyMajor -and $minor -ge $MinPyMinor)) {
                    return $candidate
                }
            }
        }
    }
    Fail "Python $MinPyMajor.$MinPyMinor+ required. Download from https://python.org"
}

function Install-Uv {
    if (Test-Command "uv") {
        Write-Info "uv already installed: $(uv --version)"
        return
    }
    Write-Info "Installing uv (Python package manager)..."
    try {
        $uvInstall = (Invoke-WebRequest -Uri "https://astral.sh/uv/install.ps1" -UseBasicParsing).Content
        Invoke-Expression $uvInstall
    } catch {
        Fail "Failed to install uv: $_`nInstall manually from https://docs.astral.sh/uv/getting-started/installation/"
    }
    # Refresh PATH for current session
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "User") + ";" + $env:PATH
    if (-not (Test-Command "uv")) {
        Write-Warn "uv installed but not on PATH yet. You may need to restart your terminal."
        Write-Warn "Add '$env:USERPROFILE\.cargo\bin' or '$env:USERPROFILE\.local\bin' to PATH."
    } else {
        Write-Info "uv installed: $(uv --version)"
    }
}

function Ensure-BinDir {
    if (-not (Test-Path $BinDir)) {
        New-Item -ItemType Directory -Path $BinDir -Force | Out-Null
    }
    $userPath = [System.Environment]::GetEnvironmentVariable("PATH", "User")
    if ($userPath -notlike "*$BinDir*") {
        Write-Warn "$BinDir is not on PATH. Adding permanently..."
        [System.Environment]::SetEnvironmentVariable(
            "PATH",
            "$userPath;$BinDir",
            "User"
        )
        $env:PATH = "$env:PATH;$BinDir"
        Write-Info "PATH updated. Changes take effect in new terminal sessions."
    }
}

function Write-Wrapper {
    $wrapperPath = Join-Path $BinDir "sentinel-mcp.cmd"
    $content = "@echo off`r`nuv run --project `"$InstallDir`" python -m sentinel.mcp %*"
    Set-Content -Path $wrapperPath -Value $content -Encoding ASCII
    Write-Info "Wrapper written: $wrapperPath"

    # Also write a PowerShell shim
    $ps1Path = Join-Path $BinDir "sentinel-mcp.ps1"
    Set-Content -Path $ps1Path -Value "uv run --project `"$InstallDir`" python -m sentinel.mcp @args" -Encoding UTF8
    Write-Info "PowerShell shim: $ps1Path"
}

function Write-McpConfig {
    if (Test-Path (Join-Path $HOME ".claude")) {
        Write-Info "Claude Code detected. Add SENTINEL to your MCP config:"
        Write-Host ""
        Write-Host "  Global (run in terminal):" -ForegroundColor Cyan
        Write-Host "    claude mcp add sentinel -- uv run --project `"$InstallDir`" python -m sentinel.mcp"
        Write-Host ""
        Write-Host "  Or project-level (.mcp.json in your repo root):" -ForegroundColor Cyan
        Write-Host @"
    {
      "mcpServers": {
        "sentinel": {
          "command": "uv",
          "args": ["run", "--project", "$($InstallDir.Replace('\','\\'))", "python", "-m", "sentinel.mcp"]
        }
      }
    }
"@
        Write-Host ""
    }
}

function Test-Install {
    Write-Info "Validating installation..."
    $result = uv run --project $InstallDir python -c "import sentinel; print('sentinel OK')" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Fail "Import validation failed: $result"
    }
    Write-Info "Import check passed."
}

# ─── uninstall ────────────────────────────────────────────────────────────────

function Invoke-Uninstall {
    Write-Host "Uninstalling SENTINEL..." -ForegroundColor Bold
    if (Test-Path $InstallDir) {
        Remove-Item -Recurse -Force $InstallDir
        Write-Info "Removed $InstallDir"
    } else {
        Write-Warn "Installation directory not found: $InstallDir"
    }
    $wrapperCmd = Join-Path $BinDir "sentinel-mcp.cmd"
    $wrapperPs1 = Join-Path $BinDir "sentinel-mcp.ps1"
    foreach ($f in @($wrapperCmd, $wrapperPs1)) {
        if (Test-Path $f) { Remove-Item $f; Write-Info "Removed $f" }
    }
    Write-Info "SENTINEL uninstalled."
}

# ─── upgrade ──────────────────────────────────────────────────────────────────

function Invoke-Upgrade {
    if (-not (Test-Path (Join-Path $InstallDir ".git"))) {
        Fail "Upgrade requires a git-cloned install (-Dev). Use -Uninstall then re-run."
    }
    Write-Host "Upgrading SENTINEL..." -ForegroundColor Cyan
    git -C $InstallDir pull --ff-only
    uv sync --project $InstallDir
    Test-Install
    Write-Info "SENTINEL upgraded."
}

# ─── install ──────────────────────────────────────────────────────────────────

function Invoke-Install {
    param([bool]$DevMode = $false)

    Write-Host "Installing SENTINEL..." -ForegroundColor Cyan

    $pyCmd = Get-PythonCmd
    Write-Info "Python: $(& $pyCmd --version)"

    Install-Uv

    if ($DevMode) {
        if (-not (Test-Command "git")) {
            Fail "-Dev mode requires git. Install from https://git-scm.com"
        }
        if (Test-Path (Join-Path $InstallDir ".git")) {
            Write-Warn "Git repo already exists at $InstallDir. Use -Upgrade to update."
        } else {
            Write-Info "Cloning repository to $InstallDir..."
            git clone $RepoUrl $InstallDir
        }
    } else {
        if (Test-Path $InstallDir) {
            Write-Warn "$InstallDir already exists. Use -Upgrade or -Uninstall first."
        } else {
            Write-Info "Downloading SENTINEL to $InstallDir..."
            New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
            $zipPath = Join-Path $env:TEMP "sentinel-main.zip"
            try {
                Invoke-WebRequest -Uri $RepoArchive -OutFile $zipPath -UseBasicParsing
                Expand-Archive -Path $zipPath -DestinationPath $env:TEMP -Force
                $extracted = Join-Path $env:TEMP "Sentinel-main"
                Copy-Item -Recurse -Force "$extracted\*" $InstallDir
                Remove-Item $zipPath, $extracted -Recurse -Force -ErrorAction SilentlyContinue
            } catch {
                Fail "Download failed: $_"
            }
        }
    }

    Write-Info "Syncing dependencies..."
    uv sync --project $InstallDir

    Ensure-BinDir
    Write-Wrapper
    Test-Install
    Write-McpConfig

    Write-Host ""
    Write-Host "SENTINEL installed successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Start MCP server:  sentinel-mcp"
    Write-Host "  Run audit:         uv run --project `"$InstallDir`" sentinel audit .\my-project"
    Write-Host "  List rules:        uv run --project `"$InstallDir`" sentinel rules"
    Write-Host ""
}

# ─── dispatch ─────────────────────────────────────────────────────────────────

if ($Uninstall) { Invoke-Uninstall }
elseif ($Upgrade) { Invoke-Upgrade }
elseif ($Dev) { Invoke-Install -DevMode $true }
else { Invoke-Install -DevMode $false }
