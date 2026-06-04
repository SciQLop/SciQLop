#define MyAppName "SciQLop"
#define MyAppPublisher "Alexis Jeandet"
#define MyAppURL "https://github.com/SciQLop/SciQLop"
#define MyAppExeName "SciQLop.exe"

[Setup]
AppId={{DE0DE37F-1FC8-445C-A229-7184C0A876C2}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir={#OutputDir}
OutputBaseFilename=SciQLop-x64-online-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; Per-user install: no UAC prompt and no admin rights required.  {autopf}
; resolves to %LOCALAPPDATA%\Programs and {group}/{autodesktop} to the user's
; own Start Menu / Desktop, so nothing is written to a protected location.
PrivilegesRequired=lowest
SetupIconFile={#ScriptDir}\..\..\SciQLop\resources\icons\SciQLop.ico
UninstallDisplayIcon={app}\python\Lib\site-packages\SciQLop\resources\icons\SciQLop.ico
; Force-close any SciQLop / bundled python.exe using files in {app} via the
; Windows Restart Manager before [InstallDelete] and install.ps1 run.
CloseApplications=force

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

; Wipe the previous payload before install.ps1 runs uv pip install.  Without
; this, re-running the installer leaves stale dist-info dirs from the older
; versions side-by-side with the new ones (uv does not always evict them),
; producing ABI mismatches at runtime.  User data lives in
; %LOCALAPPDATA%\LPP\sciqlop and is untouched.
[InstallDelete]
Type: filesandordirs; Name: "{app}\python"
Type: filesandordirs; Name: "{app}\node"
Type: filesandordirs; Name: "{app}\uv"

[Files]
Source: "{#LauncherExe}"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#ScriptDir}\install.ps1"; DestDir: "{tmp}"; Flags: deleteafterinstall

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\python\Lib\site-packages\SciQLop\resources\icons\SciQLop.ico"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\python\Lib\site-packages\SciQLop\resources\icons\SciQLop.ico"; Tasks: desktopicon

[Run]
Filename: "powershell.exe"; \
  Parameters: "-ExecutionPolicy Bypass -File ""{tmp}\install.ps1"" -InstallDir ""{app}"" -Proxy ""{code:ProxyArg}"""; \
  StatusMsg: "Installing SciQLop (downloading dependencies)..."; \
  Flags: runhidden waituntilterminated
Filename: "{app}\{#MyAppExeName}"; Description: "Launch SciQLop"; Flags: nowait postinstall skipifsilent

; Wizard page asking for an optional HTTP proxy, passed to install.ps1 as
; -Proxy.  The online installer downloads Python/uv/Node, so on a proxied
; network the download step would otherwise hang.  Pre-filled from the
; HTTP_PROXY environment variable when present; blank means a direct
; connection.
[Code]
var
  ProxyPage: TInputQueryWizardPage;

procedure InitializeWizard();
begin
  ProxyPage := CreateInputQueryPage(wpSelectDir,
    'Network proxy',
    'Does this computer reach the internet through an HTTP proxy?',
    'If so, enter the proxy URL used to download SciQLop components ' +
    '(for example http://proxy.example:8080).  Leave blank for a direct connection.');
  ProxyPage.Add('HTTP proxy URL:', False);
  ProxyPage.Values[0] := GetEnv('HTTP_PROXY');
end;

function ProxyArg(Param: String): String;
begin
  Result := Trim(ProxyPage.Values[0]);
end;

[UninstallDelete]
Type: filesandordirs; Name: "{app}\python"
Type: filesandordirs; Name: "{app}\node"
Type: filesandordirs; Name: "{app}\uv"

; Removes any legacy system-wide install left over from before the per-user
; switch (offers a single UAC prompt during PrepareToInstall).
#include "migrate_to_per_user.iss"
