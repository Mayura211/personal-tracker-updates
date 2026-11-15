#define AppVersion GetEnv('TRACKER_VERSION')
[Setup]
AppId={{9480846D-1B8D-4E23-8A59-A87667CC4143}
AppName=Personal Tracker
AppVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\PersonalTracker
DefaultGroupName=Personal Tracker
PrivilegesRequired=lowest
OutputDir=installer
OutputBaseFilename=PersonalTracker_Setup
SetupIconFile=icon.ico
Compression=lzma2
SolidCompression=yes
CloseApplications=yes
RestartApplications=no
UninstallDisplayIcon={app}\PersonalTracker.exe
[Files]
Source: "dist\PersonalTracker.exe"; DestDir: "{app}"; Flags: ignoreversion
[Icons]
Name: "{autoprograms}\Personal Tracker"; Filename: "{app}\PersonalTracker.exe"
Name: "{autodesktop}\Personal Tracker"; Filename: "{app}\PersonalTracker.exe"
[Run]
Filename: "{app}\PersonalTracker.exe"; Description: "Open Personal Tracker"; Flags: nowait postinstall skipifsilent; Check: not IsAppUpdate

Filename: "{app}\PersonalTracker.exe"; Flags: nowait; Check: IsAppUpdate
[Code]
function IsAppUpdate: Boolean;
begin
  Result := (ExpandConstant('{param:PTUPDATE|0}') = '1') or
            (ExpandConstant('{param:PTUPDATE|0}') = '2');
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
  { The old v1.0.2 updater launches Setup before its own process exits.
    Give it time to close and release the running EXE on this first upgrade. }
  if ExpandConstant('{param:PTUPDATE|0}') = '1' then
    Sleep(8000);
end;
