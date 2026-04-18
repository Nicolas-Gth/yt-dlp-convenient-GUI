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
# Ensure Homebrew paths are available on macOS
# (.app bundles don't inherit the user's shell environment)
# ---------------------------------------------------------------------------
if sys.platform == "darwin":
    for _brew_dir in ("/opt/homebrew/bin", "/usr/local/bin"):
        if os.path.isdir(_brew_dir) and _brew_dir not in os.environ.get("PATH", ""):
            os.environ["PATH"] = _brew_dir + os.pathsep + os.environ.get("PATH", "")



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
# Subprocess helper
# ---------------------------------------------------------------------------

def _run(cmd: List[str], **kwargs) -> subprocess.CompletedProcess:
    """Run a command, suppressing the console window on Windows."""
    startupinfo = None
    creationflags = 0
    if sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        creationflags = subprocess.CREATE_NO_WINDOW
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        startupinfo=startupinfo,
        creationflags=creationflags,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def check_ffmpeg() -> ComponentStatus:
    """Check whether FFmpeg is available."""
    # Ensure the local ffmpeg/bin is on PATH (it may not be loaded from config yet)
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    local_ffmpeg_bin = os.path.join(project_root, "ffmpeg", "bin")
    if os.path.isdir(local_ffmpeg_bin) and local_ffmpeg_bin not in os.environ.get("PATH", ""):
        os.environ["PATH"] = local_ffmpeg_bin + os.pathsep + os.environ.get("PATH", "")

    path = shutil.which("ffmpeg")
    if path:
        try:
            r = _run(["ffmpeg", "-version"])
            version = r.stdout.splitlines()[0] if r.stdout else ""
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
            r = _run(["deno", "--version"])
            version = r.stdout.splitlines()[0] if r.stdout else ""
            return ComponentStatus("deno", True, version)
        except Exception:
            return ComponentStatus("deno", True)
    return ComponentStatus("deno", False, message="deno not found")


def check_ytdlp() -> ComponentStatus:
    """Check whether yt-dlp and companion Python packages are importable."""
    try:
        import yt_dlp  # noqa: F401
        version = getattr(yt_dlp.version, "__version__", "") if hasattr(yt_dlp, "version") else ""
    except ImportError:
        return ComponentStatus("yt-dlp", False, message="yt-dlp not importable")

    # Also verify other critical requirements.txt packages so
    # install_requirements is triggered when any of them is missing.
    # yt_dlp_ejs is excluded: it requires Python>=3.10 and is optional.
    for mod in ("PIL", "mutagen"):
        try:
            __import__(mod)
        except ImportError:
            return ComponentStatus("yt-dlp", False, message=f"{mod} not importable")

    return ComponentStatus("yt-dlp", True, version=version)


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


def install_ffmpeg(
    on_progress: Optional[Callable[[str], None]] = None,
    on_percent: Optional[Callable[[int], None]] = None,
    on_status: Optional[Callable[[str], None]] = None,
) -> bool:
    """Attempt to install FFmpeg using the system package manager."""
    if sys.platform == "win32":
        return _install_ffmpeg_windows(on_progress, on_percent, on_status)
    elif sys.platform == "darwin":
        return _install_with_brew("ffmpeg", on_progress, on_percent)
    else:
        return _install_ffmpeg_linux(on_progress)


def _download_with_progress(
    url: str,
    dest: str,
    on_progress: Optional[Callable[[str], None]] = None,
    on_percent: Optional[Callable[[int], None]] = None,
) -> bool:
    """Download *url* to *dest*, reporting percentage progress.

    Uses curl (ships with Windows 10+) for speed, falls back to urllib.
    """
    curl = shutil.which("curl")
    if curl:
        return _download_with_curl(curl, url, dest, on_percent)
    return _download_with_urllib(url, dest, on_percent)


