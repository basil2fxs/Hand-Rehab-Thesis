; Finger Rehab, per-user Windows installer. Built by CI from the same
; commit as the exe it wraps, with Inno Setup 6. No administrator
; needed: everything lands under the user's own profile.
;
; Local build: "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installers\windows.iss
; builds\build_app.bat does that when Inno Setup is installed.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
; Fixed for the life of the product. Inno matches later installers to
; this one by it, which is what makes an update land in the same folder
; instead of beside the old copy. Never change it.
AppId={{5866941A-FC79-46E5-A140-A7F636839A95}
AppName=Finger Rehab
AppVersion={#AppVersion}
AppPublisher=Curtin University
DefaultDirName={localappdata}\Programs\Finger Rehab
DisableDirPage=yes
DefaultGroupName=Finger Rehab
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\bin\dist
OutputBaseFilename=FingerRehab-Setup-Windows
SetupIconFile=..\assets\icons\app_icon.ico
UninstallDisplayIcon={app}\Finger Rehab.exe
UninstallDisplayName=Finger Rehab
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; The watcher runs without a window, so Restart Manager cannot ask it
; to close. PrepareToInstall ends it first; force covers a stray copy.
CloseApplications=force
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Files]
; ignoreversion: the PyInstaller exe carries no version resource, and
; without this flag an update could leave the old file in place.
Source: "..\bin\dist\Finger Rehab.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{userprograms}\Finger Rehab"; Filename: "{app}\Finger Rehab.exe"
Name: "{userdesktop}\Finger Rehab"; Filename: "{app}\Finger Rehab.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Put a shortcut on the Desktop"; GroupDescription: "Shortcuts:"

[InstallDelete]
; Left by the old Setup app, and it would open the old exe.
Type: files; Name: "{userdesktop}\Finger Rehab.bat"

[Run]
; Hidden: this path prints one line and exits, it never opens a window.
; No skipifsilent, so a silent install still turns auto-start on.
Filename: "{app}\Finger Rehab.exe"; Parameters: "--register-autostart"; Flags: runhidden waituntilterminated
Filename: "{app}\Finger Rehab.exe"; Description: "Open Finger Rehab now"; Flags: postinstall nowait skipifsilent

[UninstallRun]
; Runs before the files go, so the exe is still there to do it.
Filename: "{app}\Finger Rehab.exe"; Parameters: "--unregister-autostart"; Flags: runhidden waituntilterminated; RunOnceId: "unregister"

; No uninstall-delete section on purpose. Inno removes only what it
; installed, so the sessions, config and logs folders the game writes
; under {app} stay.

[Code]
// Stop the running watcher before its exe is overwritten.
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  R: Integer;
begin
  Exec('schtasks.exe', '/End /TN FingerRehabAutostart', '', SW_HIDE,
       ewWaitUntilTerminated, R);
  Result := '';
end;
