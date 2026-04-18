"""
Unix bootstrap GUI — splash screen and PySide6 install dialog.

Uses zenity (Linux) or osascript (macOS) to show feedback.
"""
import shutil
import subprocess
import sys
import threading


def _osascript_progress(msg, pip_install_fn):
    """Show a native macOS progress dialog while *pip_install_fn* runs.

    Uses a bare ``display dialog`` (owned by the osascript process itself)
    so that terminating osascript reliably dismisses the dialog.
    """
    dialog = subprocess.Popen(
        ["osascript", "-e",
         f'display dialog "{msg}" with title "yt-dlp Convenient GUI" '
         'buttons {"Fermer"} giving up after 3600'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

    install_done = threading.Event()

    def do_install():
        try:
            pip_install_fn()
        finally:
            install_done.set()

    t = threading.Thread(target=do_install, daemon=True)
    t.start()
    install_done.wait()

    # Kill osascript → the dialog it owns disappears with it
    dialog.kill()
    dialog.wait()


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
        _osascript_progress(msg, pip_install_fn)

    else:
        pip_install_fn()


def show_splash(loading_text):
    """No-op on Unix — PySide6 starts fast enough."""
    pass


def close_splash():
    """No-op on Unix."""
    pass
