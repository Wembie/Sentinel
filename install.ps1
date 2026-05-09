<#
.SYNOPSIS
    SENTINEL Installer — Windows (PowerShell 5.1+)
.DESCRIPTION
    Detects AI coding agents on your machine and registers SENTINEL as an MCP
    server for each one. Safe to re-run — idempotent per agent.
.EXAMPLE
    irm https://raw.githubusercontent.com/Wembie/Sentinel/main/install.ps1 | iex
    .\install.ps1 -DryRun -List
    .\install.ps1 -All
    .\install.ps1 -Only claude
#>
param(
    [switch]$Dev,
    [switch]$Upgrade,
    [switch]$Uninstall,
    [switch]$DryRun,
    [switch]$Force,
    [switch]$SkipSkills,
    [switch]$WithHooks,
    [switch]$WithInit,
    [switch]$All,
    [switch]$Minimal,
    [switch]$List,
    [switch]$NoColor,
    [string[]]$Only = @()
)

$ErrorActionPreference = "Stop"

# ── Constants ──────────────────────────────────────────────────────────────
$Repo        = "Wembie/Sentinel"
$RepoUrl     = "https://github.com/$Repo"
$RepoArchive = "https://github.com/$Repo/archive/refs/heads/main.zip"
$InstallDir  = if ($env:SENTINEL_HOME) { $env:SENTINEL_HOME } else { Join-Path $HOME ".sentinel" }
$BinDir      = if ($env:SENTINEL_BIN)  { $env:SENTINEL_BIN  } else { Join-Path $HOME ".local\bin" }
$MinPyMajor  = 3
$MinPyMinor  = 11

# ── Flag resolution ────────────────────────────────────────────────────────
if ($All -and $Minimal) { Write-Error "error: -All and -Minimal are mutually exclusive"; exit 2 }
if ($All)     { $WithHooks = $true; $WithInit = $true }
if ($Minimal) { $WithHooks = $false; $WithInit = $false; $SkipSkills = $true }
# Default: WithHooks ON (matches Caveman pattern)
if (-not $Minimal -and -not $WithHooks) { $WithHooks = $true }

# ── Result trackers ────────────────────────────────────────────────────────
$InstalledIds  = [System.Collections.Generic.List[string]]::new()
$SkippedIds    = [System.Collections.Generic.List[string]]::new()
$SkippedWhy    = [System.Collections.Generic.List[string]]::new()
$FailedIds     = [System.Collections.Generic.List[string]]::new()
$FailedWhy     = [System.Collections.Generic.List[string]]::new()
$DetectedCount = 0

# ── Color helpers ──────────────────────────────────────────────────────────
function Write-Say  { param([string]$M) Write-Host $M -ForegroundColor Blue }
function Write-Note { param([string]$M) Write-Host $M -ForegroundColor DarkGray }
function Write-Warn { param([string]$M) Write-Host $M -ForegroundColor Yellow }
function Write-Err  { param([string]$M) Write-Host $M -ForegroundColor Red }
function Write-Ok   { param([string]$M) Write-Host $M -ForegroundColor Green }

function Invoke-Cmd {
    param([string]$Display, [scriptblock]$Action)
    if ($DryRun) { Write-Note "  would run: $Display" }
    else { Write-Host "  $ $Display"; & $Action }
}

# ── Helpers ────────────────────────────────────────────────────────────────
function Test-Want {
    param([string]$Id)
    if ($Only.Count -eq 0) { return $true }
    return $Only -contains $Id
}

function Test-Cmd {
    param([string]$Cmd)
    return ($null -ne (Get-Command $Cmd -ErrorAction SilentlyContinue))
}

function Test-NodeNpx {
    if ((Test-Cmd "node") -and (Test-Cmd "npx")) { return $true }
    Write-Warn "  node + npx required — install Node.js (https://nodejs.org) and re-run."
    return $false
}