def _download_with_curl(
    curl: str,
    url: str,
    dest: str,
    on_percent: Optional[Callable[[int], None]] = None,
) -> bool:
    """Download using system curl with progress bar parsing."""
    import re
    kw: dict = {}
    if sys.platform == "win32":
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        kw["startupinfo"] = si
        kw["creationflags"] = subprocess.CREATE_NO_WINDOW

    proc = subprocess.Popen(
        [curl, "-L", "-#", "-o", dest, url],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        **kw,
    )
    buf = b""
    pct_re = re.compile(rb"(\d+(?:\.\d+)?)\s*%")
    while True:
        chunk = proc.stderr.read(64)
        if not chunk:
            break
        buf += chunk
        # Keep only the latest carriage-return segment
        parts = buf.split(b"\r")
        buf = parts[-1]
        for part in parts[:-1]:
            m = pct_re.search(part)
            if m and on_percent:
                on_percent(min(int(float(m.group(1))), 100))
    proc.wait()
    return proc.returncode == 0 and os.path.isfile(dest)


def _download_with_urllib(
    url: str,
    dest: str,
    on_percent: Optional[Callable[[int], None]] = None,
) -> bool:
    """Fallback download using Python urllib."""
    import urllib.request

    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            chunk_size = 256 * 1024
            with open(dest, "wb") as fp:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    fp.write(chunk)
                    downloaded += len(chunk)
                    if total > 0 and on_percent:
                        on_percent(min(int(downloaded * 100 / total), 100))
        return os.path.isfile(dest)
    except Exception:
        return False


def _install_ffmpeg_windows(
    on_progress: Optional[Callable[[str], None]] = None,
    on_percent: Optional[Callable[[int], None]] = None,
    on_status: Optional[Callable[[str], None]] = None,
) -> bool:
    """Download and install FFmpeg into a local ffmpeg/bin directory on Windows."""
    import zipfile

    _MAX_RETRIES = 2
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    ffmpeg_bin = os.path.join(project_root, "ffmpeg", "bin")
    os.makedirs(ffmpeg_bin, exist_ok=True)
    temp_dir = os.path.join(project_root, "temp")
    os.makedirs(temp_dir, exist_ok=True)
    zip_path = os.path.join(temp_dir, "ffmpeg.zip")

    url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"

    for attempt in range(_MAX_RETRIES + 1):
        try:
            # Download
            ok = _download_with_progress(url, zip_path, on_progress, on_percent)
            if not ok:
                continue

            # Validate zip integrity before extracting
            if not zipfile.is_zipfile(zip_path):
                os.remove(zip_path)
                continue

            if on_status:
                on_status("extracting")
            if on_percent:
                on_percent(-1)

            # Extract only the binaries we need (ffmpeg, ffprobe, ffplay)
            with zipfile.ZipFile(zip_path, "r") as zf:
                for member in zf.namelist():
                    basename = os.path.basename(member)
                    if basename.lower() in ("ffmpeg.exe", "ffprobe.exe", "ffplay.exe"):
                        with zf.open(member) as src, open(os.path.join(ffmpeg_bin, basename), "wb") as dst:
                            shutil.copyfileobj(src, dst)

            # Add to PATH for this session
            os.environ["PATH"] = ffmpeg_bin + os.pathsep + os.environ.get("PATH", "")

            # Cleanup
            shutil.rmtree(temp_dir, ignore_errors=True)
            return shutil.which("ffmpeg") is not None
        except (zipfile.BadZipFile, OSError):
            if os.path.isfile(zip_path):
                os.remove(zip_path)
            continue

    shutil.rmtree(temp_dir, ignore_errors=True)
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


def _install_with_brew(
    formula: str,
    on_progress: Optional[Callable[[str], None]] = None,
    on_percent: Optional[Callable[[int], None]] = None,
) -> bool:
    """Install a Homebrew formula, parsing progress output.

    Tries a pseudo-TTY first for real-time progress; falls back to a plain
    subprocess.run() if the PTY approach fails (e.g. inside a QThread
    launched from a .app bundle).
    """
    # Resolve brew to an absolute path — shutil.which may fail inside .app
    brew = shutil.which("brew")
    if not brew:
        for candidate in ("/opt/homebrew/bin/brew", "/usr/local/bin/brew"):
            if os.path.isfile(candidate):
                brew = candidate
                break
    if not brew:
        if on_progress:
            on_progress("Homebrew not found — cannot install " + formula)
        return False

    if on_progress:
        on_progress(t("startup.installing_formula", name=formula))

    # Try the PTY approach for real-time progress
    try:
        result = _brew_install_pty(brew, formula, on_progress, on_percent)
        if result:
            return True
    except Exception:
        pass

    # Fallback: plain subprocess (no real-time progress, but reliable)
    if on_progress:
        on_progress(t("startup.installing_formula", name=formula))
    try:
        r = subprocess.run(
            [brew, "install", formula],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
            timeout=300,
        )
        return r.returncode == 0
    except Exception:
        return False


