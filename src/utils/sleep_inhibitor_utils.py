"""
Cross-platform sleep inhibitor to prevent the system from sleeping during downloads.

Supported platforms:
- Linux: D-Bus (org.freedesktop.ScreenSaver) or systemd-inhibit fallback
- Windows: SetThreadExecutionState via ctypes
- macOS: caffeinate subprocess

Safety features:
- Context manager protocol (``with sleep_inhibitor: ...``)
- ``atexit`` hook to release the inhibitor on interpreter shutdown
- On Linux, child processes receive SIGTERM when the parent dies
  (via PR_SET_PDEATHSIG) so orphans are avoided even on hard crashes.
"""
import atexit
import signal
import subprocess
import sys
from typing import Optional


class SleepInhibitor:
    """Prevents the system from going to sleep while active.

    Can be used imperatively (``inhibit()`` / ``uninhibit()``) or as a
    context manager::

        with sleep_inhibitor:
            # system will not sleep
            do_long_download()
        # sleep re-enabled automatically, even on exception
    """

    def __init__(self):
        self._inhibited = False
        self._atexit_registered = False
        # Linux: cookie returned by D-Bus Inhibit(), or subprocess handle
        self._dbus_cookie: Optional[int] = None
        self._subprocess: Optional[subprocess.Popen] = None

    @property
    def is_inhibited(self) -> bool:
        return self._inhibited

    # ------------------------------------------------------------------
    # Context manager protocol
    # ------------------------------------------------------------------

    def __enter__(self):
        self.inhibit()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.uninhibit()
        return False  # do not suppress exceptions

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def inhibit(self) -> bool:
        """Prevent the system from sleeping. Returns True on success."""
        if self._inhibited:
            return True

        try:
            if sys.platform == 'win32':
                success = self._inhibit_windows()
            elif sys.platform == 'darwin':
                success = self._inhibit_macos()
            else:
                success = self._inhibit_linux()

            if success:
                self._inhibited = True
                self._register_atexit()
                print("Sleep inhibitor: system sleep prevented during download.")
            else:
                print("Sleep inhibitor: could not inhibit sleep (not critical).")
            return success
        except Exception as e:
            print(f"Sleep inhibitor: failed to inhibit — {e}")
            return False

    def uninhibit(self):
        """Allow the system to sleep again."""
        if not self._inhibited:
            return

        try:
            if sys.platform == 'win32':
                self._uninhibit_windows()
            elif sys.platform == 'darwin':
                self._uninhibit_macos()
            else:
                self._uninhibit_linux()
        except Exception as e:
            print(f"Sleep inhibitor: failed to uninhibit — {e}")
        finally:
            self._inhibited = False
            self._dbus_cookie = None
            self._subprocess = None
            print("Sleep inhibitor: system sleep re-enabled.")

    # ------------------------------------------------------------------
    # atexit safety net
    # ------------------------------------------------------------------

    def _register_atexit(self):
        """Register a one-time atexit handler to release the inhibitor."""
        if not self._atexit_registered:
            atexit.register(self._atexit_cleanup)
            self._atexit_registered = True

    def _atexit_cleanup(self):
        """Called by the interpreter on shutdown — best-effort cleanup."""
        try:
            self.uninhibit()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Windows
    # ------------------------------------------------------------------

    def _inhibit_windows(self) -> bool:
        import ctypes
        ES_CONTINUOUS = 0x80000000
        ES_SYSTEM_REQUIRED = 0x00000001
        result = ctypes.windll.kernel32.SetThreadExecutionState(
            ES_CONTINUOUS | ES_SYSTEM_REQUIRED
        )
        return result != 0

    def _uninhibit_windows(self):
        import ctypes
        ES_CONTINUOUS = 0x80000000
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)

    # ------------------------------------------------------------------
    # Subprocess helper
    # ------------------------------------------------------------------

    @staticmethod
    def _make_pdeathsig_fn():
        """Return a preexec_fn that sets PR_SET_PDEATHSIG on Linux.

        When the parent process dies (even SIGKILL), the kernel sends
        SIGTERM to the child, preventing orphan processes.
        """
        if sys.platform == 'linux':
            import ctypes
            import ctypes.util
            PR_SET_PDEATHSIG = 1
            libc_name = ctypes.util.find_library('c')
            if libc_name:
                libc = ctypes.CDLL(libc_name, use_errno=True)
                def _set_pdeathsig():
                    libc.prctl(PR_SET_PDEATHSIG, signal.SIGTERM)
                return _set_pdeathsig
        return None

    # ------------------------------------------------------------------
    # macOS
    # ------------------------------------------------------------------

    def _inhibit_macos(self) -> bool:
        self._subprocess = subprocess.Popen(
            ['caffeinate', '-i'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return self._subprocess.poll() is None

    def _uninhibit_macos(self):
        if self._subprocess:
            self._subprocess.terminate()
            self._subprocess.wait(timeout=5)

    # ------------------------------------------------------------------
    # Linux (D-Bus → systemd-inhibit fallback)
    # ------------------------------------------------------------------

    def _inhibit_linux(self) -> bool:
        """Try D-Bus ScreenSaver interface, then systemd-inhibit as fallback."""
        if self._inhibit_linux_dbus():
            return True
        return self._inhibit_linux_systemd()

    def _inhibit_linux_dbus(self) -> bool:
        """Use org.freedesktop.ScreenSaver.Inhibit via gdbus."""
        try:
            result = subprocess.run(
                [
                    'gdbus', 'call', '--session',
                    '--dest', 'org.freedesktop.ScreenSaver',
                    '--object-path', '/org/freedesktop/ScreenSaver',
                    '--method', 'org.freedesktop.ScreenSaver.Inhibit',
                    'yt-dlp-convenient-GUI',
                    'Download in progress',
                ],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                # Output looks like "(uint32 123,)"
                cookie_str = result.stdout.strip().strip('()').rstrip(',')
                # Extract just the number
                parts = cookie_str.split()
                self._dbus_cookie = int(parts[-1].rstrip(','))
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired, ValueError, IndexError):
            pass
        return False

    def _uninhibit_linux_dbus(self):
        """Release the D-Bus inhibit cookie."""
        if self._dbus_cookie is None:
            return
        try:
            subprocess.run(
                [
                    'gdbus', 'call', '--session',
                    '--dest', 'org.freedesktop.ScreenSaver',
                    '--object-path', '/org/freedesktop/ScreenSaver',
                    '--method', 'org.freedesktop.ScreenSaver.UnInhibit',
                    str(self._dbus_cookie),
                ],
                capture_output=True, text=True, timeout=5,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    def _inhibit_linux_systemd(self) -> bool:
        """Fallback: spawn systemd-inhibit wrapping a sleep process."""
        try:
            self._subprocess = subprocess.Popen(
                [
                    'systemd-inhibit',
                    '--what=idle',
                    '--who=yt-dlp-convenient-GUI',
                    '--why=Download in progress',
                    'sleep', 'infinity',
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=self._make_pdeathsig_fn(),
            )
            return self._subprocess.poll() is None
        except FileNotFoundError:
            return False

    def _uninhibit_linux(self):
        if self._dbus_cookie is not None:
            self._uninhibit_linux_dbus()
        if self._subprocess:
            self._subprocess.terminate()
            try:
                self._subprocess.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._subprocess.kill()


# Module-level singleton
sleep_inhibitor = SleepInhibitor()
