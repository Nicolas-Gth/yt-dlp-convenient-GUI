"""
Soulseek integration via slskd.

slskd is a self-hosted Soulseek client daemon that exposes a REST API. This
module manages its lifecycle (download, launch, configure) and provides a thin
HTTP client for searching and downloading.

The app downloads the platform-specific slskd binary on first use, launches it
as a background subprocess bound to localhost, and talks to it over HTTP. The
user's Soulseek credentials are passed to the subprocess via environment
variables (never logged) and are not persisted by this module.
"""
import json
import os
import platform
import socket
import stat
import subprocess
import sys
import urllib.request
import urllib.error
import urllib.parse
import zipfile
from typing import Optional, Dict, List, Callable

_SLSKD_RELEASES_API = "https://api.github.com/repos/slskd/slskd/releases/latest"
_SLSKD_BINARY = "slskd.exe" if sys.platform == "win32" else "slskd"
_TIMEOUT = 15

# Search states that indicate a search has finished (prefix "Completed").
_COMPLETED_STATES = (
    "Completed, NoMoreResults",
    "Completed, Faulted",
    "Completed, Cancelled",
    "Completed, TimedOut",
    "Completed, FileLimitReached",
    "Completed, ResponseLimitReached",
)


def _project_root() -> str:
    """Return the application root directory (parent of src/)."""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def slskd_dir() -> str:
    """Directory where the slskd binary and its data live."""
    return os.path.join(_project_root(), "slskd")


def slskd_binary_path() -> str:
    return os.path.join(slskd_dir(), _SLSKD_BINARY)


def slskd_downloads_dir() -> str:
    """Directory where slskd writes downloaded files (staging)."""
    return os.path.join(slskd_dir(), "downloads")


def is_slskd_installed() -> bool:
    return os.path.isfile(slskd_binary_path())


def _platform_key() -> str:
    """Return the slskd asset platform token, e.g. 'linux-x64', 'win-x64'."""
    if sys.platform == "win32":
        os_key = "win"
    elif sys.platform == "darwin":
        os_key = "osx"
    else:
        os_key = "linux"

    machine = (platform.machine() or "").lower()
    if machine in ("x86_64", "amd64", "x64"):
        arch = "x64"
    elif machine in ("aarch64", "arm64"):
        arch = "arm64"
    elif machine.startswith("arm"):
        arch = "arm"
    else:
        arch = "x64"
    return f"{os_key}-{arch}"


def _download(url: str, timeout: int = _TIMEOUT, accept: Optional[str] = None) -> Optional[bytes]:
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "yt-dlp-convenient-GUI")
    if accept:
        req.add_header("Accept", accept)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception as e:
        print(f"[soulseek] download failed: {e}")
        return None


def _latest_asset() -> Optional[Dict]:
    """Return the asset dict matching the current platform, or None."""
    data = _download(_SLSKD_RELEASES_API, timeout=20, accept="application/vnd.github+json")
    if not data:
        return None
    try:
        release = json.loads(data)
    except Exception:
        return None
    tag = release.get("tag_name", "")
    key = _platform_key()
    for asset in release.get("assets", []):
        name = asset.get("name", "")
        # e.g. "slskd-0.26.0-linux-x64.zip" -> match trailing "linux-x64.zip"
        if name == f"slskd-{tag}-{key}.zip":
            return asset
    # Fallback: match by suffix in case naming changes slightly.
    for asset in release.get("assets", []):
        name = asset.get("name", "")
        if name.endswith(f"-{key}.zip"):
            return asset
    return None


