# Fetch the pinned launcher binary and verify its digest (Windows counterpart
# of fetch_launcher.sh). Set $env:SCIQLOP_LAUNCHER_BIN to use a local build.
param(
    [Parameter(Mandatory = $true)][string]$Destination,
    [string]$Platform = "windows_x86_64"
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

$pins = @{}
Get-Content (Join-Path $ScriptDir "launcher.version") | ForEach-Object {
    if ($_ -match '^\s*([A-Za-z0-9_]+)\s*=\s*(\S+)\s*$') { $pins[$Matches[1]] = $Matches[2] }
}

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Destination) | Out-Null

if ($env:SCIQLOP_LAUNCHER_BIN) {
    Write-Host "Using local launcher: $env:SCIQLOP_LAUNCHER_BIN"
    Copy-Item $env:SCIQLOP_LAUNCHER_BIN $Destination -Force
    exit 0
}

$expected = $pins["LAUNCHER_SHA256_$Platform"]
if (-not $expected) { throw "No pinned digest for $Platform in launcher.version" }

$version = $pins["LAUNCHER_VERSION"]

# All-zero digest is the placeholder launcher.version ships until a real
# launcher-v$version release exists — skip instead of 404ing CI.
if ($expected -match '^0+$') {
    Write-Host "launcher $version not pinned for $Platform (placeholder digest) — skipping"
    exit 0
}

$repo = $pins["LAUNCHER_REPO"]

# Must match the artifact names published by .github/workflows/launcher.yml.
$assets = @{ "windows_x86_64" = "sciqlop-launcher-windows-x86_64.exe" }
$asset = $assets[$Platform]
if (-not $asset) { throw "Unknown launcher platform: $Platform" }

$url = "https://github.com/$repo/releases/download/launcher-v$version/$asset"

Write-Host "Downloading launcher $version ($Platform)..."
Invoke-WebRequest -Uri $url -OutFile $Destination -UseBasicParsing

$actual = (Get-FileHash -Path $Destination -Algorithm SHA256).Hash.ToLower()
if ($actual -ne $expected.ToLower()) {
    Remove-Item $Destination -Force
    throw "Launcher digest mismatch for $Platform`n  expected $expected`n  actual   $actual"
}

Write-Host "Launcher verified: $Destination"
