; Inno Setup script for the VideoDub Windows installer.
;
; Build (from videodub/desktop after desktop\build.bat):
;   ISCC.exe /DAppVersion=1.2.3 installer\VideoDub.iss
; Output: desktop\dist\installer\VideoDub-Setup-<version>.exe
;
; The installer is per-user (no admin/UAC prompt) and installs into
; %LOCALAPPDATA%\Programs\VideoDub. User data (jobs, videos, settings) lives in
; %LOCALAPPDATA%\VideoDub and is kept on uninstall and upgrade.

#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#ifndef AppPublisher
  #define AppPublisher "VideoDub"
#endif
#ifndef SourceDir
  #define SourceDir "..\dist\VideoDub"
#endif

[Setup]
; Never change AppId: Windows uses it to recognise upgrades of the same app.
AppId={{C44107E3-9E06-4F46-B2BC-84D44A0BAFA1}
AppName=VideoDub
AppVersion={#AppVersion}
AppVerName=VideoDub {#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\VideoDub
DefaultGroupName=VideoDub
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
OutputDir=..\dist\installer
OutputBaseFilename=VideoDub-Setup-{#AppVersion}
SetupIconFile=..\VideoDub.ico
UninstallDisplayIcon={app}\VideoDub.exe
UninstallDisplayName=VideoDub
Compression=lzma2/max
SolidCompression=yes
LZMAUseSeparateProcess=yes
WizardStyle=modern
; Close a running VideoDub before files are replaced during an upgrade.
CloseApplications=yes
RestartApplications=no
UsePreviousAppDir=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
; Vietnamese is an unofficial Inno Setup translation and is not shipped with
; the compiler. To localise the wizard, put Vietnamese.isl from
; https://jrsoftware.org/files/istrans/ next to this script and add:
; Name: "vietnamese"; MessagesFile: "Vietnamese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[InstallDelete]
; Upgrades wipe the PyInstaller runtime folder so stale DLLs from an older
; build cannot be loaded by the new version. User data is elsewhere.
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Evergreen WebView2 bootstrapper (~2 MB). Only run when WebView2 is missing.
Source: "MicrosoftEdgeWebview2Setup.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall skipifsourcedoesntexist; Check: NeedsWebView2

[Icons]
Name: "{autoprograms}\VideoDub"; Filename: "{app}\VideoDub.exe"
Name: "{autodesktop}\VideoDub"; Filename: "{app}\VideoDub.exe"; Tasks: desktopicon

[Run]
Filename: "{tmp}\MicrosoftEdgeWebview2Setup.exe"; Parameters: "/silent /install"; \
  StatusMsg: "Installing Microsoft Edge WebView2 Runtime..."; \
  Check: NeedsWebView2 and FileExists(ExpandConstant('{tmp}\MicrosoftEdgeWebview2Setup.exe')); Flags: waituntilterminated
Filename: "{app}\VideoDub.exe"; Description: "{cm:LaunchProgram,VideoDub}"; Flags: nowait postinstall skipifsilent

[Code]
const
  WebView2ClientKey = 'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';

function WebView2VersionFound(RootKey: Integer; SubKey: String): Boolean;
var
  Version: String;
begin
  Result := RegQueryStringValue(RootKey, SubKey, 'pv', Version)
    and (Version <> '') and (Version <> '0.0.0.0');
end;

function NeedsWebView2(): Boolean;
begin
  Result := not (
    WebView2VersionFound(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}')
    or WebView2VersionFound(HKLM, WebView2ClientKey)
    or WebView2VersionFound(HKCU, WebView2ClientKey));
end;
