; ─────────────────────────────────────────────────────────────────────────────
; Inno Setup script for yt-dlp Convenient GUI (Windows)
;
; This creates a proper Windows installer that:
;   - Bundles the source code
;   - Installs Python 3.12 silently into the app folder
;   - Creates the venv and installs PySide6 during setup
;   - Creates desktop & start-menu shortcuts
;   - Provides an uninstaller
;
; Updates via git: the source code is present, so git-based updates work.
;
; Build:
;   1. Download python-3.12.X-amd64.exe into the project root
;   2. Compile with Inno Setup Compiler (ISCC.exe): ISCC installer.iss
; ─────────────────────────────────────────────────────────────────────────────

#define MyAppName "yt-dlp Convenient GUI"
#define MyAppPublisher "Nicolas-Gth"
#define MyAppURL "https://github.com/Nicolas-Gth/yt-dlp-convenient-GUI"
#define MyAppLauncher "launcher.vbs"

; Version — set by CI via /DMyAppVersion=x.y.z, else read from file or default
#ifndef MyAppVersion
  #if FileExists("version_installer.txt")
    #define MyAppVersion ReadIni("version_installer.txt", "")
  #else
    #define MyAppVersion "1.0.0"
  #endif
#endif

; Python installer filename — set by CI via /DPythonInstaller=python-3.x.y-amd64.exe
#ifndef PythonInstaller
  #define PythonInstaller "python-3.12.10-amd64.exe"
#endif

