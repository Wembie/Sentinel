# SENTINEL Installer — Windows (PowerShell 5.1+)
# Usage:
#   irm https://raw.githubusercontent.com/Wembie/Sentinel/main/install.ps1 | iex
#   .\install.ps1 [-Dev] [-Upgrade] [-Uninstall] [-DryRun] [-List] [-NoMcp] [-Only <agent>]
#
# Options:
#   -Dev        Clone repository and install in editable mode (requires git)
#   -Upgrade    Pull latest changes and re-sync dependencies
#   -Uninstall  Remove SENTINEL installation
#   -DryRun     Print all actions without executing anything
#   -List       List detected agents and exit
#   -NoMcp      Skip MCP auto-registration
#   -Only <id>  Register with a specific agent only (e.g. -Only claude)
#
# Environment overrides:
#   $env:SENTINEL_HOME   Install directory (default: $HOME\.sentinel)
#   $env:SENTINEL_BIN    Bin directory      (default: $HOME\.local\bin)

param(
    [switch]$Dev,
    [switch]$Upgrade,
    [switch]$Uninstall,
    [switch]$DryRun,
    [switch]$List,
    [switch]$NoMcp,
    [string]$Only = ""
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
function Write-Cyan  { param([string]$Msg) Write-Host $Msg -ForegroundColor Cyan }
function Fail        { param([string]$Msg) Write-Err $Msg; exit 1 }

function Invoke-Cmd {
    param([string]$Cmd, [string]$Desc = "")
    if ($DryRun) {
        Write-Host "  [dry-run] $Cmd" -ForegroundColor Yellow
    } else {
        Invoke-Expression $Cmd
    }
}

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
    if ($DryRun) {
        Write-Host "  [dry-run] Invoke-WebRequest https://astral.sh/uv/install.ps1 | iex" -ForegroundColor Yellow
        return
    }
    try {
        $uvInstall = (Invoke-WebRequest -Uri "https://astral.sh/uv/install.ps1" -UseBasicParsing).Content
        Invoke-Expression $uvInstall
    } catch {
        Fail "Failed to install uv: $_`nInstall manually from https://docs.astral.sh/uv/getting-started/installation/"
    }
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
        [System.Environment]::SetEnvironmentVariable("PATH", "$userPath;$BinDir", "User")
        $env:PATH = "$env:PATH;$BinDir"
        Write-Info "PATH updated. Changes take effect in new terminal sessions."
    }
}

function Write-Wrapper {
    if ($DryRun) {
        Write-Host "  [dry-run] write sentinel-mcp.cmd and sentinel-mcp.ps1 to $BinDir" -ForegroundColor Yellow
        return
    }
    $wrapperPath = Join-Path $BinDir "sentinel-mcp.cmd"
    $content = "@echo off`r`nuv run --project `"$InstallDir`" python -m sentinel.mcp %*"
    Set-Content -Path $wrapperPath -Value $content -Encoding ASCII
    Write-Info "Wrapper written: $wrapperPath"

    $ps1Path = Join-Path $BinDir "sentinel-mcp.ps1"
    Set-Content -Path $ps1Path -Value "uv run --project `"$InstallDir`" python -m sentinel.mcp @args" -Encoding UTF8
    Write-Info "PowerShell shim: $ps1Path"
}

function Test-Install {
    Write-Info "Validating installation..."
    if ($DryRun) {
        Write-Host "  [dry-run] uv run --project $InstallDir python -c 'import sentinel'" -ForegroundColor Yellow
        return
    }
    $result = uv run --project $InstallDir python -c "import sentinel; print('sentinel OK')" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Fail "Import validation failed: $result"
    }
    Write-Info "Import check passed."
}

# ─── agent detection ──────────────────────────────────────────────────────────

$script:DetectedAgents = [System.Collections.Generic.List[string]]::new()