function Add-Installed { param([string]$Id) $InstalledIds.Add($Id) }
function Add-Skipped   { param([string]$Id, [string]$Why) $SkippedIds.Add($Id); $SkippedWhy.Add($Why) }
function Add-Failed    { param([string]$Id, [string]$Why) $FailedIds.Add($Id); $FailedWhy.Add($Why) }

# ── Detection helpers ──────────────────────────────────────────────────────
function Test-VSCodeExt {
    param([string]$Needle)
    $roots = @(
        (Join-Path $HOME ".vscode\extensions"),
        (Join-Path $HOME ".cursor\extensions"),
        (Join-Path $HOME ".windsurf\extensions")
    )
    foreach ($r in $roots) {
        if ((Test-Path $r) -and (Get-ChildItem $r -EA SilentlyContinue | Where-Object { $_.Name -ilike "*$Needle*" })) {
            return $true
        }
    }
    return $false
}

function Test-JetbrainsPlugin {
    param([string]$Needle)
    $roots = @(
        (Join-Path $env:APPDATA "JetBrains"),
        (Join-Path $HOME ".config\JetBrains")
    )
    foreach ($r in $roots) {
        if ((Test-Path $r) -and (Get-ChildItem $r -Recurse -Depth 4 -Directory -EA SilentlyContinue | Where-Object { $_.Name -ilike "*$Needle*" })) {
            return $true
        }
    }
    return $false
}

# Parse a detection spec "command:foo||dir:~/.x" and return true if any clause matches.
function Test-DetectMatch {
    param([string]$Spec)
    $clauses = $Spec -split '\|\|'
    foreach ($clause in $clauses) {
        $clause = $clause.Trim()
        if ($clause -match '^command:(.+)$') {
            if (Test-Cmd $Matches[1]) { return $true }
        } elseif ($clause -match '^dir:(.+)$') {
            $expanded = $Matches[1] -replace '^\$HOME', $HOME
            if (Test-Path $expanded -PathType Container) { return $true }
        } elseif ($clause -match '^file:(.+)$') {
            $expanded = $Matches[1] -replace '^\$HOME', $HOME
            if (Test-Path $expanded -PathType Leaf) { return $true }
        } elseif ($clause -match '^vscode-ext:(.+)$') {
            if (Test-VSCodeExt $Matches[1]) { return $true }
        } elseif ($clause -match '^jetbrains-plugin:(.+)$') {
            if (Test-JetbrainsPlugin $Matches[1]) { return $true }
        }
    }
    return $false
}

