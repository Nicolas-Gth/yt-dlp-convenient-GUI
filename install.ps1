# yt-dlp Convenient GUI — Windows installer & shortcut manager
#
# Usage:
#   Right-click → Run with PowerShell   (or: powershell -ExecutionPolicy Bypass -File install.ps1)
#   install.ps1                          → Show menu (create shortcuts / launch app)
#   install.ps1 -Launch                  → Launch the app directly (used by shortcuts)

param([switch]$Launch)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$AppDir  = Split-Path -Parent $MyInvocation.MyCommand.Definition
$AppName = 'yt-dlp Convenient GUI'
$Icon    = Join-Path $AppDir 'assets\icon.ico'

# -------------------------------------------------------------------
# i18n helper (works before Python is available)
# -------------------------------------------------------------------
function RawT([string]$key) {
    $lang = 'en'
    $cfg  = Join-Path $AppDir 'yt-dlp-gui-config.json'
    if (Test-Path $cfg) {
        try {
            $j = Get-Content $cfg -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($j.language -and $j.language -ne 'system') { $lang = $j.language }
            else { $lang = (Get-Culture).TwoLetterISOLanguageName }
        } catch { }
    } else {
        $lang = (Get-Culture).TwoLetterISOLanguageName
    }
    $f = Join-Path $AppDir "locales\$lang.json"
    if (-not (Test-Path $f)) { $f = Join-Path $AppDir 'locales\en.json' }
    try {
        $d = Get-Content $f -Raw -Encoding UTF8 | ConvertFrom-Json
        $v = $d.$key
        if ($v) { return $v }
    } catch { }
    return $key
}

function NewIcon {
    if (Test-Path $Icon) { return (New-Object System.Drawing.Icon($Icon)) }
    return $null
}

# -------------------------------------------------------------------
# Ensure Python 3 is installed
# -------------------------------------------------------------------
$hasPython = $null -ne (Get-Command python -ErrorAction SilentlyContinue)
if (-not $hasPython) {
    $notFound  = RawT 'install.python_not_found'
    $installing = RawT 'install.python_installing'
    $failed    = RawT 'install.python_failed'
    $restart   = RawT 'install.python_restart'

    $hasWinget = $null -ne (Get-Command winget -ErrorAction SilentlyContinue)
    if (-not $hasWinget) {
        [System.Windows.Forms.MessageBox]::Show(
            ($notFound + "`n`nPlease download Python from https://www.python.org/downloads/`nMake sure to check 'Add Python to PATH'."),
            $AppName, 'OK', 'Error')
        exit 1
    }

    $reply = [System.Windows.Forms.MessageBox]::Show($notFound, $AppName, 'YesNo', 'Question')
    if ($reply -ne 'Yes') { exit 0 }

    # Progress dialog with a Timer polling the winget process
    $form = New-Object System.Windows.Forms.Form
    $form.Text = $AppName
    $form.Size = New-Object System.Drawing.Size(380, 100)
    $form.StartPosition = 'CenterScreen'
    $form.FormBorderStyle = 'FixedDialog'
    $form.MaximizeBox = $false; $form.MinimizeBox = $false; $form.ControlBox = $false
    $ico = NewIcon; if ($ico) { $form.Icon = $ico }

    $lbl = New-Object System.Windows.Forms.Label
    $lbl.Text = $installing; $lbl.AutoSize = $true
    $lbl.Location = New-Object System.Drawing.Point(20, 25)
    $lbl.Font = New-Object System.Drawing.Font('Segoe UI', 10)
    $form.Controls.Add($lbl)

    $bar = New-Object System.Windows.Forms.ProgressBar
    $bar.Style = 'Marquee'; $bar.MarqueeAnimationSpeed = 30
    $bar.Location = New-Object System.Drawing.Point(20, 50)
    $bar.Size = New-Object System.Drawing.Size(320, 20)
    $form.Controls.Add($bar)
    $form.Size = New-Object System.Drawing.Size(380, 115)

    $proc = Start-Process -FilePath 'winget' `
        -ArgumentList 'install','--id','Python.Python.3.12','--accept-source-agreements','--accept-package-agreements' `
        -PassThru -WindowStyle Hidden

    $timer = New-Object System.Windows.Forms.Timer
    $timer.Interval = 500
    $timer.Add_Tick({
        if ($proc.HasExited) { $timer.Stop(); $form.Close() }
    })
    $timer.Start()
    [void]$form.ShowDialog()

    # Refresh PATH
    $env:Path = [System.Environment]::GetEnvironmentVariable('Path','Machine') + ';' +
                [System.Environment]::GetEnvironmentVariable('Path','User')

    $hasPython = $null -ne (Get-Command python -ErrorAction SilentlyContinue)
    if (-not $hasPython) {
        [System.Windows.Forms.MessageBox]::Show($failed, $AppName, 'OK', 'Error')
        exit 1
    }
    [System.Windows.Forms.MessageBox]::Show($restart, $AppName, 'OK', 'Information')
    # Re-run ourselves
    Start-Process -FilePath 'powershell' -ArgumentList '-ExecutionPolicy','Bypass','-File',$MyInvocation.MyCommand.Definition -WindowStyle Hidden
    exit 0
}

