<#
.SYNOPSIS
    SENTINEL Claude Code hooks uninstaller (Windows)
.PARAMETER DryRun
    Print actions without removing files.
#>
param([switch]$DryRun)

$ErrorActionPreference = 'Stop'

function Write-Ok($msg)   { Write-Host "  ✓ $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "  ! $msg" -ForegroundColor Yellow }

function Invoke-Cmd($description, [scriptblock]$block) {
    if ($DryRun) { Write-Host "  [dry-run] $description" -ForegroundColor Yellow }
    else { & $block }
}

$ClaudeDir    = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $env:APPDATA '.claude' }
$HooksDst     = Join-Path $ClaudeDir 'hooks'
$SettingsFile = Join-Path $ClaudeDir 'settings.json'
$FlagPath     = Join-Path $ClaudeDir '.sentinel-active'

Write-Host "`nSENTINEL hooks uninstaller`n" -ForegroundColor Cyan

# Remove flag file
if (Test-Path $FlagPath) {
    Invoke-Cmd "remove .sentinel-active" { Remove-Item $FlagPath -Force }
    Write-Ok "Removed .sentinel-active flag"
}

# Remove hook scripts
foreach ($f in @('sentinel-activate.js', 'sentinel-statusline.ps1')) {
    $p = Join-Path $HooksDst $f
    if (Test-Path $p) {
        Invoke-Cmd "remove $f" { Remove-Item $p -Force }
        Write-Ok "Removed $p"
    }
}

# Remove entries from settings.json
$UnregisterPy = @"
import json, sys, os

settings_path = sys.argv[1]
if not os.path.exists(settings_path):
    print('no-settings'); sys.exit(0)

with open(settings_path, 'r') as f:
    try: data = json.load(f)
    except json.JSONDecodeError:
        print('invalid-json'); sys.exit(0)

changed = False
hooks = data.get('hooks', {})
session_hooks = hooks.get('SessionStart', [])
new_hooks = [h for h in session_hooks if 'sentinel' not in str(h)]
if len(new_hooks) != len(session_hooks):
    hooks['SessionStart'] = new_hooks
    if not new_hooks: del hooks['SessionStart']
    changed = True

if 'sentinel' in str(data.get('statusLine', '')):
    del data['statusLine']; changed = True

if changed:
    with open(settings_path, 'w') as f: json.dump(data, f, indent=2)
    print('ok')
else:
    print('nothing-to-remove')
"@

if ($DryRun) {
    Write-Warn "[dry-run] Would remove sentinel entries from $SettingsFile"
} else {
    try {
        $result = $UnregisterPy | python - $SettingsFile 2>&1
        switch ($result) {
            'ok'               { Write-Ok "Removed sentinel entries from $SettingsFile" }
            'nothing-to-remove'{ Write-Warn "No sentinel entries in $SettingsFile" }
            'no-settings'      { Write-Warn "$SettingsFile not found" }
            default            { Write-Warn "Could not update $SettingsFile`: $result" }
        }
    } catch {
        Write-Warn "Could not update settings.json: $_"
    }
}

Write-Host "`nDone.`n" -ForegroundColor Green
if ($DryRun) { Write-Host "Dry-run: no files removed.`n" -ForegroundColor Yellow }