# ── Provider matrix ────────────────────────────────────────────────────────
$Providers = @(
    # id, label, skills-profile, detect-spec
    [pscustomobject]@{ Id="claude";      Label="Claude Code";          Profile="";              Detect="command:claude||dir:$HOME\.claude" }
    [pscustomobject]@{ Id="gemini";      Label="Gemini CLI";           Profile="";              Detect="command:gemini||dir:$HOME\.gemini" }
    [pscustomobject]@{ Id="codex";       Label="Codex CLI";            Profile="codex";         Detect="command:codex||dir:$HOME\.codex" }
    [pscustomobject]@{ Id="cursor";      Label="Cursor";               Profile="cursor";        Detect="command:cursor||dir:$HOME\.cursor" }
    [pscustomobject]@{ Id="windsurf";    Label="Windsurf";             Profile="windsurf";      Detect="command:windsurf||dir:$HOME\.codeium\windsurf||dir:$HOME\.windsurf" }
    [pscustomobject]@{ Id="cline";       Label="Cline";                Profile="cline";         Detect="vscode-ext:cline" }
    [pscustomobject]@{ Id="copilot";     Label="GitHub Copilot";       Profile="github-copilot"; Detect="command:gh" }
    [pscustomobject]@{ Id="continue";    Label="Continue";             Profile="continue";      Detect="vscode-ext:continue.continue||vscode-ext:continue" }
    [pscustomobject]@{ Id="kilo";        Label="Kilo Code";            Profile="kilo";          Detect="vscode-ext:kilocode||dir:$HOME\.kilocode" }
    [pscustomobject]@{ Id="roo";         Label="Roo Code";             Profile="roo";           Detect="vscode-ext:roo||vscode-ext:rooveterinaryinc.roo-cline" }
    [pscustomobject]@{ Id="augment";     Label="Augment Code";         Profile="augment";       Detect="vscode-ext:augment||jetbrains-plugin:augment" }
    [pscustomobject]@{ Id="aider-desk";  Label="Aider Desk";           Profile="aider-desk";    Detect="command:aider||dir:$HOME\.aider-desk" }
    [pscustomobject]@{ Id="amp";         Label="Sourcegraph Amp";      Profile="amp";           Detect="command:amp" }
    [pscustomobject]@{ Id="bob";         Label="IBM Bob";              Profile="bob";           Detect="command:bob||dir:$HOME\.bob" }
    [pscustomobject]@{ Id="crush";       Label="Crush";                Profile="crush";         Detect="command:crush||dir:$HOME\.config\crush" }
    [pscustomobject]@{ Id="devin";       Label="Devin";                Profile="devin";         Detect="command:devin||dir:$HOME\.config\devin" }
    [pscustomobject]@{ Id="droid";       Label="Droid (Factory)";      Profile="droid";         Detect="command:droid||dir:$HOME\.factory" }
    [pscustomobject]@{ Id="forgecode";   Label="ForgeCode";            Profile="forgecode";     Detect="command:forge||dir:$HOME\.forge" }
    [pscustomobject]@{ Id="goose";       Label="Block Goose";          Profile="goose";         Detect="command:goose||dir:$HOME\.config\goose" }
    [pscustomobject]@{ Id="iflow";       Label="iFlow CLI";            Profile="iflow-cli";     Detect="command:iflow||dir:$HOME\.iflow" }
    [pscustomobject]@{ Id="junie";       Label="JetBrains Junie";      Profile="junie";         Detect="dir:$HOME\.junie||jetbrains-plugin:junie" }
    [pscustomobject]@{ Id="kiro";        Label="Kiro CLI";             Profile="kiro-cli";      Detect="command:kiro||dir:$HOME\.kiro" }
    [pscustomobject]@{ Id="mistral";     Label="Mistral Vibe";         Profile="mistral-vibe";  Detect="command:mistral||dir:$HOME\.vibe" }
    [pscustomobject]@{ Id="openhands";   Label="OpenHands";            Profile="openhands";     Detect="command:openhands||dir:$HOME\.openhands" }
    [pscustomobject]@{ Id="opencode";    Label="opencode";             Profile="opencode";      Detect="command:opencode||file:$HOME\.config\opencode\AGENTS.md" }
    [pscustomobject]@{ Id="qwen";        Label="Qwen Code";            Profile="qwen-code";     Detect="command:qwen||dir:$HOME\.qwen" }
    [pscustomobject]@{ Id="qoder";       Label="Qoder";                Profile="qoder";         Detect="dir:$HOME\.qoder" }
    [pscustomobject]@{ Id="rovodev";     Label="Atlassian Rovo Dev";   Profile="rovodev";       Detect="command:rovodev||dir:$HOME\.rovodev" }
    [pscustomobject]@{ Id="tabnine";     Label="Tabnine CLI";          Profile="tabnine-cli";   Detect="command:tabnine||dir:$HOME\.tabnine" }
    [pscustomobject]@{ Id="trae";        Label="Trae";                 Profile="trae";          Detect="command:trae||dir:$HOME\.trae" }
    [pscustomobject]@{ Id="warp";        Label="Warp";                 Profile="warp";          Detect="command:warp||dir:$HOME\.warp" }
    [pscustomobject]@{ Id="replit";      Label="Replit Agent";         Profile="replit";        Detect="command:replit||dir:$HOME\.replit" }
    [pscustomobject]@{ Id="antigravity"; Label="Google Antigravity";   Profile="antigravity";   Detect="dir:$HOME\.gemini\antigravity" }
)

