#!/usr/bin/env python3
"""
Single-click launcher for yt-dlp Convenient GUI.

This script handles the full bootstrap:
  1. Creates a virtual environment if needed
  2. Installs PySide6 (the only dep required to show the GUI)
  3. Launches the application

On Windows, all GUI feedback uses ctypes (Win32 API) so that
pythonw.exe can show dialogs without ever spawning a console window.
On Linux, zenity is used. On macOS, osascript.
"""
import os
import sys
import subprocess
import shutil
import venv

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_DIR = os.path.join(SCRIPT_DIR, "venv")
SRC_DIR = os.path.join(SCRIPT_DIR, "src")

# i18n is available without PySide6 — reuse the existing module.
sys.path.insert(0, SRC_DIR)
from utils.i18n_utils import t as _bootstrap_t
sys.path.pop(0)

# Platform-specific bootstrap GUI
if sys.platform == "win32":
    import _bootstrap_win32 as _gui
else:
    import _bootstrap_unix as _gui

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


def _find_best_python() -> str | None:
    """On macOS, find a Python 3.10+ interpreter (prefer Homebrew).
    Returns the path if found, None otherwise.
    """
    if sys.platform != "darwin":
        return None
    for candidate in ["/opt/homebrew/bin/python3", "/usr/local/bin/python3"]:
        if os.path.isfile(candidate):
            try:
                r = subprocess.run(
                    [candidate, "-c",
                     "import sys; print(sys.version_info >= (3,10))"],
                    capture_output=True, text=True, timeout=5,
                )
                if r.stdout.strip() == "True":
                    return candidate
            except Exception:
                continue
    return None


def _venv_python_version_ok() -> bool:
    """Check if the venv Python is 3.10+."""
    vpy = _venv_python()
    if not os.path.isfile(vpy):
        return True  # no venv yet — will be created fresh
    try:
        r = subprocess.run(
            [vpy, "-c", "import sys; print(sys.version_info >= (3,10))"],
            capture_output=True, text=True, timeout=5,
        )
        return r.stdout.strip() == "True"
    except Exception:
        return True


def _ensure_venv():
    """Create the virtual environment if it doesn't exist.
    On macOS, recreate the venv with a 3.10+ Python if needed.
    """
    # If the venv exists but uses Python < 3.10, try to recreate with a newer one
    if os.path.isfile(_venv_python()) and not _venv_python_version_ok():
        best = _find_best_python()
        if best:
            shutil.rmtree(VENV_DIR, ignore_errors=True)
            subprocess.run(
                [best, "-m", "venv", VENV_DIR],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            return

    if not os.path.isfile(_venv_python()):
        # Try using a modern Python on macOS
        best = _find_best_python()
        if best:
            subprocess.run(
                [best, "-m", "venv", VENV_DIR],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        else:
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
# Main
# ---------------------------------------------------------------------------

def main():
    # Must be called BEFORE any window (including the native splash) is
    # created, otherwise the taskbar button picks up the default id and
    # right-click  Pin to taskbar  will pin python/pythonw instead.
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "nicolasgth.ytdlp-convenient-gui")

    _gui.show_splash(_bootstrap_t("startup.loading"))

    _ensure_venv()

    if not _pyside6_available():
        _gui.close_splash()
        _gui.install_pyside6_with_gui(
            _pip_install_pyside6,
            _bootstrap_t("startup.installing_pyside6"),
        )
        _gui.show_splash(_bootstrap_t("startup.loading"))

    # Re-launch inside the venv if we're not already in it
    current_exe = os.path.abspath(sys.executable).lower()
    venv_dir_abs = os.path.abspath(VENV_DIR).lower()
    if not current_exe.startswith(venv_dir_abs):
        _gui.close_splash()
        app_main = os.path.join(SRC_DIR, "main.py")
        sys.exit(subprocess.call(
            [_venv_pythonw(), app_main],
            **_win_no_window_kwargs(),
        ))
    else:
        sys.path.insert(0, SRC_DIR)
        from main import main as app_main
        _gui.close_splash()
        app_main()


if __name__ == "__main__":
    main()
