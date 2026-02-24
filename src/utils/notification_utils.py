"""
Desktop notification utilities for download completion.
"""
import os
import shutil
import subprocess
from typing import Optional, Dict

from config import ICON_PATH, APP_NAME
from models import DownloadProgress


def send_completion_notification(
    config,
    video_infos: Optional[Dict],
    progress: Optional[DownloadProgress],
):
    """Send a desktop notification when a download completes."""
    if not video_infos:
        return

    if config.is_playlist:
        playlist_title = video_infos.get('title', 'Unknown Playlist')
        count = progress.current_song if progress else 0
        if count > 0:
            message = f"{count} element{'s' if count > 1 else ''} downloaded from playlist {playlist_title}."
        else:
            message = f"Playlist {playlist_title} downloaded."
    else:
        title = video_infos.get('title', 'Unknown')
        message = f"Video \"{title}\" has been downloaded."

    try:
        if shutil.which("notify-send"):
            cmd = [
                "notify-send",
                f"--app-name={APP_NAME}",
                "--expire-time=5000",
                "Download Complete!",
                message,
            ]
            # Add icon if available
            if ICON_PATH and os.path.isfile(ICON_PATH):
                cmd.insert(1, f"--icon={ICON_PATH}")
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            print(f"Download Complete! {message}")
    except Exception:
        print(f"Download Complete! {message}")