function Detect-Agents {
    Write-Info "Scanning for AI coding agents..."
    $script:DetectedAgents.Clear()

    # Claude Code
    if ((Test-Command "claude") -or (Test-Path (Join-Path $HOME ".claude"))) {
        $script:DetectedAgents.Add("claude:Claude Code")
    }

    # Cursor
    if ((Test-Command "cursor") -or (Test-Path (Join-Path $HOME ".cursor"))) {
        $script:DetectedAgents.Add("cursor:Cursor")
    }

    # Windsurf
    $windsurfPaths = @(
        (Join-Path $HOME ".codeium\windsurf"),
        (Join-Path $HOME ".windsurf")
    )
    foreach ($p in $windsurfPaths) {
        if (Test-Path $p) {
            $script:DetectedAgents.Add("windsurf:Windsurf")
            break
        }
    }
    if (Test-Command "windsurf") { $script:DetectedAgents.Add("windsurf:Windsurf") }

    # VS Code
    if (Test-Command "code") {
        $script:DetectedAgents.Add("vscode:VS Code")
    }

    # JetBrains
    $jbPaths = @(
        (Join-Path $env:APPDATA "JetBrains"),
        (Join-Path $HOME ".config\JetBrains")
    )
    foreach ($jbPath in $jbPaths) {
        if (Test-Path $jbPath) {
            $script:DetectedAgents.Add("jetbrains:JetBrains")
            break
        }
    }

    # Cline (VS Code extension)
    $extDirs = @(
        (Join-Path $HOME ".vscode\extensions"),
        (Join-Path $HOME ".cursor\extensions")
    )
    foreach ($extDir in $extDirs) {
        if ((Test-Path $extDir) -and (Get-ChildItem $extDir -ErrorAction SilentlyContinue | Where-Object { $_.Name -like "saoudrizwan.claude-dev*" })) {
            $script:DetectedAgents.Add("cline:Cline")
            break
        }
    }

    # Continue
    foreach ($extDir in $extDirs) {
        if ((Test-Path $extDir) -and (Get-ChildItem $extDir -ErrorAction SilentlyContinue | Where-Object { $_.Name -like "continue.continue*" })) {
            $script:DetectedAgents.Add("continue:Continue")
            break
        }
    }

    # Roo
    foreach ($extDir in $extDirs) {
        if ((Test-Path $extDir) -and (Get-ChildItem $extDir -ErrorAction SilentlyContinue | Where-Object { $_.Name -like "rooveterinaryinc.roo-cline*" })) {
            $script:DetectedAgents.Add("roo:Roo")
            break
        }
    }

    # OpenHands
    if ((Test-Command "openhands") -or (Test-Path (Join-Path $HOME ".openhands"))) {
        $script:DetectedAgents.Add("openhands:OpenHands")
    }

    # Codex
    if ((Test-Command "codex") -or (Test-Path (Join-Path $HOME ".codex"))) {
        $script:DetectedAgents.Add("codex:Codex")
    }

    if ($script:DetectedAgents.Count -eq 0) {
        Write-Warn "No AI coding agents detected. Configure MCP manually — see $InstallDir\mcp.example.json"
        return
    }

    Write-Info "Detected agents:"
    foreach ($entry in $script:DetectedAgents) {
        $label = $entry.Split(":")[1]
        Write-Host "    OK $label" -ForegroundColor Green
    }
}

# ─── list mode ────────────────────────────────────────────────────────────────

function Invoke-List {
    Write-Host "SENTINEL — Agent Detection" -ForegroundColor Cyan
    Write-Host ""
    Detect-Agents
    Write-Host ""
    Write-Host "Supported: Claude Code, Cursor, Windsurf, VS Code, JetBrains, Cline, Continue, Roo, OpenHands, Codex"
    Write-Host "MCP examples: $InstallDir\mcp.example.json (after install)"
}

# ─── MCP registration ─────────────────────────────────────────────────────────

