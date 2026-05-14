import os
from datetime import datetime

from PySide6.QtCore import QThread, Signal

from .metadata import _extract_title_artist, _check_lyrics


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
                if os.path.splitext(fname)[1].lower() in extensions:
                    full = os.path.join(root, fname)
                    rel = os.path.relpath(full, directory)
                    artist, title = _extract_title_artist(full)
                    lyrics, lyr_type = _check_lyrics(full)
                    mtime = datetime.fromtimestamp(os.path.getmtime(full)).strftime("%d/%m/%Y %H:%M")
                    results.append((full, rel, artist, title, lyrics, lyr_type, mtime))

        results.sort(key=lambda x: x[1].lower())
        self.results_ready.emit(results, directory)
