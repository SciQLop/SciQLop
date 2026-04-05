$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SciQLopRoot = Resolve-Path "$ScriptDir\..\.."
$Dist = "D:\dist"
$PackageDir = "$Dist\S"

# Run shared bundling
& "$ScriptDir\bundle.ps1"

########################################
# MSIX assets
########################################

New-Item -ItemType Directory -Force -Path "$PackageDir\Assets" | Out-Null
$SourceIcon = "$SciQLopRoot\SciQLop\resources\icons\SciQLop.png"

$Sizes = @(
    @{ Name = "StoreLogo"; Width = 50; Height = 50 },
    @{ Name = "Square44x44Logo"; Width = 44; Height = 44 },
    @{ Name = "Square150x150Logo"; Width = 150; Height = 150 },
    @{ Name = "Wide310x150Logo"; Width = 310; Height = 150 }
)

foreach ($asset in $Sizes) {
    $out = "$PackageDir\Assets\$($asset.Name).png"
    if ($asset.Width -eq $asset.Height) {
        magick $SourceIcon -resize "$($asset.Width)x$($asset.Height)" $out
    } else {
        magick $SourceIcon -resize "$($asset.Height)x$($asset.Height)" `
            -gravity center -background none -extent "$($asset.Width)x$($asset.Height)" $out
    }
}

########################################
# AppxManifest
########################################

$VersionLine = Select-String -Path "$SciQLopRoot\pyproject.toml" -Pattern '^version\s*=\s*"(.+)"'
$MsixVersion = "$($VersionLine.Matches.Groups[1].Value).0"

$ManifestTemplate = Get-Content "$ScriptDir\AppxManifest.xml.in" -Raw
$Manifest = $ManifestTemplate -replace "VERSION_PLACEHOLDER", $MsixVersion
$Manifest | Set-Content "$PackageDir\AppxManifest.xml" -Encoding UTF8

########################################
# Pack MSIX
########################################

Write-Host "Packing MSIX..."
& makeappx pack /d $PackageDir /p "$Dist\SciQLop-x64.msix" /o

$RepoDist = "$SciQLopRoot\dist"
New-Item -ItemType Directory -Force -Path $RepoDist | Out-Null
Copy-Item "$Dist\SciQLop-x64.msix" "$RepoDist\SciQLop-x64.msix"

Write-Host "Done: $RepoDist\SciQLop-x64.msix"
