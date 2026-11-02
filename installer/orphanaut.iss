; Inno Setup script for the Orphanaut Windows installer.
; Built in CI:  iscc /DAppVersion=2.1.0 installer\orphanaut.iss
; Installs per-user (no admin rights needed), adds Start menu / desktop shortcuts
; and a normal uninstaller in Settings → Apps.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6F1D3C1E-8B7A-4C61-9E0B-0B6E2F5A9C21}
AppName=Orphanaut
AppVersion={#AppVersion}
AppVerName=Orphanaut {#AppVersion}
AppPublisher=Rajinikanth Vadla
AppPublisherURL=https://github.com/rajinikanthvadla-ai/orphanaut
AppSupportURL=https://github.com/rajinikanthvadla-ai/orphanaut/issues
AppUpdatesURL=https://github.com/rajinikanthvadla-ai/orphanaut/releases
DefaultDirName={localappdata}\Programs\Orphanaut
DefaultGroupName=Orphanaut
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist
OutputBaseFilename=Orphanaut-Setup-Windows
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\Orphanaut.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
LicenseFile=..\LICENSE

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\Orphanaut\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Orphanaut"; Filename: "{app}\Orphanaut.exe"
Name: "{group}\Uninstall Orphanaut"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Orphanaut"; Filename: "{app}\Orphanaut.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Orphanaut.exe"; Description: "{cm:LaunchProgram,Orphanaut}"; Flags: nowait postinstall skipifsilent
