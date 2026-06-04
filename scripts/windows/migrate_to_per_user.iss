; Shared migration helper, #included by installer.iss and online_installer.iss.
;
; Earlier SciQLop releases installed system-wide (admin, into Program Files)
; and registered their uninstaller under HKLM.  The installer is now per-user
; (PrivilegesRequired=lowest), so a fresh install lands in
; %LOCALAPPDATA%\Programs instead.  Without this step the old all-users copy
; would be orphaned next to the new one.  Offer to remove it (a single UAC
; prompt) before the per-user install is laid down.
;
; AppId must match the [Setup] AppId of both installers.

[Code]
const
  LegacyUninstallSubkey =
    'Software\Microsoft\Windows\CurrentVersion\Uninstall\' +
    '{DE0DE37F-1FC8-445C-A229-7184C0A876C2}_is1';

function FindLegacyAllUsersUninstaller(var ExePath: String): Boolean;
begin
  if RegQueryStringValue(HKLM64, LegacyUninstallSubkey, 'UninstallString', ExePath)
     and (ExePath <> '') then
  begin
    Result := True;
    Exit;
  end;
  Result :=
    RegQueryStringValue(HKLM32, LegacyUninstallSubkey, 'UninstallString', ExePath)
    and (ExePath <> '');
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ExePath: String;
  ResultCode: Integer;
begin
  Result := '';
  if not FindLegacyAllUsersUninstaller(ExePath) then
    Exit;

  if MsgBox(
       'A previous system-wide installation of SciQLop was found.' #13#10#13#10 +
       'SciQLop now installs per-user and no longer needs administrator ' +
       'rights.  Remove the old system-wide installation now?' #13#10#13#10 +
       'This is the only step that asks for administrator approval.',
       mbConfirmation, MB_YESNO) <> IDYES then
    Exit;

  { The legacy uninstaller is manifested requireAdministrator, so the 'runas'
    verb raises a single UAC prompt to remove the old Program Files install. }
  if not ShellExec('runas', RemoveQuotes(ExePath),
       '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART', '', SW_SHOW,
       ewWaitUntilTerminated, ResultCode) then
    MsgBox(
      'The previous system-wide installation could not be removed ' +
      '(administrator approval was declined or unavailable).' #13#10#13#10 +
      'The per-user installation will continue; you can remove the old copy ' +
      'later from "Apps & features".',
      mbInformation, MB_OK);
end;
