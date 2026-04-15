"""
Desktop notification utilities for download completion.
"""
import os
import shutil
import subprocess
from typing import Optional, Dict

from config import ICON_PATH, APP_NAME
from models import DownloadProgress
from utils.i18n_utils import t


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
            key = "completion.element_playlist" if count == 1 else "completion.elements_playlist"
            message = t(key, count=count, playlist_title=playlist_title)
        else:
            message = t("completion.playlist_done", playlist_title=playlist_title)
    else:
        title = video_infos.get('title', 'Unknown')
        message = t("download.single", title=title)

    try:
        if shutil.which("notify-send"):
            cmd = [
                "notify-send",
                f"--app-name={APP_NAME}",
                "--expire-time=5000",
                t("completion.download_complete"),
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
