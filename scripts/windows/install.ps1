param(
    [Parameter(Mandatory)][string]$InstallDir
)

$ErrorActionPreference = "Stop"

$PythonVersion = "3.14"
$NodeVersion = "23.11.0"
$UvVersion = "0.11.2"

$UvDir = "$InstallDir\uv"
$PythonDir = "$InstallDir\python"
$NodeDir = "$InstallDir\node"

########################################
# Download uv
########################################

New-Item -ItemType Directory -Force -Path $UvDir | Out-Null

$UvUrl = "https://github.com/astral-sh/uv/releases/download/$UvVersion/uv-x86_64-pc-windows-msvc.zip"
$UvZip = "$env:TEMP\uv.zip"
Write-Host "Downloading uv $UvVersion..."
Invoke-WebRequest -Uri $UvUrl -OutFile $UvZip
Expand-Archive -Path $UvZip -DestinationPath "$env:TEMP\uv-extract" -Force
$UvExe = Get-ChildItem "$env:TEMP\uv-extract" -Recurse -Filter "uv.exe" | Select-Object -First 1
Copy-Item $UvExe.FullName "$UvDir\uv.exe"
$UvBin = "$UvDir\uv.exe"

########################################
# Install Python via uv
########################################

Write-Host "Installing Python $PythonVersion..."
& $UvBin python install $PythonVersion --install-dir "$env:TEMP\python-installs"

$PythonExe = Get-ChildItem "$env:TEMP\python-installs" -Recurse -Filter "python.exe" | Select-Object -First 1
if (Test-Path $PythonDir) { Remove-Item -Recurse -Force $PythonDir }
Move-Item $PythonExe.Directory.FullName $PythonDir

$PythonBin = "$PythonDir\python.exe"

# Remove PEP 668 marker
Get-ChildItem -Path $PythonDir -Recurse -Filter "EXTERNALLY-MANAGED" -ErrorAction SilentlyContinue |
    Remove-Item -Force

########################################
# Install SciQLop
########################################

Write-Host "Installing SciQLop..."
& $UvBin pip install --system --python $PythonBin --link-mode=copy sciqlop

########################################
# Install plugin dependencies
########################################

$ListScript = "$PythonDir\Lib\site-packages\SciQLop\..\..\..\..\scripts\list_plugins_dependencies.py"
$PluginsDir = "$PythonDir\Lib\site-packages\SciQLop\plugins"

if (Test-Path $PluginsDir) {
    # Use the installed SciQLop's own plugin list
    $PluginDepsRaw = & $PythonBin -c "
import json, os, sys
plugins_dir = r'$PluginsDir'
deps = []
for p in os.listdir(plugins_dir):
    pj = os.path.join(plugins_dir, p, 'plugin.json')
    if os.path.exists(pj):
        with open(pj) as f:
            info = json.load(f)
        deps.extend(info.get('dependencies', []))
print(' '.join(deps))
"
    $PluginDeps = ($PluginDepsRaw -join " ") -split '\s+' | Where-Object { $_ }
    if ($PluginDeps) {
        Write-Host "Installing plugin dependencies: $PluginDeps"
        & $UvBin pip install --system --python $PythonBin --link-mode=copy @PluginDeps
    }
}

########################################
# SSL certificates
########################################

& $UvBin pip install --system --python $PythonBin --link-mode=copy certifi

########################################
# Download Node.js
########################################

Write-Host "Downloading Node.js $NodeVersion..."
$NodeUrl = "https://nodejs.org/dist/v$NodeVersion/node-v$NodeVersion-win-x64.zip"
$NodeZip = "$env:TEMP\node.zip"
Invoke-WebRequest -Uri $NodeUrl -OutFile $NodeZip
Expand-Archive -Path $NodeZip -DestinationPath "$env:TEMP" -Force
if (Test-Path $NodeDir) { Remove-Item -Recurse -Force $NodeDir }
Move-Item "$env:TEMP\node-v$NodeVersion-win-x64" $NodeDir

########################################
# Cleanup
########################################

Remove-Item "$env:TEMP\uv.zip", "$env:TEMP\node.zip" -Force -ErrorAction SilentlyContinue
Remove-Item "$env:TEMP\uv-extract", "$env:TEMP\python-installs" -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "Installation complete"
