$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SciQLopRoot = Resolve-Path "$ScriptDir\..\.."
$Dist = "D:\dist"
$PackageDir = "$Dist\S"
$RepoDist = "$SciQLopRoot\dist"

# Run shared bundling
& "$ScriptDir\bundle.ps1"

########################################
# Build installer with Inno Setup
########################################

$VersionLine = Select-String -Path "$SciQLopRoot\pyproject.toml" -Pattern '^version\s*=\s*"(.+)"'
$Version = $VersionLine.Matches.Groups[1].Value

New-Item -ItemType Directory -Force -Path $RepoDist | Out-Null

Write-Host "Building installer with Inno Setup..."
& iscc /DMyAppVersion="$Version" /DSourceDir="$PackageDir" /DOutputDir="$RepoDist" "$ScriptDir\installer.iss"

Write-Host "Done: $RepoDist\SciQLop-x64-setup.exe"
