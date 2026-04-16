"""
Startup utilities — dependency checking, installation, and update logic.

These functions move the work previously done by install.bat / install.sh into
Python so the GUI can display progress instead of a terminal window.
"""
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from typing import List, Optional, Callable

from utils.i18n_utils import t


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ComponentStatus:
    """Result of checking a single dependency."""
    name: str
    ok: bool
    version: str = ""
    message: str = ""


@dataclass
class StartupReport:
    """Aggregated result of all startup checks."""
    components: List[ComponentStatus] = field(default_factory=list)
    missing: List[str] = field(default_factory=list)
    update_available: bool = False
    update_commits: int = 0
    ytdlp_updated: bool = False

    @property
    def all_ok(self) -> bool:
        return len(self.missing) == 0


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def check_ffmpeg() -> ComponentStatus:
    """Check whether FFmpeg is available."""
    path = shutil.which("ffmpeg")
    if path:
        try:
            out = subprocess.check_output(
                ["ffmpeg", "-version"], stderr=subprocess.DEVNULL, text=True
            )
            version = out.splitlines()[0] if out else ""
            return ComponentStatus("ffmpeg", True, version)
        except Exception:
            return ComponentStatus("ffmpeg", True)
    return ComponentStatus("ffmpeg", False, message="ffmpeg not found in PATH")


def check_deno() -> ComponentStatus:
    """Check whether Deno is available (needed for YouTube signature solving)."""
    # Ensure ~/.deno/bin is on PATH
    deno_bin = os.path.join(os.path.expanduser("~"), ".deno", "bin")
    if os.path.isdir(deno_bin) and deno_bin not in os.environ.get("PATH", ""):
        os.environ["PATH"] = deno_bin + os.pathsep + os.environ.get("PATH", "")

    path = shutil.which("deno")
    if path:
        try:
            out = subprocess.check_output(
                ["deno", "--version"], stderr=subprocess.DEVNULL, text=True
            )
            version = out.splitlines()[0] if out else ""
            return ComponentStatus("deno", True, version)
        except Exception:
            return ComponentStatus("deno", True)
    return ComponentStatus("deno", False, message="deno not found")


def check_ytdlp() -> ComponentStatus:
    """Check whether yt-dlp Python package is importable."""
    try:
        import yt_dlp  # noqa: F401
        version = getattr(yt_dlp.version, "__version__", "") if hasattr(yt_dlp, "version") else ""
        return ComponentStatus("yt-dlp", True, version=version)
    except ImportError:
        return ComponentStatus("yt-dlp", False, message="yt-dlp not importable")


def run_all_checks() -> StartupReport:
    """Run every startup check and return an aggregated report."""
    report = StartupReport()
    for checker in (check_ffmpeg, check_deno, check_ytdlp):
        status = checker()
        report.components.append(status)
        if not status.ok:
            report.missing.append(status.name)
    return report


# ---------------------------------------------------------------------------
# Installation helpers (non-blocking wrappers around system commands)
# ---------------------------------------------------------------------------

def _run(cmd: List[str], **kwargs) -> subprocess.CompletedProcess:
    """Run a command, suppressing the console window on Windows."""
    startupinfo = None
    if sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        startupinfo=startupinfo,
        **kwargs,
    )


def install_ffmpeg(on_progress: Optional[Callable[[str], None]] = None) -> bool:
    """Attempt to install FFmpeg using the system package manager."""
    if sys.platform == "win32":
        return _install_ffmpeg_windows(on_progress)
    elif sys.platform == "darwin":
        return _install_with_brew("ffmpeg", on_progress)
    else:
        return _install_ffmpeg_linux(on_progress)


def _install_ffmpeg_windows(on_progress: Optional[Callable[[str], None]] = None) -> bool:
    """Download and install FFmpeg into a local ffmpeg/bin directory on Windows."""
    try:
        if on_progress:
            on_progress(t("startup.downloading_ffmpeg"))
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        ffmpeg_bin = os.path.join(project_root, "ffmpeg", "bin")
        os.makedirs(ffmpeg_bin, exist_ok=True)
        temp_dir = os.path.join(project_root, "temp")
        os.makedirs(temp_dir, exist_ok=True)
        zip_path = os.path.join(temp_dir, "ffmpeg.zip")

        _run([
            "powershell", "-Command",
            f"$ProgressPreference='SilentlyContinue'; "
            f"Invoke-WebRequest -Uri 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip' "
            f"-OutFile '{zip_path}'"
        ])

        if not os.path.isfile(zip_path):
            return False

        if on_progress:
            on_progress(t("startup.extracting_ffmpeg"))
        extract_dir = os.path.join(temp_dir, "ffmpeg-extract")
        _run([
            "powershell", "-Command",
            f"Expand-Archive -Path '{zip_path}' -DestinationPath '{extract_dir}' -Force"
        ])

        # Copy binaries
        for entry in os.listdir(extract_dir):
            bin_src = os.path.join(extract_dir, entry, "bin")
            if os.path.isdir(bin_src):
                for f in os.listdir(bin_src):
                    shutil.copy2(os.path.join(bin_src, f), ffmpeg_bin)
                break

        # Add to PATH for this session
        os.environ["PATH"] = ffmpeg_bin + os.pathsep + os.environ.get("PATH", "")

        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)
        return shutil.which("ffmpeg") is not None
    except Exception:
        return False


