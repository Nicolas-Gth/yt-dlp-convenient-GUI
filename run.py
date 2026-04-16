#!/usr/bin/env python3
"""
Single-click launcher for yt-dlp Convenient GUI.

This script handles the full bootstrap:
  1. Creates a virtual environment if needed
  2. Installs PySide6 (the only dep required to show the GUI)
  3. Launches the application

If PySide6 is not yet installed, an OS-native dialog (zenity on Linux,
PowerShell/WinForms on Windows, osascript on macOS) shows progress
so the user never has to see a terminal window.
"""
import os
import sys
import subprocess
import venv

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_DIR = os.path.join(SCRIPT_DIR, "venv")
SRC_DIR = os.path.join(SCRIPT_DIR, "src")

# i18n is available without PySide6 — reuse the existing module.
sys.path.insert(0, SRC_DIR)
from utils.i18n_utils import t as _bootstrap_t
sys.path.pop(0)

# ---------------------------------------------------------------------------
# Bootstrap helpers
# ---------------------------------------------------------------------------

def _venv_python() -> str:
    """Return the path to the venv Python interpreter."""
    if sys.platform == "win32":
        return os.path.join(VENV_DIR, "Scripts", "python.exe")
    return os.path.join(VENV_DIR, "bin", "python")


def _ensure_venv():
    """Create the virtual environment if it doesn't exist."""
    if not os.path.isfile(_venv_python()):
        venv.create(VENV_DIR, with_pip=True)


def _pyside6_available() -> bool:
    """Check whether PySide6 is importable inside the venv."""
    r = subprocess.run(
        [_venv_python(), "-c", "import PySide6"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return r.returncode == 0


def _pip_install_pyside6():
    """Run pip to upgrade pip and install PySide6 inside the venv."""
    subprocess.run(
        [_venv_python(), "-m", "pip", "install", "--upgrade", "pip"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    subprocess.run(
        [_venv_python(), "-m", "pip", "install", "PySide6>=6.5.0"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def _install_pyside6_with_gui():
    """Install PySide6 inside the venv, showing an OS-native progress dialog."""
    import shutil

    msg = _bootstrap_t("startup.installing_pyside6")

    if sys.platform == "win32":
        # Windows — PowerShell popup with marquee progress bar
        ps_script = '''
Add-Type -AssemblyName System.Windows.Forms
$form = New-Object System.Windows.Forms.Form
$form.Text = "yt-dlp Convenient GUI"
$form.Size = New-Object System.Drawing.Size(380, 120)
$form.StartPosition = "CenterScreen"
$form.FormBorderStyle = "FixedDialog"
$form.MaximizeBox = $false
$form.MinimizeBox = $false
$label = New-Object System.Windows.Forms.Label
$label.Text = "''' + msg.replace('"', '`"') + '''"
$label.AutoSize = $true
$label.Location = New-Object System.Drawing.Point(20, 15)
$form.Controls.Add($label)
$bar = New-Object System.Windows.Forms.ProgressBar
$bar.Style = "Marquee"
$bar.MarqueeAnimationSpeed = 30
$bar.Location = New-Object System.Drawing.Point(20, 45)
$bar.Size = New-Object System.Drawing.Size(320, 25)
$form.Controls.Add($bar)
$form.Show()
$form.Refresh()
[Console]::In.ReadLine()
$form.Close()
'''
        dialog = subprocess.Popen(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        _pip_install_pyside6()
        dialog.stdin.write(b"\n")
        dialog.stdin.close()
        dialog.wait()

    elif shutil.which("zenity"):
        # Linux/macOS with zenity
        dialog = subprocess.Popen(
            [
                "zenity", "--progress", "--pulsate", "--no-cancel", "--auto-close",
                "--title=yt-dlp Convenient GUI",
                "--text=" + msg,
                "--width=360",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        _pip_install_pyside6()
        # Close the dialog by closing stdin (triggers auto-close)
        dialog.stdin.close()
        dialog.wait()

    elif sys.platform == "darwin" and shutil.which("osascript"):
        # macOS without zenity — AppleScript notification
        subprocess.Popen(
            ["osascript", "-e",
             f'display notification "{msg}" with title "yt-dlp Convenient GUI"'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        _pip_install_pyside6()

    else:
        # No dialog tool available — install silently
        _pip_install_pyside6()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    _ensure_venv()

    if not _pyside6_available():
        _install_pyside6_with_gui()

    # Re-launch inside the venv if we're not already in it
    venv_python = _venv_python()
    if os.path.abspath(sys.executable) != os.path.abspath(venv_python):
        app_main = os.path.join(SRC_DIR, "main.py")
        sys.exit(subprocess.call([venv_python, app_main]))
    else:
        # We're already in the venv — just run
        sys.path.insert(0, SRC_DIR)
        from main import main as app_main
        app_main()


if __name__ == "__main__":
    main()
