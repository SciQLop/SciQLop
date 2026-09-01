param(
    [Parameter(Mandatory)][string]$InstallDir,
    [string]$Proxy = ""
)

$ErrorActionPreference = "Stop"

$PythonVersion = "3.14"
$NodeVersion = "23.11.0"
$UvVersion = "0.11.2"

########################################
# HTTP proxy
########################################
# At install time SciQLop is not installed yet, so the proxy comes either from
# the installer wizard (-Proxy) or from an inherited environment variable.
# Apply it to both Invoke-WebRequest (uv.zip / node.zip) and uv (HTTP_PROXY).
if (-not $Proxy) { $Proxy = $env:HTTPS_PROXY }
if (-not $Proxy) { $Proxy = $env:HTTP_PROXY }
if ($Proxy) {
    Write-Host "Using HTTP proxy: $Proxy"
    $env:HTTP_PROXY = $Proxy
    $env:HTTPS_PROXY = $Proxy
    $PSDefaultParameterValues['Invoke-WebRequest:Proxy'] = $Proxy
}

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

Write-Host "Installing SciQLop launcher..."
# The bare package is only the launcher — read the manifest/settings, then
# drive uv. It never imports the GUI stack (test_launcher_thin_imports.py),
# so it doesn't need [all] here: the application (and plugin
# python_dependencies) is installed into each workspace's own venv at first
# launch by prepare_workspace(). Installing either into this bundled Python
# would bake the whole app into the install, defeating the point of the
# self-contained-workspace split.
& $UvBin pip install --system --python $PythonBin --link-mode=copy "sciqlop"

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