def _brew_install_pty(
    brew: str,
    formula: str,
    on_progress: Optional[Callable[[str], None]] = None,
    on_percent: Optional[Callable[[int], None]] = None,
) -> bool:
    """Run ``brew install`` with a pseudo-TTY for real-time output."""
    import pty
    import re
    import errno

    master_fd, slave_fd = pty.openpty()

    proc = subprocess.Popen(
        [brew, "install", formula],
        stdout=slave_fd,
        stderr=slave_fd,
        stdin=subprocess.DEVNULL,
    )
    os.close(slave_fd)

    # Modern brew (2024+) no longer prints "XX%" — it uses spinner + size.
    # We track progress by counting "Pouring" lines (one per bottle).
    # The total is parsed from "Installing dependencies for ..." which lists
    # dependencies.
    pct_re = re.compile(rb"(\d+(?:\.\d+)?)\s*%")
    # Match "Pouring xxx--version.bottle.tar.gz"
    pouring_re = re.compile(rb"Pouring\s+\S+")
    # Match "Installing dependencies for ffmpeg: dep1, dep2, ..."
    deps_re = re.compile(
        rb"Installing dependencies for[^:]*:\s*(.+)", re.IGNORECASE
    )
    total_bottles = 0
    poured_count = 0
    buf = b""
    while True:
        try:
            chunk = os.read(master_fd, 1024)
        except OSError as e:
            if e.errno == errno.EIO:
                break  # child closed the PTY
            raise
        if not chunk:
            break
        buf += chunk
        # Split on \r or \n to capture curl's carriage-return progress
        while b"\r" in buf or b"\n" in buf:
            idx_r = buf.find(b"\r")
            idx_n = buf.find(b"\n")
            if idx_r == -1:
                idx = idx_n
            elif idx_n == -1:
                idx = idx_r
            else:
                idx = min(idx_r, idx_n)
            seg = buf[:idx].strip()
            buf = buf[idx + 1:]
            if not seg:
                continue
            clean_seg = re.sub(rb"\x1b\[[0-9;]*[a-zA-Z]", b"", seg)
            clean_text = clean_seg.decode("utf-8", errors="replace").strip()

            # Try to detect total number of bottles from the deps line
            if total_bottles == 0:
                fm = deps_re.search(clean_seg)
                if fm:
                    # Count comma-separated dependency names + the formula itself
                    deps_text = fm.group(1).decode("utf-8", errors="replace")
                    total_bottles = len([
                        d for d in deps_text.split(",") if d.strip()
                    ]) + 1  # +1 for the formula itself

            # Count "Pouring" lines as progress steps
            if pouring_re.search(clean_seg):
                poured_count += 1
                if total_bottles > 0 and on_percent:
                    pct = min(int(poured_count / total_bottles * 100), 100)
                    on_percent(pct)

            # Legacy: also check for percentage patterns (older brew / curl)
            m = pct_re.search(seg)
            if m and on_percent:
                on_percent(min(int(float(m.group(1))), 100))
            elif on_progress:
                if clean_text:
                    on_progress(clean_text)

    os.close(master_fd)
    proc.wait()
    return proc.returncode == 0


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
    """Install all requirements.txt dependencies.

    Installs each requirement individually so that a single incompatible
    package (e.g. one requiring a newer Python) does not prevent the rest
    from being installed.
    """
    if on_progress:
        on_progress(t("startup.installing_deps"))
    req_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "requirements.txt"))
    if not os.path.isfile(req_file):
        return False
    try:
        with open(req_file) as f:
            lines = f.readlines()
    except OSError:
        return False

    all_ok = True
    for line in lines:
        pkg = line.strip()
        if not pkg or pkg.startswith("#"):
            continue
        try:
            r = _run([sys.executable, "-m", "pip", "install", pkg])
            if r.returncode != 0:
                all_ok = False
        except Exception:
            all_ok = False
    return all_ok


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
    try:
        fetch = _run(["git", "fetch", "origin"], cwd=project_root, timeout=15)
    except subprocess.TimeoutExpired:
        return (-1, None)
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
