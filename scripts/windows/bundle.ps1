$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SciQLopRoot = Resolve-Path "$ScriptDir\..\.."
$Dist = "D:\dist"
$PackageDir = "$Dist\S"

$PythonVersion = "3.14"
$NodeVersion = "23.11.0"
$UvVersion = "0.11.2"

# Read version from pyproject.toml
$VersionLine = Select-String -Path "$SciQLopRoot\pyproject.toml" -Pattern '^version\s*=\s*"(.+)"'
$Version = $VersionLine.Matches.Groups[1].Value
Write-Host "Bundling SciQLop version $Version"

########################################
# Skip if already bundled
########################################

if (Test-Path "$PackageDir\SciQLop.exe") {
    Write-Host "Bundle already exists at $PackageDir, skipping"
    return
}

########################################
# Clean and create layout
########################################

if (Test-Path $PackageDir) { Remove-Item -Recurse -Force $PackageDir }
New-Item -ItemType Directory -Force -Path "$PackageDir\uv" | Out-Null
New-Item -ItemType Directory -Force -Path $Dist -ErrorAction SilentlyContinue | Out-Null

########################################
# Fetch uv
########################################

$UvUrl = "https://github.com/astral-sh/uv/releases/download/$UvVersion/uv-x86_64-pc-windows-msvc.zip"
if (-not (Test-Path "$Dist\uv.zip")) {
    Write-Host "Downloading uv $UvVersion..."
    Invoke-WebRequest -Uri $UvUrl -OutFile "$Dist\uv.zip"
}
Expand-Archive -Path "$Dist\uv.zip" -DestinationPath "$Dist\uv-extract" -Force
$UvExe = Get-ChildItem "$Dist\uv-extract" -Recurse -Filter "uv.exe" | Select-Object -First 1
Copy-Item $UvExe.FullName "$PackageDir\uv\uv.exe"
$UvBin = "$PackageDir\uv\uv.exe"

########################################
# Fetch Python via uv
########################################

Write-Host "Installing Python $PythonVersion..."
& $UvBin python install $PythonVersion --install-dir "$PackageDir\python-installs"

$PythonExe = Get-ChildItem "$PackageDir\python-installs" -Recurse -Filter "python.exe" | Select-Object -First 1
$PythonInstallDir = $PythonExe.Directory.FullName
Write-Host "Found Python at: $PythonInstallDir"
Move-Item $PythonInstallDir "$PackageDir\python"
Remove-Item "$PackageDir\python-installs" -Recurse -Force

$PythonBin = "$PackageDir\python\python.exe"

$ExternallyManaged = Get-ChildItem -Path "$PackageDir\python" -Recurse -Filter "EXTERNALLY-MANAGED" -ErrorAction SilentlyContinue
if ($ExternallyManaged) { Remove-Item $ExternallyManaged.FullName -Force }

########################################
# Install SciQLop
########################################

Write-Host "Installing SciQLop..."
& $UvBin pip install --system --python $PythonBin --link-mode=copy --reinstall --no-cache "$SciQLopRoot\"

########################################
# Plugin dependencies
########################################

$PluginDepsRaw = & $PythonBin -I "$SciQLopRoot\scripts\list_plugins_dependencies.py" "$SciQLopRoot\SciQLop\plugins"
$PluginDeps = ($PluginDepsRaw -join " ") -split '\s+' | Where-Object { $_ }
if ($PluginDeps) {
    Write-Host "Installing plugin dependencies: $PluginDeps"
    & $UvBin pip install --system --python $PythonBin --link-mode=copy @PluginDeps
}

########################################
# SSL certificates
########################################

& $UvBin pip install --system --python $PythonBin --link-mode=copy certifi

########################################
# Dev speasy override (non-release only)
########################################

if (-not $env:RELEASE) {
    & $UvBin pip install --system --python $PythonBin --link-mode=copy --upgrade "git+https://github.com/SciQLop/speasy"
}

########################################
# Bundle Node.js
########################################

$NodeUrl = "https://nodejs.org/dist/v$NodeVersion/node-v$NodeVersion-win-x64.zip"
if (-not (Test-Path "$Dist\node.zip")) {
    Write-Host "Downloading Node.js $NodeVersion..."
    Invoke-WebRequest -Uri $NodeUrl -OutFile "$Dist\node.zip"
}
Expand-Archive -Path "$Dist\node.zip" -DestinationPath $Dist -Force
Move-Item "$Dist\node-v$NodeVersion-win-x64" "$PackageDir\node"

########################################
# Compile launcher
########################################

Write-Host "Compiling launcher..."
& cl /nologo /O2 /Fe:"$PackageDir\SciQLop.exe" "$ScriptDir\launcher.c" `
    /link user32.lib kernel32.lib /SUBSYSTEM:WINDOWS

########################################
# Trim bloat
########################################

Write-Host "Trimming package contents..."
Get-ChildItem -Path "$PackageDir\python" -Recurse -Directory -Filter "__pycache__" |
    Remove-Item -Recurse -Force
Get-ChildItem -Path "$PackageDir\python" -Recurse -Directory -Filter "tests" |
    Where-Object { $_.FullName -match 'site-packages' -and $_.FullName -notmatch 'astropy' } |
    Remove-Item -Recurse -Force
Get-ChildItem -Path "$PackageDir\python" -Recurse -Directory -Filter "test" |
    Where-Object { $_.FullName -match 'site-packages' -and $_.FullName -notmatch 'astropy' } |
    Remove-Item -Recurse -Force
Get-ChildItem -Path $PackageDir -Recurse |
    Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint } |
    Remove-Item -Force

# Remove Unix artifacts that trip the Windows Store pre-processing scanner (0x800700C1)
Get-ChildItem -Path $PackageDir -Recurse -Include *.a,*.o,*.so,*.dylib |
    Remove-Item -Force
# Node.js ships extensionless Unix shell scripts alongside .cmd wrappers
foreach ($dir in @("$PackageDir\node", "$PackageDir\node\node_modules")) {
    if (Test-Path $dir) {
        Get-ChildItem -Path $dir -Recurse -File |
            Where-Object { -not $_.Extension } |
            Where-Object {
                $first = Get-Content $_.FullName -First 1 -ErrorAction SilentlyContinue
                $first -and $first.StartsWith("#!")
            } |
            ForEach-Object {
                Write-Host "Removing Unix shell script: $($_.FullName)"
                Remove-Item $_.FullName -Force
            }
    }
}

########################################
# Validate PE binaries
########################################

Write-Host "Validating PE binaries..."
$InvalidBinaries = @()
Get-ChildItem -Path $PackageDir -Recurse -Include *.exe,*.dll,*.pyd |
    ForEach-Object {
        $bytes = [System.IO.File]::ReadAllBytes($_.FullName)
        if ($bytes.Length -lt 2 -or $bytes[0] -ne 0x4D -or $bytes[1] -ne 0x5A) {
            $InvalidBinaries += $_.FullName
            Write-Warning "Invalid PE: $($_.FullName)"
        }
    }
if ($InvalidBinaries.Count -gt 0) {
    Write-Error "Found $($InvalidBinaries.Count) invalid PE binary(ies) in the bundle"
    exit 1
}
Write-Host "All PE binaries valid."

Write-Host "Bundle complete at $PackageDir"