def _install_ffmpeg_linux(on_progress: Optional[Callable[[str], None]] = None) -> bool:
    """Install FFmpeg via the detected Linux package manager."""
    if on_progress:
        on_progress(t("startup.installing_ffmpeg"))
    pm = _detect_linux_pm()
    if pm == "apt":
        r = _run(["sudo", "-n", "apt", "install", "-y", "ffmpeg"])
    elif pm == "dnf":
        r = _run(["sudo", "-n", "dnf", "install", "-y", "ffmpeg"])
    elif pm == "pacman":
        r = _run(["sudo", "-n", "pacman", "-S", "--noconfirm", "ffmpeg"])
    else:
        return False
    return r.returncode == 0


def _install_with_brew(formula: str, on_progress: Optional[Callable[[str], None]] = None) -> bool:
    if on_progress:
        on_progress(t("startup.installing_formula", name=formula))
    r = _run(["brew", "install", formula])
    return r.returncode == 0


def install_deno(on_progress: Optional[Callable[[str], None]] = None) -> bool:
    """Install Deno using the official installer script."""
    if on_progress:
        on_progress(t("startup.installing_deno"))
    try:
        if sys.platform == "win32":
            _run(["powershell", "-Command", "irm https://deno.land/install.ps1 | iex"])
        else:
            _run(["sh", "-c", "curl -fsSL https://deno.land/install.sh | sh"])
        # Add to PATH
        deno_bin = os.path.join(os.path.expanduser("~"), ".deno", "bin")
        if os.path.isdir(deno_bin):
            os.environ["PATH"] = deno_bin + os.pathsep + os.environ.get("PATH", "")
        return shutil.which("deno") is not None
    except Exception:
        return False


def update_ytdlp(on_progress: Optional[Callable[[str], None]] = None) -> bool:
    """Upgrade yt-dlp and yt-dlp-ejs via pip."""
    if on_progress:
        on_progress(t("startup.updating_ytdlp_pip"))
    try:
        r = _run([sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp", "yt-dlp-ejs"])
        return r.returncode == 0
    except Exception:
        return False


def install_requirements(on_progress: Optional[Callable[[str], None]] = None) -> bool:
    """Install all requirements.txt dependencies."""
    if on_progress:
        on_progress(t("startup.installing_deps"))
    req_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "requirements.txt"))
    if not os.path.isfile(req_file):
        return False
    try:
        r = _run([sys.executable, "-m", "pip", "install", "-r", req_file])
        return r.returncode == 0
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Git update helpers
# ---------------------------------------------------------------------------

def check_git_updates() -> tuple:
    """Check for Git-based app updates.

    Returns (commits_behind: int, remote_branch: str | None).
    0 means up-to-date, -1 means could not check.
    """
    if not shutil.which("git"):
        return (-1, None)

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

    try:
        r = _run(["git", "rev-parse", "--is-inside-work-tree"], cwd=project_root)
        if r.returncode != 0:
            return (-1, None)
    except Exception:
        return (-1, None)

    # Fetch
    fetch = _run(["git", "fetch", "origin"], cwd=project_root)
    if fetch.returncode != 0:
        return (-1, None)

    # Determine remote branch
    remote_branch = None
    for branch in ("origin/main", "origin/master"):
        r = _run(["git", "rev-parse", branch], cwd=project_root)
        if r.returncode == 0:
            remote_branch = branch
            break
    if not remote_branch:
        return (-1, None)

    # Compare
    local = _run(["git", "rev-parse", "HEAD"], cwd=project_root).stdout.strip()
    remote = _run(["git", "rev-parse", remote_branch], cwd=project_root).stdout.strip()
    if local == remote:
        return (0, remote_branch)

    behind = _run(["git", "rev-list", "--count", f"HEAD..{remote_branch}"], cwd=project_root)
    try:
        count = int(behind.stdout.strip())
    except ValueError:
        count = 1
    return (count, remote_branch)


def apply_git_update(remote_branch: str) -> bool:
    """Hard-reset to the remote branch."""
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    r = _run(["git", "reset", "--hard", remote_branch], cwd=project_root)
    return r.returncode == 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _detect_linux_pm() -> Optional[str]:
    """Detect the Linux package manager available on this system."""
    for pm in ("apt", "dnf", "pacman", "zypper", "xbps-install", "apk"):
        if shutil.which(pm):
            return pm
    return None
