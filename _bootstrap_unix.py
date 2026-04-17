"""
Unix bootstrap GUI — splash screen and PySide6 install dialog.

Uses zenity (Linux) or osascript (macOS) to show feedback.
"""
import shutil
import subprocess
import sys


def install_pyside6_with_gui(pip_install_fn, msg):
    """Show a progress dialog while *pip_install_fn* runs."""
    if shutil.which("zenity"):
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
        pip_install_fn()
        dialog.stdin.close()
        dialog.wait()

    elif sys.platform == "darwin" and shutil.which("osascript"):
        subprocess.Popen(
            ["osascript", "-e",
             f'display notification "{msg}" with title "yt-dlp Convenient GUI"'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        pip_install_fn()

    else:
        pip_install_fn()


def show_splash(loading_text):
    """No-op on Unix — PySide6 starts fast enough."""
    pass


def close_splash():
    """No-op on Unix."""
    pass