# ── --list mode ────────────────────────────────────────────────────────────
if ($List) {
    Write-Say "SENTINEL agent matrix"
    Write-Host ""
    Write-Host ("  {0,-14} {1,-22} {2}" -f "ID", "AGENT", "INSTALL MECHANISM")
    Write-Host ("  {0,-14} {1,-22} {2}" -f "----", "-----", "-----------------")
    foreach ($p in $Providers) {
        $mech = if ($p.Profile) { "npx skills add ($($p.Profile))" } else { "native" }
        if ($p.Id -eq "claude")  { $mech = "claude mcp add" }
        if ($p.Id -eq "gemini")  { $mech = "gemini extensions install" }
        Write-Host ("  {0,-14} {1,-22} {2}" -f $p.Id, $p.Label, $mech)
    }
    Write-Host ""
    Write-Note "  Defaults: -WithHooks ON. -All turns on -WithInit. -Minimal turns both off."
    Write-Host ""
    exit 0
}

# ── Core install helpers ───────────────────────────────────────────────────
function Get-PythonCmd {
    foreach ($candidate in @("python", "python3", "py")) {
        if (Test-Cmd $candidate) {
            $ver = & $candidate -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
            if ($ver -match "^(\d+)\.(\d+)$") {
                if ([int]$Matches[1] -gt $MinPyMajor -or ([int]$Matches[1] -eq $MinPyMajor -and [int]$Matches[2] -ge $MinPyMinor)) {
                    return $candidate
                }
            }
        }
    }
    Write-Err "Python $MinPyMajor.$MinPyMinor+ required — https://python.org"
    exit 1
}

function Install-Uv {
    if (Test-Cmd "uv") { Write-Note "  uv $(uv --version) already installed"; return }
    Write-Say "  -> installing uv..."
    if ($DryRun) { Write-Note "  would run: Invoke-WebRequest https://astral.sh/uv/install.ps1 | iex"; return }
    try {
        $uvScript = (Invoke-WebRequest -Uri "https://astral.sh/uv/install.ps1" -UseBasicParsing).Content
        Invoke-Expression $uvScript
    } catch {
        Write-Err "Failed to install uv: $_"; exit 1
    }
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "User") + ";" + $env:PATH
    if (-not (Test-Cmd "uv")) { Write-Warn "  uv installed but not on PATH yet — restart terminal" }
}

function Ensure-BinDir {
    if (-not (Test-Path $BinDir)) { New-Item -ItemType Directory -Path $BinDir -Force | Out-Null }
    $userPath = [System.Environment]::GetEnvironmentVariable("PATH", "User")
    if ($userPath -notlike "*$BinDir*") {
        [System.Environment]::SetEnvironmentVariable("PATH", "$userPath;$BinDir", "User")
        $env:PATH = "$env:PATH;$BinDir"
        Write-Ok "  PATH updated — effective in new terminal sessions"
    }
}

function Write-Wrapper {
    if ($DryRun) { Write-Note "  would write sentinel-mcp.cmd + sentinel-mcp.ps1 to $BinDir"; return }
    $cmdPath = Join-Path $BinDir "sentinel-mcp.cmd"
    Set-Content -Path $cmdPath -Value "@echo off`r`nuv run --project `"$InstallDir`" python -m sentinel.mcp %*" -Encoding ASCII
    $ps1Path = Join-Path $BinDir "sentinel-mcp.ps1"
    Set-Content -Path $ps1Path -Value "uv run --project `"$InstallDir`" python -m sentinel.mcp @args" -Encoding UTF8
    Write-Ok "  wrapper: $cmdPath"
}

function Test-SentinelInstall {
    if ($DryRun) { Write-Note "  would validate: import sentinel"; return }
    $result = uv run --project $InstallDir python -c "import sentinel; print('OK')" 2>&1
    if ($LASTEXITCODE -ne 0) { Write-Err "import validation failed: $result"; exit 1 }
    Write-Ok "  import OK"
}