# -------------------------------------------------------------------
# Direct launch mode (called by desktop/start menu shortcut)
# -------------------------------------------------------------------
if ($Launch) {
    Set-Location $AppDir
    Start-Process -FilePath 'pythonw' -ArgumentList 'run.py' -WorkingDirectory $AppDir -WindowStyle Hidden
    exit 0
}

# -------------------------------------------------------------------
# Shortcut menu
# -------------------------------------------------------------------
$Target    = Join-Path $AppDir 'install.ps1'
$Desktop   = Join-Path ([Environment]::GetFolderPath('Desktop')) "$AppName.lnk"
$StartMenu = Join-Path ([Environment]::GetFolderPath('Programs')) "$AppName.lnk"
$installed = (Test-Path $Desktop) -or (Test-Path $StartMenu)

$form = New-Object System.Windows.Forms.Form
$form.Text = $AppName
$form.Size = New-Object System.Drawing.Size(360, 240)
$form.StartPosition = 'CenterScreen'
$form.FormBorderStyle = 'FixedDialog'
$form.MaximizeBox = $false
$ico = NewIcon; if ($ico) { $form.Icon = $ico }

$label = New-Object System.Windows.Forms.Label
$label.Text = RawT 'shortcut.create'
$label.AutoSize = $true
$label.Location = New-Object System.Drawing.Point(20, 20)
$label.Font = New-Object System.Drawing.Font('Segoe UI', 10)
$form.Controls.Add($label)

$y = 60

$btnLaunch = New-Object System.Windows.Forms.Button
$btnLaunch.Text = RawT 'shortcut.btn_launch'
$btnLaunch.Size = New-Object System.Drawing.Size(300, 35)
$btnLaunch.Location = New-Object System.Drawing.Point(20, $y)
$btnLaunch.Add_Click({ $form.Tag = 'launch'; $form.Close() })
$form.Controls.Add($btnLaunch)
$y += 45

if ($installed) {
    $btn = New-Object System.Windows.Forms.Button
    $btn.Text = RawT 'shortcut.btn_remove'
    $btn.Size = New-Object System.Drawing.Size(300, 35)
    $btn.Location = New-Object System.Drawing.Point(20, $y)
    $btn.Add_Click({ $form.Tag = 'remove'; $form.Close() })
    $form.Controls.Add($btn)
} else {
    $btn = New-Object System.Windows.Forms.Button
    $btn.Text = RawT 'shortcut.btn_create'
    $btn.Size = New-Object System.Drawing.Size(300, 35)
    $btn.Location = New-Object System.Drawing.Point(20, $y)
    $btn.Add_Click({ $form.Tag = 'install'; $form.Close() })
    $form.Controls.Add($btn)
}
$y += 45

$btnQuit = New-Object System.Windows.Forms.Button
$btnQuit.Text = RawT 'shortcut.btn_quit'
$btnQuit.Size = New-Object System.Drawing.Size(300, 35)
$btnQuit.Location = New-Object System.Drawing.Point(20, $y)
$btnQuit.Add_Click({ $form.Tag = 'quit'; $form.Close() })
$form.Controls.Add($btnQuit)

$form.AcceptButton = $btnLaunch
[void]$form.ShowDialog()

switch ($form.Tag) {
    'launch' {
        Start-Process -FilePath 'pythonw' -ArgumentList 'run.py' -WorkingDirectory $AppDir -WindowStyle Hidden
    }
    'install' {
        $ws = New-Object -ComObject WScript.Shell
        # Find pythonw.exe next to python.exe
        $pythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
        $pythonw = Join-Path (Split-Path $pythonExe) 'pythonw.exe'
        $runpy = Join-Path $AppDir 'run.py'
        foreach ($p in @($Desktop, $StartMenu)) {
            $s = $ws.CreateShortcut($p)
            # Shortcut launches pythonw directly — no PowerShell, no console flash
            $s.TargetPath = $pythonw
            $s.Arguments = "`"$runpy`""
            $s.WorkingDirectory = $AppDir
            $s.WindowStyle = 7
            if (Test-Path $Icon) { $s.IconLocation = $Icon }
            $s.Description = RawT 'shortcut.comment'
            $s.Save()
        }
        [System.Windows.Forms.MessageBox]::Show(
            (RawT 'shortcut.created'), $AppName, 'OK', 'Information')
    }
    'remove' {
        Remove-Item -Path $Desktop -Force -ErrorAction SilentlyContinue
        Remove-Item -Path $StartMenu -Force -ErrorAction SilentlyContinue
        [System.Windows.Forms.MessageBox]::Show(
            (RawT 'shortcut.removed'), $AppName, 'OK', 'Information')
    }
}
