<#
.SYNOPSIS
    SENTINEL Claude Code hooks installer (Windows)
.DESCRIPTION
    Copies sentinel-activate.js and registers it as a SessionStart hook.
    Also registers the statusline script.
.PARAMETER DryRun
    Print actions without writing files.
.PARAMETER Force
    Overwrite existing hook files.
.EXAMPLE
    .\hooks\install.ps1
    .\hooks\install.ps1 -DryRun
    .\hooks\install.ps1 -Force
#>
param(
    [switch]$DryRun,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'

function Write-Ok($msg)   { Write-Host "  ✓ $msg" -ForegroundColor Green }
function Write-Info($msg) { Write-Host "  → $msg" -ForegroundColor Cyan }
function Write-Warn($msg) { Write-Host "  ! $msg" -ForegroundColor Yellow }
function Write-Err($msg)  { Write-Host "  ✗ $msg" -ForegroundColor Red }

function Invoke-Cmd($description, [scriptblock]$block) {
    if ($DryRun) {
        Write-Host "  [dry-run] $description" -ForegroundColor Yellow
    } else {
        & $block
    }
}

# ── Paths ──────────────────────────────────────────────────────────────────────
$ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$ClaudeDir   = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $env:APPDATA '.claude' }
$HooksDst    = Join-Path $ClaudeDir 'hooks'
$SettingsFile = Join-Path $ClaudeDir 'settings.json'

Write-Host "`nSENTINEL hooks installer`n" -ForegroundColor Cyan

# ── Pre-flight ─────────────────────────────────────────────────────────────────
if (-not (Test-Path $ClaudeDir)) {
    Write-Err "Claude Code config directory not found: $ClaudeDir"
    Write-Err "Install Claude Code first, or set CLAUDE_CONFIG_DIR."
    exit 1
}

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Err "Node.js required for hooks but not found on PATH."
    exit 1
}

# ── Copy hook script ───────────────────────────────────────────────────────────
$ActivateSrc = Join-Path $ScriptDir 'sentinel-activate.js'
$ActivateDst = Join-Path $HooksDst  'sentinel-activate.js'

if (-not (Test-Path $ActivateSrc)) {
    Write-Err "Hook source not found: $ActivateSrc"
    exit 1
}

if ((Test-Path $ActivateDst) -and -not $Force) {
    Write-Warn "Hook already installed: $ActivateDst  (use -Force to overwrite)"
} else {
    Invoke-Cmd "mkdir $HooksDst" { New-Item -ItemType Directory -Path $HooksDst -Force | Out-Null }
    Invoke-Cmd "copy sentinel-activate.js" { Copy-Item $ActivateSrc $ActivateDst -Force }
    Write-Ok "Copied sentinel-activate.js → $ActivateDst"
}

# ── Copy statusline script ─────────────────────────────────────────────────────
$StatuslineSrc = Join-Path $ScriptDir 'sentinel-statusline.ps1'
$StatuslineDst = Join-Path $HooksDst  'sentinel-statusline.ps1'

if (Test-Path $StatuslineSrc) {
    if ((Test-Path $StatuslineDst) -and -not $Force) {
        Write-Warn "Statusline already installed: $StatuslineDst"
    } else {
        Invoke-Cmd "copy sentinel-statusline.ps1" { Copy-Item $StatuslineSrc $StatuslineDst -Force }
        Write-Ok "Copied sentinel-statusline.ps1 → $StatuslineDst"
    }
}

# ── Register in settings.json ──────────────────────────────────────────────────
$HookCmd      = "node `"$ActivateDst`""
$StatuslineCmd = "powershell -NonInteractive -File `"$StatuslineDst`""

$RegisterPy = @"
import json, sys, os

settings_path  = sys.argv[1]
hook_cmd       = sys.argv[2]
statusline_cmd = sys.argv[3]

data = {}
if os.path.exists(settings_path):
    with open(settings_path, 'r') as f:
        try: data = json.load(f)
        except json.JSONDecodeError: data = {}

hooks = data.setdefault('hooks', {})
session_hooks = hooks.setdefault('SessionStart', [])
already = any(hook_cmd in str(h) for h in session_hooks)
if not already:
    session_hooks.append({'matcher': '', 'hooks': [{'type': 'command', 'command': hook_cmd}]})

if statusline_cmd not in str(data.get('statusLine', '')):
    data['statusLine'] = statusline_cmd

with open(settings_path, 'w') as f:
    json.dump(data, f, indent=2)
print('ok')
"@

if ($DryRun) {
    Write-Info "[dry-run] Would register SessionStart hook in $SettingsFile"
    Write-Info "[dry-run] Would register statusLine in $SettingsFile"
} else {
    try {
        $result = $RegisterPy | python - $SettingsFile $HookCmd $StatuslineCmd 2>&1
        if ($result -eq 'ok') {
            Write-Ok "Registered SessionStart hook in $SettingsFile"
            Write-Ok "Registered statusLine in $SettingsFile"
        } else {
            throw $result
        }
    } catch {
        Write-Warn "Could not update $SettingsFile automatically: $_"
        Write-Warn "Add manually to settings.json:"
        Write-Warn "  `"hooks`": {`"SessionStart`": [{`"matcher`":`"`",`"hooks`":[{`"type`":`"command`",`"command`":`"$HookCmd`"}]}]}"
        Write-Warn "  `"statusLine`": `"$StatuslineCmd`""
    }
}

Write-Host "`nHooks installed. Restart Claude Code to activate.`n" -ForegroundColor Green
if ($DryRun) { Write-Host "Dry-run: no files written.`n" -ForegroundColor Yellow }