function Write-Config {
    $configDir  = Join-Path $HOME ".config\sentinel"
    $configFile = Join-Path $configDir "config.json"

    if (Test-Path $configFile) { Write-Note "  config exists at $configFile — skipping"; return }

    $provider = ""; $apiKey = ""
    if ($env:ANTHROPIC_API_KEY) { $provider = "claude"; $apiKey = $env:ANTHROPIC_API_KEY }
    elseif ($env:OPENAI_API_KEY) { $provider = "openai"; $apiKey = $env:OPENAI_API_KEY }
    else { return }

    Write-Say "  -> detected $provider API key — writing config"
    if ($DryRun) { Write-Note "  would write $configFile (llm_provider=$provider)"; return }

    if (-not (Test-Path $configDir)) { New-Item -ItemType Directory -Path $configDir -Force | Out-Null }
    [ordered]@{ llm_provider = $provider; llm_api_key = $apiKey } | ConvertTo-Json | Set-Content -Path $configFile -Encoding UTF8
    Write-Ok "  config: $configFile"
}

# ── Core installation ──────────────────────────────────────────────────────
function Invoke-CoreInstall {
    param([bool]$DevMode = $false)

    Write-Say "SENTINEL installer"
    Write-Note "  $RepoUrl"
    if ($DryRun) { Write-Note "  (dry run — nothing will be written)" }
    Write-Host ""

    $pyCmd = Get-PythonCmd
    Write-Note "  python: $(& $pyCmd --version)"

    Install-Uv

    if ($DevMode) {
        if (-not (Test-Cmd "git")) { Write-Err "-Dev requires git — https://git-scm.com"; exit 1 }
        if (Test-Path (Join-Path $InstallDir ".git")) {
            Write-Warn "  $InstallDir already exists — use -Upgrade"
        } else {
            Write-Say "  -> cloning to $InstallDir..."
            if ($DryRun) { Write-Note "  would run: git clone $RepoUrl $InstallDir" }
            else { git clone $RepoUrl $InstallDir }
        }
    } else {
        if (Test-Path $InstallDir) {
            Write-Warn "  $InstallDir already exists — use -Upgrade or -Uninstall first"
        } else {
            Write-Say "  -> downloading to $InstallDir..."
            if ($DryRun) {
                Write-Note "  would download $RepoArchive -> $InstallDir"
            } else {
                New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
                $zipPath = Join-Path $env:TEMP "sentinel-main.zip"
                try {
                    Invoke-WebRequest -Uri $RepoArchive -OutFile $zipPath -UseBasicParsing
                    Expand-Archive -Path $zipPath -DestinationPath $env:TEMP -Force
                    $extracted = Join-Path $env:TEMP "Sentinel-main"
                    Copy-Item -Recurse -Force "$extracted\*" $InstallDir
                    Remove-Item $zipPath, $extracted -Recurse -Force -EA SilentlyContinue
                } catch { Write-Err "Download failed: $_"; exit 1 }
            }
        }
    }

    Write-Say "  -> syncing dependencies..."
    if ($DryRun) { Write-Note "  would run: uv sync --project $InstallDir" }
    else { uv sync --project $InstallDir }

    Ensure-BinDir
    Write-Wrapper
    Test-SentinelInstall
    Write-Config
    Write-Host ""
}

