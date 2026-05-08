<#
.SYNOPSIS
    SENTINEL Installer — Windows (PowerShell 5.1+)
.DESCRIPTION
    Installs SENTINEL, registers MCP servers, and optionally installs Claude Code hooks.
.PARAMETER Dev
    Clone repository and install in editable mode (requires git).
.PARAMETER Upgrade
    Pull latest changes and re-sync dependencies.
.PARAMETER Uninstall
    Remove SENTINEL installation.
.PARAMETER DryRun
    Print all actions without executing anything.
.PARAMETER List
    List detected agents and exit.
.PARAMETER NoMcp
    Skip MCP auto-registration.
.PARAMETER WithHooks
    Install Claude Code session hooks (auto-activates SENTINEL at session start).
.PARAMETER WithInit
    Run `sentinel init` in the current directory after install.
.PARAMETER All
    Enable WithHooks and MCP registration for all detected agents.
.PARAMETER Minimal
    Install package only; skip MCP registration, hooks, and init.
.PARAMETER Only
    Register with a specific agent only (e.g. -Only claude).
.EXAMPLE
    irm https://raw.githubusercontent.com/Wembie/Sentinel/main/install.ps1 | iex
    .\install.ps1 -DryRun -List
    .\install.ps1 -All
    .\install.ps1 -WithHooks
#>
param(
    [switch]$Dev,
    [switch]$Upgrade,
    [switch]$Uninstall,
    [switch]$DryRun,
    [switch]$List,
    [switch]$NoMcp,
    [switch]$WithHooks,
    [switch]$WithInit,
    [switch]$All,
    [switch]$Minimal,
    [string]$Only = ""
)

$ErrorActionPreference = "Stop"

# --all implies WithHooks
if ($All) { $WithHooks = $true }
# --minimal implies NoMcp
if ($Minimal) { $NoMcp = $true }

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
        Write-Warn "uv installed but not on PATH yet. Restart terminal or add ~/.cargo/bin to PATH."
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

    $extDirs = @(
        (Join-Path $HOME ".vscode\extensions"),
        (Join-Path $HOME ".cursor\extensions"),
        (Join-Path $HOME ".windsurf\extensions")
    )

    # ── Native CLI agents ──────────────────────────────────────────────────────

    # Claude Code
    if ((Test-Command "claude") -or (Test-Path (Join-Path $HOME ".claude"))) {
        $script:DetectedAgents.Add("claude:Claude Code")
    }

    # Gemini CLI
    if ((Test-Command "gemini") -or (Test-Path (Join-Path $HOME ".gemini"))) {
        $script:DetectedAgents.Add("gemini:Gemini CLI")
    }

    # OpenAI Codex CLI
    if ((Test-Command "codex") -or (Test-Path (Join-Path $HOME ".codex"))) {
        $script:DetectedAgents.Add("codex:Codex CLI")
    }

    # GitHub Copilot CLI
    if ((Test-Command "gh") -and (& gh extension list 2>$null | Select-String "gh-copilot")) {
        $script:DetectedAgents.Add("copilot-cli:GitHub Copilot CLI")
    }

    # Aider
    if (Test-Command "aider") {
        $script:DetectedAgents.Add("aider:Aider")
    }

    # v0 (Vercel)
    if (Test-Command "v0") {
        $script:DetectedAgents.Add("v0:v0")
    }

    # ── IDE editors ─────────────────────────────────────────────────────────────

    # Cursor
    if ((Test-Command "cursor") -or (Test-Path (Join-Path $HOME ".cursor"))) {
        $script:DetectedAgents.Add("cursor:Cursor")
    }

    # Windsurf
    $windsurfPaths = @(
        (Join-Path $HOME ".codeium\windsurf"),
        (Join-Path $HOME ".windsurf")
    )
    $windsurfFound = $false
    foreach ($p in $windsurfPaths) {
        if (Test-Path $p) { $windsurfFound = $true; break }
    }
    if ($windsurfFound -or (Test-Command "windsurf")) {
        $script:DetectedAgents.Add("windsurf:Windsurf")
    }

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

    # Sourcegraph Amp
    if ((Test-Command "amp") -or (Test-Path (Join-Path $HOME ".amp"))) {
        $script:DetectedAgents.Add("amp:Sourcegraph Amp")
    }

    # ── VS Code / Cursor extensions ──────────────────────────────────────────────

    # Cline
    $clineAdded = $false
    foreach ($extDir in $extDirs) {
        if (-not $clineAdded -and (Test-Path $extDir) -and (Get-ChildItem $extDir -EA SilentlyContinue | Where-Object { $_.Name -like "saoudrizwan.claude-dev*" })) {
            $script:DetectedAgents.Add("cline:Cline"); $clineAdded = $true
        }
    }

    # Continue
    $continueAdded = $false
    foreach ($extDir in $extDirs) {
        if (-not $continueAdded -and (Test-Path $extDir) -and (Get-ChildItem $extDir -EA SilentlyContinue | Where-Object { $_.Name -like "continue.continue*" })) {
            $script:DetectedAgents.Add("continue:Continue"); $continueAdded = $true
        }
    }

    # Roo
    $rooAdded = $false
    foreach ($extDir in $extDirs) {
        if (-not $rooAdded -and (Test-Path $extDir) -and (Get-ChildItem $extDir -EA SilentlyContinue | Where-Object { $_.Name -like "rooveterinaryinc.roo-cline*" })) {
            $script:DetectedAgents.Add("roo:Roo"); $rooAdded = $true
        }
    }

    # ── AI coding platforms ──────────────────────────────────────────────────────

    # OpenHands
    if ((Test-Command "openhands") -or (Test-Path (Join-Path $HOME ".openhands"))) {
        $script:DetectedAgents.Add("openhands:OpenHands")
    }

    # Devin
    if (Test-Path (Join-Path $HOME ".devin")) {
        $script:DetectedAgents.Add("devin:Devin")
    }

    # Kode
    if ((Test-Command "kode") -or (Test-Path (Join-Path $HOME ".kode"))) {
        $script:DetectedAgents.Add("kode:Kode")
    }

    # Aide
    if ((Test-Command "aide") -or (Test-Path (Join-Path $HOME ".aide"))) {
        $script:DetectedAgents.Add("aide:Aide")
    }

    if ($script:DetectedAgents.Count -eq 0) {
        Write-Warn "No AI coding agents detected."
        Write-Warn "Install MCP manually using mcp.example.json, or run: sentinel init"
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
    Write-Host "Supported: Claude Code, Gemini CLI, Codex CLI, Copilot CLI, Aider, v0," -ForegroundColor Cyan
    Write-Host "           Cursor, Windsurf, VS Code, JetBrains, Amp, Cline, Continue," -ForegroundColor Cyan
    Write-Host "           Roo, OpenHands, Devin, Kode, Aide — plus any skills-CLI-compatible agent." -ForegroundColor Cyan
}

