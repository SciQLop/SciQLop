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
SetupIconFile={#ScriptDir}\..\..\SciQLop\resources\icons\SciQLop.ico
UninstallDisplayIcon={app}\python\Lib\site-packages\SciQLop\resources\icons\SciQLop.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#LauncherExe}"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#ScriptDir}\install.ps1"; DestDir: "{tmp}"; Flags: deleteafterinstall

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\python\Lib\site-packages\SciQLop\resources\icons\SciQLop.ico"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\python\Lib\site-packages\SciQLop\resources\icons\SciQLop.ico"; Tasks: desktopicon

[Run]
Filename: "powershell.exe"; \
  Parameters: "-ExecutionPolicy Bypass -File ""{tmp}\install.ps1"" -InstallDir ""{app}"""; \
  StatusMsg: "Installing SciQLop (downloading dependencies)..."; \
  Flags: runhidden waituntilterminated
Filename: "{app}\{#MyAppExeName}"; Description: "Launch SciQLop"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\python"
Type: filesandordirs; Name: "{app}\node"
Type: filesandordirs; Name: "{app}\uv"
