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
OutputBaseFilename=SciQLop-x64-setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile={#SourceDir}\python\Lib\site-packages\SciQLop\resources\icons\SciQLop.ico
UninstallDisplayIcon={app}\python\Lib\site-packages\SciQLop\resources\icons\SciQLop.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

; Wipe the previous payload before extracting the new bundle.  Without this,
; Inno Setup overlays files in {app} and never deletes ones that have moved
; to a different name in the new bundle (e.g. pyside6-6.10.2.dist-info →
; pyside6-6.11.0.dist-info), leaving two parallel installs side-by-side and
; producing ABI mismatches at import time.  User data lives in
; %LOCALAPPDATA%\LPP\sciqlop and is untouched.
[InstallDelete]
Type: filesandordirs; Name: "{app}\python"
Type: filesandordirs; Name: "{app}\node"
Type: filesandordirs; Name: "{app}\uv"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\python\Lib\site-packages\SciQLop\resources\icons\SciQLop.ico"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\python\Lib\site-packages\SciQLop\resources\icons\SciQLop.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch SciQLop"; Flags: nowait postinstall skipifsilent
