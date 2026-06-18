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
$AppId   = 'nicolasgth.ytdlp-convenient-gui'
$Icon    = Join-Path $AppDir 'assets\icon.ico'

# P/Invoke to write AppUserModelID into a .lnk shortcut so the
# taskbar recognises the process and pins the correct icon.
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;

public static class ShortcutHelper
{
    [ComImport, Guid("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99")]
    [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IPropertyStore
    {
        void GetCount(out uint cProps);
        void GetAt(uint iProp, out PROPERTYKEY pkey);
        void GetValue(ref PROPERTYKEY key, out PROPVARIANT pv);
        void SetValue(ref PROPERTYKEY key, ref PROPVARIANT pv);
        void Commit();
    }

    [StructLayout(LayoutKind.Sequential, Pack = 4)]
    struct PROPERTYKEY
    {
        public Guid fmtid;
        public uint pid;
    }

    // Minimum PROPVARIANT for VT_LPWSTR — works x86 and x64
    [StructLayout(LayoutKind.Sequential)]
    struct PROPVARIANT
    {
        public ushort vt;
        public ushort wReserved1;
        public ushort wReserved2;
        public ushort wReserved3;
        public IntPtr pwszVal;
    }

    [DllImport("shell32.dll", CharSet = CharSet.Unicode)]
    static extern int SHGetPropertyStoreFromParsingName(
        string pszPath, IntPtr pbc, uint flags,
        ref Guid riid,
        [MarshalAs(UnmanagedType.Interface)] out IPropertyStore ppv);

    static readonly Guid _fmtid = new Guid("9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3");
    const uint _pid = 5;
    const uint GPS_READWRITE = 0x00000002;

    public static void SetAppUserModelId(string path, string appId)
    {
        Guid iid = typeof(IPropertyStore).GUID;
        IPropertyStore store;
        int hr = SHGetPropertyStoreFromParsingName(
            path, IntPtr.Zero, GPS_READWRITE, ref iid, out store);
        if (hr != 0)
            throw new InvalidOperationException(
                "SHGetPropertyStoreFromParsingName 0x" + hr.ToString("X8"));

        PROPERTYKEY key = new PROPERTYKEY { fmtid = _fmtid, pid = _pid };

        IntPtr pStr = Marshal.StringToCoTaskMemUni(appId);
        PROPVARIANT pv = new PROPVARIANT { vt = 31, pwszVal = pStr };

        store.SetValue(ref key, ref pv);
        Marshal.FreeCoTaskMem(pStr);
        store.Commit();

        if (Marshal.IsComObject(store))
            Marshal.ReleaseComObject(store);
    }
}
'@ -ReferencedAssemblies System.Runtime.InteropServices

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
        # Create a local launcher script so the shortcut never breaks
        # when the system Python path changes (e.g. Microsoft Store update).
        $launcher = Join-Path $AppDir 'launcher.vbs'
        $launcherContent = @"
' launcher.vbs for yt-dlp Convenient GUI
' Resolves pythonw.exe (venv first, then system PATH) and launches run.py silently.

Dim WshShell, FSO, AppDir, VenvPython, SysPython, Args

Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")

AppDir = FSO.GetParentFolderName(WScript.ScriptFullName)

' 1. Try venv pythonw first
VenvPython = FSO.BuildPath(AppDir, "venv\Scripts\pythonw.exe")
If FSO.FileExists(VenvPython) Then
    SysPython = VenvPython
Else
    ' 2. Fallback to system pythonw via PATH
    SysPython = "pythonw.exe"
End If

Args = """" & FSO.BuildPath(AppDir, "run.py") & """"

WshShell.CurrentDirectory = AppDir
WshShell.Run """" & SysPython & """ " & Args, 0, False
"@
        $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
        [IO.File]::WriteAllText($launcher, $launcherContent, $utf8NoBom)

        $ws = New-Object -ComObject WScript.Shell
        foreach ($p in @($Desktop, $StartMenu)) {
            $s = $ws.CreateShortcut($p)
            # Resolve pythonw.exe: prefer the venv copy (the final process that
            # actually hosts the main GUI), fall back to PATH-lookup pythonw.
            $pyw = Join-Path $AppDir 'venv\Scripts\pythonw.exe'
            if (Test-Path $pyw) {
                $s.TargetPath = $pyw
                $s.Arguments = "run.py"
            } else {
                $s.TargetPath = 'pythonw.exe'
                $s.Arguments = "run.py"
            }
            $s.WorkingDirectory = $AppDir
            $s.WindowStyle = 7
            if (Test-Path $Icon) { $s.IconLocation = $Icon }
            $s.Description = RawT 'shortcut.comment'
            $s.Save()

            # Bind the shortcut to our AppUserModelID so Windows
            # pins the shortcut instead of pythonw.exe.
            [ShortcutHelper]::SetAppUserModelId($p, $AppId)
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
