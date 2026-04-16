#!/usr/bin/env python3
"""
Single-click launcher for yt-dlp Convenient GUI.

This script handles the full bootstrap:
  1. Creates a virtual environment if needed
  2. Installs PySide6 (the only dep required to show the GUI)
  3. Launches the application

On Windows, all GUI feedback uses tkinter (bundled with Python) so that
pythonw.exe can show dialogs without ever spawning a console window.
On Linux, zenity is used. On macOS, osascript.
"""
import os
import sys
import subprocess
import threading
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


def _venv_pythonw() -> str:
    """Return the path to the windowless venv Python interpreter (Windows)."""
    if sys.platform == "win32":
        pw = os.path.join(VENV_DIR, "Scripts", "pythonw.exe")
        if os.path.isfile(pw):
            return pw
    return _venv_python()


def _win_no_window_kwargs() -> dict:
    """Return subprocess kwargs that prevent any console window on Windows."""
    if sys.platform != "win32":
        return {}
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return {
        "startupinfo": si,
        "creationflags": subprocess.CREATE_NO_WINDOW,
    }


def _ensure_venv():
    """Create the virtual environment if it doesn't exist."""
    if not os.path.isfile(_venv_python()):
        venv.create(VENV_DIR, with_pip=True)


def _pyside6_available() -> bool:
    """Check whether PySide6 is importable inside the venv."""
    r = subprocess.run(
        [_venv_pythonw(), "-c", "import PySide6"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        **_win_no_window_kwargs(),
    )
    return r.returncode == 0


def _pip_install_pyside6():
    """Run pip to upgrade pip and install PySide6 inside the venv."""
    kw = _win_no_window_kwargs()
    subprocess.run(
        [_venv_pythonw(), "-m", "pip", "install", "--upgrade", "pip"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        **kw,
    )
    subprocess.run(
        [_venv_pythonw(), "-m", "pip", "install", "PySide6>=6.5.0"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        **kw,
    )


# ---------------------------------------------------------------------------
# tkinter-based GUI helpers (no console window, works from pythonw.exe)
# ---------------------------------------------------------------------------

def _tk_root(title="yt-dlp Convenient GUI"):
    """Create a tkinter root window with the app icon."""
    import tkinter as tk
    root = tk.Tk()
    root.title(title)
    root.resizable(False, False)
    root.attributes("-topmost", True)
    icon_path = os.path.join(SCRIPT_DIR, "assets", "icon.ico")
    if os.path.isfile(icon_path):
        try:
            root.iconbitmap(icon_path)
        except tk.TclError:
            pass
    return root


def _install_pyside6_with_gui():
    """Install PySide6 inside the venv, showing a progress dialog."""
    import shutil

    msg = _bootstrap_t("startup.installing_pyside6")

    if sys.platform == "win32":
        # Windows — tkinter dialog (runs inside pythonw = no console at all)
        import tkinter as tk
        from tkinter import ttk

        root = _tk_root()
        root.geometry("380x100")
        root.protocol("WM_DELETE_WINDOW", lambda: None)  # prevent closing

        tk.Label(root, text=msg, font=("Segoe UI", 10)).pack(pady=(15, 5))
        bar = ttk.Progressbar(root, mode="indeterminate", length=320)
        bar.pack(pady=5)
        bar.start(20)

        def do_install():
            _pip_install_pyside6()
            root.after(0, root.destroy)

        threading.Thread(target=do_install, daemon=True).start()
        root.mainloop()

    elif shutil.which("zenity"):
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
        dialog.stdin.close()
        dialog.wait()

    elif sys.platform == "darwin" and shutil.which("osascript"):
        subprocess.Popen(
            ["osascript", "-e",
             f'display notification "{msg}" with title "yt-dlp Convenient GUI"'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        _pip_install_pyside6()

    else:
        _pip_install_pyside6()


# ---------------------------------------------------------------------------
# Splash screen (shown during bootstrap before PySide6 is ready)
# ---------------------------------------------------------------------------

_splash_root = None


def _show_splash():
    """Show a splash window while the app loads."""
    if sys.platform != "win32":
        return
    try:
        import tkinter as tk
        from tkinter import ttk

        global _splash_root
        root = _tk_root()
        root.geometry("340x90")
        root.protocol("WM_DELETE_WINDOW", lambda: None)

        bar = ttk.Progressbar(root, mode="indeterminate", length=280)
        bar.pack(pady=(18, 5))
        bar.start(20)

        msg = _bootstrap_t("startup.loading")
        tk.Label(root, text=msg, font=("Segoe UI", 9), fg="gray").pack()

        _splash_root = root
        root.update()
    except Exception:
        pass


def _close_splash():
    """Close the splash window if it's open."""
    global _splash_root
    if _splash_root is not None:
        try:
            _splash_root.destroy()
        except Exception:
            pass
        _splash_root = None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    _show_splash()

    _ensure_venv()

    if not _pyside6_available():
        _close_splash()
        _install_pyside6_with_gui()
        _show_splash()

    # Re-launch inside the venv if we're not already in it
    current_exe = os.path.abspath(sys.executable).lower()
    venv_dir_abs = os.path.abspath(VENV_DIR).lower()
    if not current_exe.startswith(venv_dir_abs):
        _close_splash()
        app_main = os.path.join(SRC_DIR, "main.py")
        sys.exit(subprocess.call(
            [_venv_pythonw(), app_main],
            **_win_no_window_kwargs(),
        ))
    else:
        sys.path.insert(0, SRC_DIR)
        from main import main as app_main
        _close_splash()
        app_main()


if __name__ == "__main__":
    main()
