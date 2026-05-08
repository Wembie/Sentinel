# SENTINEL statusline script for Claude Code (Windows).
# Reads the .sentinel-active flag and outputs a badge if active.

$claudeDir = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $env:APPDATA '.claude' }
$flagPath  = Join-Path $claudeDir '.sentinel-active'

if (Test-Path $flagPath -PathType Leaf) {
    Write-Output "🛡 SENTINEL"
}
