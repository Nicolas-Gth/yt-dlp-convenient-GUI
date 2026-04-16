@echo off
:: yt-dlp Convenient GUI — Windows installer & shortcut manager
::
:: Usage:
::   install.bat            → Show menu (create shortcuts / launch app)
::   install.bat --launch   → Launch the app directly (used by shortcuts)

cd /d "%~dp0"
set "APP_DIR=%~dp0"
if "%APP_DIR:~-1%"=="\" set "APP_DIR=%APP_DIR:~0,-1%"

:: -------------------------------------------------------------------
:: Ensure Python 3 is installed — auto-install with user confirmation
:: -------------------------------------------------------------------
where python >nul 2>&1
if errorlevel 1 (
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
"Add-Type -AssemblyName System.Windows.Forms; ^
$AppDir = '%APP_DIR%'; ^
$AppName = 'yt-dlp Convenient GUI'; ^
$Icon = Join-Path $AppDir 'assets\icon.ico'; ^
function RawT($key) { ^
  $lang = 'en'; ^
  $cfg = Join-Path $AppDir 'yt-dlp-gui-config.json'; ^
  if (Test-Path $cfg) { ^
    try { $j = Get-Content $cfg -Raw | ConvertFrom-Json; if ($j.language -and $j.language -ne 'system') { $lang = $j.language } else { $lang = (Get-Culture).TwoLetterISOLanguageName } } catch { } ^
  } else { $lang = (Get-Culture).TwoLetterISOLanguageName }; ^
  $f = Join-Path $AppDir \"locales\$lang.json\"; ^
  if (-not (Test-Path $f)) { $f = Join-Path $AppDir 'locales\en.json' }; ^
  try { $d = Get-Content $f -Raw | ConvertFrom-Json; $v = $d.$key; if ($v) { return $v } } catch { }; ^
  return $key ^
}; ^
$notFound = RawT 'install.python_not_found'; ^
$installing = RawT 'install.python_installing'; ^
$failed = RawT 'install.python_failed'; ^
$restart = RawT 'install.python_restart'; ^
$quit = RawT 'shortcut.btn_quit'; ^
$hasWinget = $null -ne (Get-Command winget -ErrorAction SilentlyContinue); ^
if (-not $hasWinget) { ^
  [System.Windows.Forms.MessageBox]::Show($notFound + \"`n`nPlease download Python from https://www.python.org/downloads/`nMake sure to check 'Add Python to PATH'.\", $AppName, 'OK', 'Error'); ^
  exit 1 ^
}; ^
$r = [System.Windows.Forms.MessageBox]::Show($notFound, $AppName, 'YesNo', 'Question'); ^
if ($r -ne 'Yes') { exit 0 }; ^
$form = New-Object System.Windows.Forms.Form; ^
$form.Text = $AppName; ^
$form.Size = New-Object System.Drawing.Size(380, 100); ^
$form.StartPosition = 'CenterScreen'; ^
$form.FormBorderStyle = 'FixedDialog'; ^
$form.MaximizeBox = $false; $form.MinimizeBox = $false; $form.ControlBox = $false; ^
if (Test-Path $Icon) { $form.Icon = New-Object System.Drawing.Icon($Icon) }; ^
$lbl = New-Object System.Windows.Forms.Label; ^
$lbl.Text = $installing; $lbl.AutoSize = $true; ^
$lbl.Location = New-Object System.Drawing.Point(20, 25); ^
$lbl.Font = New-Object System.Drawing.Font('Segoe UI', 10); ^
$form.Controls.Add($lbl); ^
$form.Shown.Add({ ^
  $form.Refresh(); ^
  $p = Start-Process -FilePath 'winget' -ArgumentList 'install','--id','Python.Python.3.12','--accept-source-agreements','--accept-package-agreements' -PassThru -WindowStyle Hidden; ^
  $p.WaitForExit(); ^
  $form.Close() ^
}); ^
[void]$form.ShowDialog(); ^
$env:Path = [System.Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [System.Environment]::GetEnvironmentVariable('Path','User'); ^
$hasPython = $null -ne (Get-Command python -ErrorAction SilentlyContinue); ^
if (-not $hasPython) { ^
  [System.Windows.Forms.MessageBox]::Show($failed, $AppName, 'OK', 'Error'); ^
  exit 1 ^
}; ^
[System.Windows.Forms.MessageBox]::Show($restart, $AppName, 'OK', 'Information'); ^
exit 0"
    if errorlevel 1 exit /b 1
    :: Re-run after Python install (PATH refreshed by new cmd)
    start "" "%~f0" %*
    exit
)

:: Direct launch mode (called by desktop/start menu shortcut)
if "%~1"=="--launch" (
    start "" pythonw run.py
    exit
)

:: Inline PowerShell shortcut menu
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
"Add-Type -AssemblyName System.Windows.Forms; ^
Add-Type -AssemblyName System.Drawing; ^
$AppDir = '%APP_DIR%'; ^
$AppName = 'yt-dlp Convenient GUI'; ^
$Icon = Join-Path $AppDir 'assets\icon.ico'; ^
$Target = Join-Path $AppDir 'install.bat'; ^
$Desktop = Join-Path $env:USERPROFILE \"Desktop\$AppName.lnk\"; ^
$StartMenu = Join-Path $env:APPDATA \"Microsoft\Windows\Start Menu\Programs\$AppName.lnk\"; ^
$installed = (Test-Path $Desktop) -or (Test-Path $StartMenu); ^
$form = New-Object System.Windows.Forms.Form; ^
$form.Text = $AppName; ^
$form.Size = New-Object System.Drawing.Size(360, 240); ^
$form.StartPosition = 'CenterScreen'; ^
$form.FormBorderStyle = 'FixedDialog'; ^
$form.MaximizeBox = $false; ^
if (Test-Path $Icon) { $form.Icon = New-Object System.Drawing.Icon($Icon) }; ^
$label = New-Object System.Windows.Forms.Label; ^
$label.Text = 'What would you like to do?'; ^
$label.AutoSize = $true; ^
$label.Location = New-Object System.Drawing.Point(20, 20); ^
$label.Font = New-Object System.Drawing.Font('Segoe UI', 10); ^
$form.Controls.Add($label); ^
$y = 60; ^
$btnLaunch = New-Object System.Windows.Forms.Button; ^
$btnLaunch.Text = 'Launch the application'; ^
$btnLaunch.Size = New-Object System.Drawing.Size(300, 35); ^
$btnLaunch.Location = New-Object System.Drawing.Point(20, $y); ^
$btnLaunch.Add_Click({ $form.Tag = 'launch'; $form.Close() }); ^
$form.Controls.Add($btnLaunch); ^
$y += 45; ^
if ($installed) { ^
  $btn = New-Object System.Windows.Forms.Button; ^
  $btn.Text = 'Remove shortcuts'; ^
  $btn.Size = New-Object System.Drawing.Size(300, 35); ^
  $btn.Location = New-Object System.Drawing.Point(20, $y); ^
  $btn.Add_Click({ $form.Tag = 'remove'; $form.Close() }); ^
  $form.Controls.Add($btn) ^
} else { ^
  $btn = New-Object System.Windows.Forms.Button; ^
  $btn.Text = 'Create Desktop and Start Menu shortcuts'; ^
  $btn.Size = New-Object System.Drawing.Size(300, 35); ^
  $btn.Location = New-Object System.Drawing.Point(20, $y); ^
  $btn.Add_Click({ $form.Tag = 'install'; $form.Close() }); ^
  $form.Controls.Add($btn) ^
}; ^
$form.AcceptButton = $btnLaunch; ^
[void]$form.ShowDialog(); ^
switch ($form.Tag) { ^
  'launch' { Start-Process -FilePath 'pythonw' -ArgumentList 'run.py' -WorkingDirectory $AppDir } ^
  'install' { ^
    $ws = New-Object -ComObject WScript.Shell; ^
    foreach ($p in @($Desktop, $StartMenu)) { ^
      $s = $ws.CreateShortcut($p); ^
      $s.TargetPath = $Target; ^
      $s.Arguments = '--launch'; ^
      $s.WorkingDirectory = $AppDir; ^
      $s.WindowStyle = 7; ^
      if (Test-Path $Icon) { $s.IconLocation = $Icon }; ^
      $s.Description = 'Download videos and audio with yt-dlp'; ^
      $s.Save() ^
    }; ^
    [System.Windows.Forms.MessageBox]::Show('Shortcuts created! You can find the app on your Desktop and Start Menu.', $AppName, 'OK', 'Information'); ^
    Start-Process -FilePath 'pythonw' -ArgumentList 'run.py' -WorkingDirectory $AppDir ^
  } ^
  'remove' { ^
    Remove-Item -Path $Desktop -Force -ErrorAction SilentlyContinue; ^
    Remove-Item -Path $StartMenu -Force -ErrorAction SilentlyContinue; ^
    [System.Windows.Forms.MessageBox]::Show('Shortcuts removed.', $AppName, 'OK', 'Information') ^
  } ^
}"
