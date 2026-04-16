import os
import subprocess

_DIR = os.path.dirname(os.path.abspath(__file__))

# In a git checkout, this stays as a literal dollar-sign string.
# In a GitHub ZIP download, git expands it to the describe output (e.g. "v3.0-5-gabcdef").
_GIT_ARCHIVE_DESCRIBE = "$Format:%(describe:tags=true,match=v*)$"


def _parse_describe(desc):
    """Parse a git describe output (e.g. 'v3.0-4-gabcdef') into a version string."""
    parts = desc.lstrip("v").split("-")
    base = parts[0]
    patch = parts[1] if len(parts) >= 2 else "0"
    return f"{base}.{patch}"


def get_version():
    """Get app version from git describe, or from the archive-expanded placeholder."""
    # 1. Try live git describe (normal dev environment)
    try:
        desc = subprocess.check_output(
            ["git", "describe", "--tags", "--match", "v*"],
            stderr=subprocess.DEVNULL,
            cwd=_DIR,
            text=True,
        ).strip()
        return _parse_describe(desc)
    except Exception:
        pass

    # 2. Try the export-subst placeholder (GitHub ZIP download)
    if not _GIT_ARCHIVE_DESCRIBE.startswith("$"):
        return _parse_describe(_GIT_ARCHIVE_DESCRIBE)

    return "unknown"