function Register-Mcp {
    param([string]$InstallPath)
    if ($NoMcp) { return }
    if ($script:DetectedAgents.Count -eq 0) { Detect-Agents }

    $registered = [System.Collections.Generic.List[string]]::new()
    $manualAgents = [System.Collections.Generic.List[string]]::new()

    foreach ($entry in $script:DetectedAgents) {
        $agentId    = $entry.Split(":")[0]
        $agentLabel = $entry.Split(":")[1]

        if ($Only -and $agentId -ne $Only) { continue }

        switch ($agentId) {
            "claude" {
                if (Test-Command "claude") {
                    if ($DryRun) {
                        Write-Host "  [dry-run] claude mcp add sentinel -- uv run --project `"$InstallPath`" python -m sentinel.mcp" -ForegroundColor Yellow
                        $registered.Add("$agentLabel (dry-run)")
                    } else {
                        try {
                            & claude mcp add sentinel -- uv run --project "$InstallPath" python -m sentinel.mcp 2>$null
                            Write-Info "Claude Code: MCP server registered."
                            $registered.Add($agentLabel)
                        } catch {
                            Write-Warn "Claude Code: auto-registration failed."
                            $manualAgents.Add($agentLabel)
                        }
                    }
                } else {
                    $manualAgents.Add($agentLabel)
                }
            }
            default {
                $manualAgents.Add($agentLabel)
            }
        }
    }

    if ($registered.Count -gt 0) {
        Write-Host ""
        Write-Info "Auto-registered: $($registered -join ', ')"
    }

    if ($manualAgents.Count -gt 0) {
        Write-Host ""
        Write-Cyan "Manual MCP config needed for: $($manualAgents -join ', ')"
        Write-Host ""
        Write-Host "  Add to your editor's MCP server settings:" -ForegroundColor Cyan
        Write-Host @"
    {
      "command": "uv",
      "args": ["run", "--project", "$($InstallPath.Replace('\','\\'))", "python", "-m", "sentinel.mcp"]
    }
"@
        Write-Host ""
        Write-Host "  See $InstallPath\mcp.example.json for editor-specific examples." -ForegroundColor Cyan
        Write-Host "  Or run: sentinel init  (in any project root) to drop rule files for all detected editors." -ForegroundColor Cyan
    }
}

# ─── uninstall ────────────────────────────────────────────────────────────────

function Invoke-Uninstall {
    Write-Host "Uninstalling SENTINEL..." -ForegroundColor Cyan
    if (Test-Path $InstallDir) {
        if ($DryRun) {
            Write-Host "  [dry-run] Remove-Item -Recurse -Force $InstallDir" -ForegroundColor Yellow
        } else {
            Remove-Item -Recurse -Force $InstallDir
            Write-Info "Removed $InstallDir"
        }
    } else {
        Write-Warn "Installation directory not found: $InstallDir"
    }
    $wrapperCmd = Join-Path $BinDir "sentinel-mcp.cmd"
    $wrapperPs1 = Join-Path $BinDir "sentinel-mcp.ps1"
    foreach ($f in @($wrapperCmd, $wrapperPs1)) {
        if (Test-Path $f) {
            if ($DryRun) {
                Write-Host "  [dry-run] Remove-Item $f" -ForegroundColor Yellow
            } else {
                Remove-Item $f
                Write-Info "Removed $f"
            }
        }
    }
    Write-Info "SENTINEL uninstalled."
}

# ─── upgrade ──────────────────────────────────────────────────────────────────

function Invoke-Upgrade {
    if (-not (Test-Path (Join-Path $InstallDir ".git"))) {
        Fail "Upgrade requires a git-cloned install (-Dev). Use -Uninstall then re-run."
    }
    Write-Host "Upgrading SENTINEL..." -ForegroundColor Cyan
    if ($DryRun) {
        Write-Host "  [dry-run] git -C $InstallDir pull --ff-only" -ForegroundColor Yellow
        Write-Host "  [dry-run] uv sync --project $InstallDir" -ForegroundColor Yellow
    } else {
        git -C $InstallDir pull --ff-only
        uv sync --project $InstallDir
    }
    Test-Install
    Write-Info "SENTINEL upgraded."
}

# ─── install ──────────────────────────────────────────────────────────────────

function Invoke-Install {
    param([bool]$DevMode = $false)

    Write-Host "Installing SENTINEL..." -ForegroundColor Cyan
    if ($DryRun) { Write-Warn "Dry-run mode — no changes will be made." }
    Write-Host ""

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
            if ($DryRun) {
                Write-Host "  [dry-run] git clone $RepoUrl $InstallDir" -ForegroundColor Yellow
            } else {
                git clone $RepoUrl $InstallDir
            }
        }
    } else {
        if (Test-Path $InstallDir) {
            Write-Warn "$InstallDir already exists. Use -Upgrade or -Uninstall first."
        } else {
            Write-Info "Downloading SENTINEL to $InstallDir..."
            if ($DryRun) {
                Write-Host "  [dry-run] download $RepoArchive -> $InstallDir" -ForegroundColor Yellow
            } else {
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
    }

    Write-Info "Syncing dependencies..."
    if ($DryRun) {
        Write-Host "  [dry-run] uv sync --project $InstallDir" -ForegroundColor Yellow
    } else {
        uv sync --project $InstallDir
    }

    Ensure-BinDir
    Write-Wrapper
    Test-Install

    Detect-Agents
    Register-Mcp -InstallPath $InstallDir

    Write-Host ""
    Write-Host "SENTINEL installed successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Start MCP server:   sentinel-mcp"
    Write-Host "  Run audit:          uv run --project `"$InstallDir`" sentinel audit .\my-project"
    Write-Host "  List rules:         uv run --project `"$InstallDir`" sentinel rules"
    Write-Host "  Per-project setup:  uv run --project `"$InstallDir`" sentinel init"
    Write-Host ""
}

# ─── dispatch ─────────────────────────────────────────────────────────────────

if      ($List)      { Invoke-List }
elseif  ($Uninstall) { Invoke-Uninstall }
elseif  ($Upgrade)   { Invoke-Upgrade }
elseif  ($Dev)       { Invoke-Install -DevMode $true }
else                 { Invoke-Install -DevMode $false }
