$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SciQLopRoot = Resolve-Path "$ScriptDir\..\.."
$RepoDist = "$SciQLopRoot\dist"

$VersionLine = Select-String -Path "$SciQLopRoot\pyproject.toml" -Pattern '^version\s*=\s*"(.+)"'
$Version = $VersionLine.Matches.Groups[1].Value

New-Item -ItemType Directory -Force -Path $RepoDist | Out-Null

########################################
# Fetch native launcher
#
# This online installer's {app}\SciQLop.exe is the same self-contained-bundle
# entry point as the offline one (bundle.ps1): install.ps1 downloads
# python/node/uv into {app}\python, {app}\node, {app}\uv, and the launcher
# finds them next to itself the same way (launcher/src/paths.cpp's
# bundled_python()/bundled_path_prefix()) — see launcher/README.md.
########################################

Write-Host "Fetching native launcher..."
& "$ScriptDir\..\fetch_launcher.ps1" -Destination "$RepoDist\SciQLop.exe" -Platform windows_x86_64

# See bundle.ps1's identical check for why $LASTEXITCODE isn't used here:
# fetch_launcher.ps1 only sets it via an explicit `exit`, not on a normal
# return, and this installer has no fallback entry point either.
if (-not (Test-Path "$RepoDist\SciQLop.exe")) {
    throw "Native launcher missing at $RepoDist\SciQLop.exe after fetch_launcher.ps1. " +
          "Most likely launcher-v<version> is not released yet for windows_x86_64 " +
          "(see scripts/launcher.version) — tag one and fill in the digest before building."
}

########################################
# Build online installer with Inno Setup
########################################

Write-Host "Building online installer..."
& iscc /DMyAppVersion="$Version" /DOutputDir="$RepoDist" /DScriptDir="$ScriptDir" `
    /DLauncherExe="$RepoDist\SciQLop.exe" "$ScriptDir\online_installer.iss"

Write-Host "Done: $RepoDist\SciQLop-x64-online-setup.exe"
