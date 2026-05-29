import os
import re
from datetime import datetime

from PySide6.QtCore import QThread, Signal

from .metadata import _extract_scan_metadata

# yt-dlp temporary file patterns
_TEMP_RE = re.compile(r'\.f\d+\.[a-zA-Z0-9]+$')


def _is_temp_file(filepath):
    """Return True if *filepath* is a yt-dlp temporary/in-progress file."""
    fname = os.path.basename(filepath)
    # .part and .ytdl files
    if fname.endswith('.part') or fname.endswith('.ytdl'):
        return True
    # Fragment files:  title.f399.mp4
    if _TEMP_RE.search(fname):
        return True
    # Empty files (download not started or just finished)
    try:
        if os.path.getsize(filepath) == 0:
            return True
    except OSError:
        return True
    return False


class FileScanner(QThread):
    """Background thread that scans a directory for audio/video files and reads metadata."""

    results_ready = Signal(list, str)  # list of tuples, directory

    def __init__(self, directory, parent=None):
        super().__init__(parent)
        self.directory = directory

    def run(self):
        directory = self.directory
        extensions = ('.mp3', '.mp4', '.opus')
        results = []

        for root, _dirs, filenames in os.walk(directory):
            for fname in filenames:
                if self.isInterruptionRequested():
                    return
                if os.path.splitext(fname)[1].lower() in extensions:
                    full = os.path.join(root, fname)
                    if _is_temp_file(full):
                        continue
                    rel = os.path.relpath(full, directory)
                    artist, title, album, genre, year, tracknumber, lyrics, lyr_type = _extract_scan_metadata(full)
                    try:
                        mtime = datetime.fromtimestamp(os.path.getmtime(full)).strftime("%d/%m/%Y %H:%M")
                        size = os.path.getsize(full)
                    except (OSError, FileNotFoundError):
                        continue
                    results.append((full, rel, artist, title, album, genre, year, tracknumber, lyrics, lyr_type, size, mtime))

        if not self.isInterruptionRequested():
            results.sort(key=lambda x: x[1].lower())
            self.results_ready.emit(results, directory)