[Setup]
AppId={{2E7F1A5C-9D3B-4F6E-8A2C-1B5D7F3E9A4C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
LicenseFile=LICENSE
OutputDir=installer
OutputBaseFilename=yt-dlp-gui-setup-{#MyAppVersion}
SetupIconFile=assets\icon.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesInstallIn64BitMode=x64compatible
; Enough space for Python (~100MB) + venv + deps (~250MB) + source (~10MB)
ExtraDiskSpaceRequired=350000000

[Languages]
Name: "english";    MessagesFile: "compiler:Default.isl"
Name: "french";     MessagesFile: "compiler:Languages\French.isl"
Name: "german";     MessagesFile: "compiler:Languages\German.isl"
Name: "spanish";    MessagesFile: "compiler:Languages\Spanish.isl"
Name: "italian";    MessagesFile: "compiler:Languages\Italian.isl"
Name: "dutch";      MessagesFile: "compiler:Languages\Dutch.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startmenu";   Description: "Create a &Start Menu shortcut"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; ── Source code ─────────────────────────────────────────────────────────────
Source: "run.py";                     DestDir: "{app}"; Flags: ignoreversion
Source: "_bootstrap_win32.py";        DestDir: "{app}"; Flags: ignoreversion
Source: "_bootstrap_unix.py";         DestDir: "{app}"; Flags: ignoreversion
Source: "launcher.vbs";               DestDir: "{app}"; Flags: ignoreversion
Source: "install.ps1";                DestDir: "{app}"; Flags: ignoreversion
Source: "install.sh";                 DestDir: "{app}"; Flags: ignoreversion
Source: "LICENSE";                    DestDir: "{app}"; Flags: ignoreversion
Source: "README.md";                  DestDir: "{app}"; Flags: ignoreversion
Source: "requirements.txt";           DestDir: "{app}"; Flags: ignoreversion
Source: ".gitignore";                 DestDir: "{app}"; Flags: ignoreversion
Source: ".gitattributes";             DestDir: "{app}"; Flags: ignoreversion

; Source Python modules
Source: "src\*.py";                   DestDir: "{app}\src"; Flags: ignoreversion
Source: "src\controllers\*.py";       DestDir: "{app}\src\controllers"; Flags: ignoreversion
Source: "src\models\*.py";            DestDir: "{app}\src\models"; Flags: ignoreversion
Source: "src\utils\*.py";             DestDir: "{app}\src\utils"; Flags: ignoreversion
Source: "src\views\*.py";             DestDir: "{app}\src\views"; Flags: ignoreversion

; Assets
Source: "assets\icon.ico";            DestDir: "{app}\assets"; Flags: ignoreversion
Source: "assets\yt-dlp_convenient_gui_icon.png"; DestDir: "{app}\assets"; Flags: ignoreversion
Source: "assets\ui\*.svg";            DestDir: "{app}\assets\ui"; Flags: ignoreversion

; Locales
Source: "locales\*.json";             DestDir: "{app}\locales"; Flags: ignoreversion

; ── Git repository (for incremental updates) ─────────────────────────────────
; The .git directory is small (~3 MB) and enables git-based updates.
Source: ".git\*";                     DestDir: "{app}\.git"; Flags: ignoreversion recursesubdirs

; ── Python installer ────────────────────────────────────────────────────────
Source: "{#PythonInstaller}";         DestDir: "{tmp}"; Flags: deleteafterinstall; Check: not IsPythonInstalled

[Icons]
; Start menu shortcuts — use launcher.vbs (same as install.ps1)
Name: "{group}\{#MyAppName}";     Filename: "{app}\{#MyAppLauncher}"; WorkingDir: "{app}"; IconFilename: "{app}\assets\icon.ico"; Tasks: startmenu
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"; Tasks: startmenu

; Desktop shortcut
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppLauncher}"; WorkingDir: "{app}"; IconFilename: "{app}\assets\icon.ico"; Tasks: desktopicon

[Run]
; Launch the app after install (optional)
Filename: "{app}\{#MyAppLauncher}"; WorkingDir: "{app}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent shellexec

[UninstallDelete]
; Clean up venv and external deps on uninstall
Type: filesandordirs; Name: "{app}\venv"
Type: filesandordirs; Name: "{app}\ffmpeg"
Type: filesandordirs; Name: "{app}\temp"
Type: filesandordirs; Name: "{app}\python"
Type: files;          Name: "{app}\yt-dlp-gui-config.json"

[Code]
// ────────────────────────────────────────────────────────────────────────────
// Check if a working Python 3.10+ is already on the system PATH
// ────────────────────────────────────────────────────────────────────────────

function IsPythonInstalled: Boolean;
var
  ResultCode: Integer;
begin
  Result := False;
  if Exec('python', '-c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)"',
          '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
  begin
    Result := (ResultCode = 0);
  end;
end;

// ────────────────────────────────────────────────────────────────────────────
// Install Python silently into {app}\python
// ────────────────────────────────────────────────────────────────────────────

procedure InstallPython;
var
  PythonPath: string;
  ResultCode: Integer;
begin
  PythonPath := ExpandConstant('{app}\python');

  if not Exec(ExpandConstant('{tmp}\{#PythonInstaller}'),
              '/quiet InstallAllUsers=0 Include_test=0 Include_pip=1 ' +
              'Include_launcher=0 PrependPath=0 ' +
              'DefaultAllUsersTargetDir="' + PythonPath + '" ' +
              'TargetDir="' + PythonPath + '"',
              '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
  begin
    MsgBox('Failed to run Python installer.', mbError, MB_OK);
    ResultCode := 1;
  end;

  if ResultCode <> 0 then
  begin
    MsgBox('Python installation failed with code ' + IntToStr(ResultCode) +
           '. You can install Python manually from https://www.python.org/downloads/',
           mbError, MB_OK);
  end;
end;

// ────────────────────────────────────────────────────────────────────────────
// Create virtual environment and install all dependencies
// ────────────────────────────────────────────────────────────────────────────

procedure SetupVenv;
var
  PythonExe: string;
  PipExe: string;
  ReqFile: string;
  ResultCode: Integer;
  AppDir: string;
begin
  AppDir := ExpandConstant('{app}');

  // Determine which Python to use
  if DirExists(AppDir + '\python') then
    PythonExe := AppDir + '\python\python.exe'
  else
    PythonExe := 'python';  // System Python (fallback)

  // Create venv
  if not Exec(PythonExe, '-m venv venv', AppDir, SW_HIDE,
              ewWaitUntilTerminated, ResultCode) or (ResultCode <> 0) then
  begin
    Log('Warning: venv creation failed (will be created on first launch)');
    Exit;
  end;

  // Find pip in the new venv
  PipExe := AppDir + '\venv\Scripts\pip.exe';
  if not FileExists(PipExe) then
  begin
    Log('Warning: pip not found in venv');
    Exit;
  end;

  // Upgrade pip
  Exec(PipExe, 'install --upgrade pip', AppDir, SW_HIDE, ewWaitUntilTerminated, ResultCode);

  // Install PySide6 first (needed to show progress dialogs)
  Exec(PipExe, 'install PySide6>=6.5.0', AppDir, SW_HIDE, ewWaitUntilTerminated, ResultCode);

  // Install remaining dependencies from requirements.txt
  ReqFile := AppDir + '\requirements.txt';
  if FileExists(ReqFile) then
  begin
    Exec(PipExe, 'install -r "' + ReqFile + '"', AppDir, SW_HIDE, ewWaitUntilTerminated, ResultCode);
  end;
end;

// ────────────────────────────────────────────────────────────────────────────
// Post-install: install Python (if needed) and set up the venv
// ────────────────────────────────────────────────────────────────────────────

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // Install bundled Python if no system Python is available
    if not IsPythonInstalled then
      InstallPython;

    // Pre-create the virtual environment so the first launch is instant
    SetupVenv;
  end;
end;