# ─── MCP registration ─────────────────────────────────────────────────────────

function Register-Mcp {
    param([string]$InstallPath)
    if ($NoMcp) { return }
    if ($script:DetectedAgents.Count -eq 0) { Detect-Agents }

    $registered  = [System.Collections.Generic.List[string]]::new()
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
                } else { $manualAgents.Add($agentLabel) }
            }
            "gemini" {
                if (Test-Command "gemini") {
                    if ($DryRun) {
                        Write-Host "  [dry-run] gemini extensions install https://github.com/Wembie/Sentinel" -ForegroundColor Yellow
                        $registered.Add("$agentLabel (dry-run)")
                    } else {
                        try {
                            & gemini extensions install "https://github.com/Wembie/Sentinel" 2>$null
                            Write-Info "Gemini CLI: extension installed."
                            $registered.Add($agentLabel)
                        } catch {
                            Write-Warn "Gemini CLI: auto-install failed."
                            $manualAgents.Add($agentLabel)
                        }
                    }
                } else { $manualAgents.Add($agentLabel) }
            }
            default { $manualAgents.Add($agentLabel) }
        }
    }

    # Skills CLI fallback
    if (-not $Minimal -and -not $Only -and (Test-Command "npx")) {
        Write-Info "Running skills CLI registration (covers all skills-compatible agents)..."
        if ($DryRun) {
            Write-Host "  [dry-run] npx -y skills add https://github.com/Wembie/Sentinel" -ForegroundColor Yellow
        } else {
            try {
                npx -y skills add "https://github.com/Wembie/Sentinel" 2>$null
                Write-Info "Skills CLI: SENTINEL registered."
            } catch {
                Write-Warn "Skills CLI registration failed (non-fatal)."
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
        Write-Host "  Or run: sentinel init  (in any project root) to drop rule files." -ForegroundColor Cyan
    }
}

# ─── hooks installation ───────────────────────────────────────────────────────

function Install-Hooks {
    param([string]$InstallPath)
    $hooksInstaller = Join-Path $InstallPath "hooks\install.ps1"
    if (-not (Test-Path $hooksInstaller)) {
        Write-Warn "Hooks installer not found at $hooksInstaller — skipping."
        return
    }
    Write-Info "Installing Claude Code hooks..."
    if ($DryRun) {
        Write-Host "  [dry-run] & `"$hooksInstaller`" -DryRun" -ForegroundColor Yellow
    } else {
        try {
            & $hooksInstaller
        } catch {
            Write-Warn "Hooks installation failed (non-fatal): $_"
        }
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
    foreach ($f in @("sentinel-mcp.cmd", "sentinel-mcp.ps1")) {
        $p = Join-Path $BinDir $f
        if (Test-Path $p) {
            if ($DryRun) {
                Write-Host "  [dry-run] Remove-Item $p" -ForegroundColor Yellow
            } else {
                Remove-Item $p
                Write-Info "Removed $p"
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

    # Optional: install Claude Code hooks
    if ($WithHooks) {
        Install-Hooks -InstallPath $InstallDir
    }

    # Optional: run sentinel init in current directory
    if ($WithInit) {
        Write-Info "Running sentinel init in current directory..."
        if ($DryRun) {
            Write-Host "  [dry-run] uv run --project $InstallDir sentinel init ." -ForegroundColor Yellow
        } else {
            uv run --project $InstallDir sentinel init .
        }
    }

    Write-Host ""
    Write-Host "SENTINEL installed successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Start MCP server:    sentinel-mcp"
    Write-Host "  Run audit:           uv run --project `"$InstallDir`" sentinel audit .\"
    Write-Host "  List rules:          uv run --project `"$InstallDir`" sentinel rules"
    Write-Host "  Per-project setup:   uv run --project `"$InstallDir`" sentinel init"
    Write-Host "  Install hooks:       & `"$InstallDir\hooks\install.ps1`""
    Write-Host ""
}

# ─── dispatch ─────────────────────────────────────────────────────────────────

if      ($List)      { Invoke-List }
elseif  ($Uninstall) { Invoke-Uninstall }
elseif  ($Upgrade)   { Invoke-Upgrade }
elseif  ($Dev)       { Invoke-Install -DevMode $true }
else                 { Invoke-Install -DevMode $false }