def download_slskd(progress_cb: Optional[Callable[[int, int], None]] = None) -> str:
    """Download and extract the slskd binary. Returns the binary path.

    Raises RuntimeError on failure.
    """
    asset = _latest_asset()
    if not asset:
        raise RuntimeError("No slskd binary found for this platform.")

    url = asset.get("browser_download_url")
    total = int(asset.get("size", 0))
    if not url:
        raise RuntimeError("No download URL for slskd binary.")

    if progress_cb:
        progress_cb(0, total)
    data = _download(url, timeout=600, accept="application/octet-stream")
    if not data:
        raise RuntimeError("Failed to download slskd binary.")

    if progress_cb:
        progress_cb(len(data), total)

    target_dir = slskd_dir()
    os.makedirs(target_dir, exist_ok=True)
    zip_path = os.path.join(target_dir, "slskd.zip")
    with open(zip_path, "wb") as f:
        f.write(data)
    try:
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(target_dir)
    finally:
        try:
            os.remove(zip_path)
        except OSError:
            pass

    binary = slskd_binary_path()
    if not os.path.isfile(binary):
        raise RuntimeError("slskd binary not found after extraction.")

    # Make executable on Unix.
    if sys.platform != "win32":
        try:
            os.chmod(binary, os.stat(binary).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        except OSError:
            pass
    return binary


def _free_port() -> int:
    """Return an available TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class SlskdServer:
    """Manages the slskd subprocess and exposes its base URL."""

    def __init__(self):
        self._proc: Optional[subprocess.Popen] = None
        self._port: Optional[int] = None

    @property
    def port(self) -> Optional[int]:
        return self._port

    @property
    def base_url(self) -> Optional[str]:
        if self._port is None:
            return None
        return f"http://127.0.0.1:{self._port}"

    @property
    def running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def start(self, username: str, password: str) -> str:
        """Launch slskd with the given Soulseek credentials.

        Returns the base URL of the running instance.
        """
        self.stop()
        binary = slskd_binary_path()
        if not os.path.isfile(binary):
            raise RuntimeError("slskd is not installed.")

        port = _free_port()
        downloads = slskd_downloads_dir()
        os.makedirs(downloads, exist_ok=True)

        # Credentials are passed via environment variables (not command-line)
        # so they don't appear in process listings.
        env = dict(os.environ)
        env.update({
            "SLSKD_SLSK_USERNAME": username or "",
            "SLSKD_SLSK_PASSWORD": password or "",
        })

        cmd = [
            binary,
            "--app-dir", slskd_dir(),
            "--no-https",
            "--no-auth",
            "--no-logo",
            "--no-version-check",
            "--http-port", str(port),
            "--http-ip-address", "127.0.0.1",
            "--downloads", downloads,
        ]

        kwargs = {}
        if sys.platform == "win32":
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            kwargs = {"startupinfo": si, "creationflags": subprocess.CREATE_NO_WINDOW}

        self._proc = subprocess.Popen(
            cmd,
            cwd=slskd_dir(),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            **kwargs,
        )
        self._port = port
        return self.base_url

    def stop(self):
        if self._proc is not None:
            try:
                self._proc.terminate()
                try:
                    self._proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._proc.kill()
            except Exception:
                pass
            self._proc = None
        self._port = None


class SlskdClient:
    """Thin HTTP client for the slskd REST API."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def _request(self, method: str, path: str, body: Optional[object] = None,
                 timeout: int = _TIMEOUT, quiet: bool = False) -> tuple[int, Optional[object]]:
        """Return (status_code, parsed_json_or_None)."""
        url = f"{self.base_url}{path}"
        data = None
        headers = {"Accept": "application/json"}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                status = resp.getcode()
                if not raw:
                    return status, None
                try:
                    return status, json.loads(raw)
                except Exception:
                    return status, None
        except urllib.error.HTTPError as e:
            return e.code, None
        except Exception as e:
            if not quiet:
                print(f"[soulseek] request failed ({method} {path}): {e}")
            return 0, None

    # ── Server / connection ─────────────────────────────────────────────
    def server_state(self, quiet: bool = False) -> Optional[Dict]:
        status, data = self._request("GET", "/api/v0/server", quiet=quiet)
        if status == 200:
            return data
        return None

    # ── Search ──────────────────────────────────────────────────────────
    def start_search(self, query: str, timeout: int = 15000, file_limit: int = 500) -> Optional[Dict]:
        """Start a search.

        *timeout* is the search duration in **milliseconds** (slskd API unit),
        and *file_limit* is the max number of files to collect.
        """
        body = {
            "searchText": query,
            "searchTimeout": timeout,
            "fileLimit": file_limit,
            "filterResponses": True,
        }
        status, data = self._request("POST", "/api/v0/searches", body)
        if status in (200, 201):
            return data
        return None

    def get_search(self, search_id: str) -> Optional[Dict]:
        path = f"/api/v0/searches/{urllib.parse.quote(search_id)}?includeResponses=true"
        status, data = self._request("GET", path)
        if status == 200:
            return data
        return None

    @staticmethod
    def is_search_complete(search: Dict) -> bool:
        state = search.get("state", "")
        return bool(state) and not state.startswith("InProgress")

    @staticmethod
    def flatten_files(search: Dict) -> List[Dict]:
        """Flatten a search's responses into a list of {file, username, token}."""
        out = []
        for resp in search.get("responses", []) or []:
            username = resp.get("username", "")
            token = resp.get("token", 0)
            upload_speed = resp.get("uploadSpeed", 0)
            queue_length = resp.get("queueLength", 0)
            for f in resp.get("files", []) or []:
                item = dict(f)
                item["_username"] = username
                item["_token"] = token
                item["_uploadSpeed"] = upload_speed
                item["_queueLength"] = queue_length
                out.append(item)
        return out

    # ── Downloads ───────────────────────────────────────────────────────
    def enqueue(self, username: str, files: List[Dict]) -> bool:
        """Enqueue downloads for *files* (each has 'filename' and 'size')."""
        path = f"/api/v0/transfers/downloads/{urllib.parse.quote(username)}"
        body = [{"filename": f.get("filename"), "size": int(f.get("size", 0))} for f in files]
        status, _ = self._request("POST", path, body)
        return status in (200, 201)

    def get_downloads(self, quiet: bool = False) -> List[Dict]:
        """Return a flat list of download transfer dicts."""
        status, data = self._request("GET", "/api/v0/transfers/downloads", quiet=quiet)
        if status != 200 or not isinstance(data, list):
            return []
        out = []
        for user in data:
            username = user.get("username", "")
            for directory in user.get("directories", []) or []:
                for f in directory.get("files", []) or []:
                    f["_username"] = username
                    out.append(f)
        return out

    def clear_completed_downloads(self) -> bool:
        status, _ = self._request("DELETE", "/api/v0/transfers/downloads/all/completed")
        return status in (200, 204)


# The server is a per-session singleton so the subprocess outlives UI rebuilds.
_server: Optional[SlskdServer] = None


def get_server() -> SlskdServer:
    global _server
    if _server is None:
        _server = SlskdServer()
    return _server
