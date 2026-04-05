$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SciQLopRoot = Resolve-Path "$ScriptDir\..\.."
$RepoDist = "$SciQLopRoot\dist"

$VersionLine = Select-String -Path "$SciQLopRoot\pyproject.toml" -Pattern '^version\s*=\s*"(.+)"'
$Version = $VersionLine.Matches.Groups[1].Value

New-Item -ItemType Directory -Force -Path $RepoDist | Out-Null

########################################
# Compile launcher
########################################

Write-Host "Compiling launcher..."
& cl /nologo /O2 /Fe:"$RepoDist\SciQLop.exe" "$ScriptDir\launcher.c" `
    /link user32.lib kernel32.lib /SUBSYSTEM:WINDOWS

########################################
# Build online installer with Inno Setup
########################################

Write-Host "Building online installer..."
& iscc /DMyAppVersion="$Version" /DOutputDir="$RepoDist" /DScriptDir="$ScriptDir" `
    /DLauncherExe="$RepoDist\SciQLop.exe" "$ScriptDir\online_installer.iss"

Write-Host "Done: $RepoDist\SciQLop-x64-online-setup.exe"