# ── Per-agent install functions ────────────────────────────────────────────
function Install-Claude {
    $script:DetectedCount++
    Write-Say "-> Claude Code detected"

    if (-not $Force -and (Test-Cmd "claude") -and (& claude mcp list 2>$null | Select-String -Quiet "^sentinel")) {
        Write-Note "  sentinel MCP already registered (-Force to re-register)"
        Add-Skipped "claude" "already registered"
        Write-Host ""; return
    }

    if (Test-Cmd "claude") {
        try {
            if ($DryRun) { Write-Note "  would run: claude mcp add sentinel -- uv run --project `"$InstallDir`" python -m sentinel.mcp" }
            else { & claude mcp add sentinel -- uv run --project "$InstallDir" python -m sentinel.mcp }
            Write-Ok "  MCP server registered"
            Add-Installed "claude"
        } catch {
            Write-Warn "  claude mcp add failed: $_"
            Add-Failed "claude" "claude mcp add failed"
        }
    } else {
        Write-Warn "  claude CLI not found — add MCP server manually:"
        Write-Note "    command: uv"
        Write-Note "    args: [`"run`", `"--project`", `"$InstallDir`", `"python`", `"-m`", `"sentinel.mcp`"]"
        Add-Failed "claude" "claude CLI not on PATH"
    }

    if ($WithHooks) {
        Write-Say "  -> installing Claude Code hooks..."
        $hooksInstaller = Join-Path $InstallDir "hooks\install.ps1"
        if (Test-Path $hooksInstaller) {
            if ($DryRun) { Write-Note "  would run: & `"$hooksInstaller`"" }
            else {
                try { & $hooksInstaller; Add-Installed "claude-hooks" }
                catch { Write-Warn "  hooks installer failed (non-fatal): $_"; Add-Failed "claude-hooks" "hooks/install.ps1 failed" }
            }
        } else {
            Write-Note "  hooks installer not found — run: & `"$InstallDir\hooks\install.ps1`""
            Add-Skipped "claude-hooks" "installer not found"
        }
    }
    Write-Host ""
}

function Install-Gemini {
    $script:DetectedCount++
    Write-Say "-> Gemini CLI detected"

    if (-not $Force -and (& gemini extensions list 2>$null | Select-String -Quiet "sentinel")) {
        Write-Note "  sentinel extension already installed (-Force to reinstall)"
        Add-Skipped "gemini" "already installed"
        Write-Host ""; return
    }

    try {
        if ($DryRun) { Write-Note "  would run: gemini extensions install $RepoUrl" }
        else { & gemini extensions install $RepoUrl }
        Add-Installed "gemini"
    } catch {
        Add-Failed "gemini" "gemini extensions install failed"
    }
    Write-Host ""
}

function Install-ViaSkills {
    param([string]$Id, [string]$Label, [string]$Profile)
    $script:DetectedCount++
    Write-Say "-> $Label detected"

    if (-not (Test-NodeNpx)) { Add-Failed $Id "node/npx missing"; Write-Host ""; return }

    try {
        if ($DryRun) { Write-Note "  would run: npx -y skills add $RepoUrl -a $Profile" }
        else { npx -y skills add $RepoUrl -a $Profile }
        Add-Installed $Id
    } catch {
        Add-Failed $Id "npx skills add (profile: $Profile) failed"
    }
    Write-Host ""
}

# ── Uninstall ──────────────────────────────────────────────────────────────
function Invoke-Uninstall {
    Write-Say "SENTINEL uninstall"
    if (Test-Path $InstallDir) {
        if ($DryRun) { Write-Note "  would remove $InstallDir" }
        else { Remove-Item -Recurse -Force $InstallDir; Write-Ok "  removed $InstallDir" }
    } else { Write-Warn "  $InstallDir not found" }
    foreach ($f in @("sentinel-mcp.cmd", "sentinel-mcp.ps1")) {
        $p = Join-Path $BinDir $f
        if (Test-Path $p) {
            if ($DryRun) { Write-Note "  would remove $p" }
            else { Remove-Item $p; Write-Ok "  removed $p" }
        }
    }
    Write-Ok "  done."
}

# ── Upgrade ────────────────────────────────────────────────────────────────
function Invoke-Upgrade {
    if (-not (Test-Path (Join-Path $InstallDir ".git"))) {
        Write-Err "upgrade requires a -Dev install (git repo at $InstallDir)"; exit 1
    }
    Write-Say "SENTINEL upgrade"
    if ($DryRun) { Write-Note "  would run: git pull + uv sync" }
    else { git -C $InstallDir pull --ff-only; uv sync --project $InstallDir }
    Test-SentinelInstall
    Write-Ok "  upgraded."
}

# ── Dispatch ───────────────────────────────────────────────────────────────
if      ($Uninstall) { Invoke-Uninstall; exit 0 }
elseif  ($Upgrade)   { Invoke-Upgrade;   exit 0 }
elseif  ($Dev)       { Invoke-CoreInstall -DevMode $true }
else                 { Invoke-CoreInstall -DevMode $false }

# ── Agent registration ─────────────────────────────────────────────────────
Write-Say "SENTINEL registering with detected agents..."
Write-Host ""

foreach ($p in $Providers) {
    if (-not (Test-Want $p.Id)) { continue }
    if (-not (Test-DetectMatch $p.Detect)) { continue }

    switch ($p.Id) {
        "claude"  { Install-Claude; break }
        "gemini"  { Install-Gemini; break }
        default   { Install-ViaSkills $p.Id $p.Label $p.Profile; break }
    }
}

# ── Generic npx skills fallback ────────────────────────────────────────────
if (-not $SkipSkills -and $Only.Count -eq 0 -and $script:DetectedCount -eq 0) {
    Write-Say "-> no agents detected — running npx skills auto-detect fallback"
    if (Test-NodeNpx) {
        try {
            if ($DryRun) { Write-Note "  would run: npx -y skills add $RepoUrl" }
            else { npx -y skills add $RepoUrl }
            Add-Installed "skills-auto"
        } catch { Add-Failed "skills-auto" "npx skills add (auto) failed" }
    }
    Write-Host ""
}

# ── --with-init ────────────────────────────────────────────────────────────
if ($WithInit) {
    Write-Say "-> writing per-project rule files into $PWD (-WithInit)"
    if ($DryRun) { Write-Note "  would run: uv run --project $InstallDir sentinel init ." }
    else {
        try {
            $initArgs = @(".")
            if ($Force) { $initArgs += "--force" }
            uv run --project $InstallDir sentinel init @initArgs
            Add-Installed "sentinel-init ($PWD)"
        } catch { Add-Failed "sentinel-init" "sentinel init failed" }
    }
    Write-Host ""
} elseif ($InstalledIds.Count -gt 0 -or $SkippedIds.Count -gt 0) {
    Write-Note "  tip: re-run with -All (or -WithInit) to also write per-project IDE rule files."
}

# ── Summary ────────────────────────────────────────────────────────────────
Write-Host ""
Write-Say "SENTINEL done"
Write-Host ""

if ($InstalledIds.Count -gt 0) {
    Write-Ok "  installed:"
    $InstalledIds | ForEach-Object { Write-Host "    * $_" }
}

if ($SkippedIds.Count -gt 0) {
    Write-Host "  skipped:"
    for ($i = 0; $i -lt $SkippedIds.Count; $i++) {
        Write-Host "    * $($SkippedIds[$i]) -- $($SkippedWhy[$i])"
    }
}

if ($FailedIds.Count -gt 0) {
    Write-Warn "  failed:"
    for ($i = 0; $i -lt $FailedIds.Count; $i++) {
        Write-Host "    * $($FailedIds[$i]) -- $($FailedWhy[$i])" -ForegroundColor Red
    }
}

if ($InstalledIds.Count -eq 0 -and $SkippedIds.Count -eq 0 -and $FailedIds.Count -eq 0) {
    Write-Note "  nothing detected -- run 'install.ps1 -List' for all supported agents"
    Write-Note "  or pass -Only <agent> to force a specific target."
}

Write-Host ""
Write-Note "  start an audit: uv run --project `"$InstallDir`" sentinel audit ."
Write-Note "  per-project setup: sentinel init"

# Exit non-zero only when every detected agent failed.
if ($script:DetectedCount -gt 0 -and $InstalledIds.Count -eq 0 -and $SkippedIds.Count -eq 0) {
    exit 1
}
exit 0
