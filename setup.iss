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
UninstallDisplayIcon={app}\PersonalTracker.exe
[Files]
Source: "dist\PersonalTracker.exe"; DestDir: "{app}"; Flags: ignoreversion
[Icons]
Name: "{autoprograms}\Personal Tracker"; Filename: "{app}\PersonalTracker.exe"
Name: "{autodesktop}\Personal Tracker"; Filename: "{app}\PersonalTracker.exe"
[Run]
Filename: "{app}\PersonalTracker.exe"; Description: "Open Personal Tracker"; Flags: nowait postinstall skipifsilent
