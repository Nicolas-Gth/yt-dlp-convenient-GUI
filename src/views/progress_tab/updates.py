from io import BytesIO

from PySide6.QtWidgets import QLabel
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtCore import Qt

from utils import load_thumbnail
from utils.i18n_utils import t
from models import VideoInfo


class ProgressUpdatesMixin:
    """Mixin that updates progress information display."""

    def update_progress_info(self, video_info: VideoInfo, song_name: str, is_playlist: bool = False, playlist_title: str = ""):
        """Update progress display with video information."""
        if not hasattr(self, 'progress_frame') or self.progress_frame is None:
            return

        if is_playlist and hasattr(self, '_info_row_playlist') and self._info_row_playlist >= 0:
            self.info_table.item(self._info_row_playlist, 1).setText(playlist_title)
        self.info_table.item(self._info_row_title, 1).setText(video_info.title)
        self.info_table.item(self._info_row_author, 1).setText(video_info.uploader)
        self.info_table.item(self._info_row_duration, 1).setText(video_info.duration_formatted)

        # Update thumbnail
        if video_info.thumbnail:
            thumbnail = load_thumbnail(video_info.thumbnail, (100, 100), video_info.is_music)
            if thumbnail:
                buf = BytesIO()
                thumbnail.save(buf, format="PNG")
                buf.seek(0)
                qimg = QImage()
                qimg.loadFromData(buf.getvalue())
                pixmap = QPixmap.fromImage(qimg)
                self.thumbnail_label.setOriginalPixmap(pixmap)

    def update_video_progress(self, percentage: float, status: str = ""):
        """Update video download progress."""
        if not hasattr(self, 'video_progress') or self.video_progress is None:
            return
        if status == "processing":
            self.video_progress.setRange(0, 0)  # indeterminate animation
            self.video_progress.setFormat(t("progress.processing"))
        else:
            if self.video_progress.maximum() == 0:
                self.video_progress.setRange(0, 1000)
            self.video_progress.setValue(int(percentage * 10))
            self.video_progress.setFormat(f"{percentage:.1f}%")

    def update_total_progress(self, percentage: float, current: int = 0, total: int = 0):
        """Update total progress for playlists."""
        if not hasattr(self, 'total_progress') or self.total_progress is None:
            return
        self.total_progress.setValue(int(percentage * 10))
        if percentage >= 100:
            self.total_progress.setFormat(t("progress.done"))
        elif current > 0 and total > 0:
            self.total_progress.setFormat(t("progress.element_of", current=current, total=total))
        else:
            self.total_progress.setFormat(f"{percentage:.1f}%")
