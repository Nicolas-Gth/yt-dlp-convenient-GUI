"""
Progress display mixin for the main application view.

Contains all progress-related UI: download progress bars, ETA,
thumbnails, normalize feedback, skipped entries, and fetching progress.
"""
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QTextEdit, QFrame, QSizePolicy
)
from PySide6.QtGui import QFont, QPixmap, QImage
from PySide6.QtCore import Qt, QTimer, QByteArray, QBuffer

from utils import load_thumbnail
from models import VideoInfo

from io import BytesIO


class ProgressMixin:
    """Mixin that provides progress display methods for MainApplicationView."""

    # ------------------------------------------------------------------
    # Download progress widgets
    # ------------------------------------------------------------------

    def show_progress_widgets(self, is_playlist: bool = False):
        """Show download progress widgets."""
        self.disable_interactive_widgets()
        self.convert_button.hide()

        # Create progress container
        self.progress_frame = QFrame()
        self.progress_layout = QVBoxLayout(self.progress_frame)
        self.progress_layout.setContentsMargins(7, 10, 7, 0)

        # Song name label
        self.song_label = QLabel("")
        self.song_label.setFont(QFont("Arial", 9, QFont.Bold))
        self.song_label.setWordWrap(True)
        self.progress_layout.addWidget(self.song_label)

        # Thumbnail + info row
        thumb_info_layout = QHBoxLayout()
        self.thumbnail_label = QLabel()
        self.thumbnail_label.setFixedSize(100, 60)
        thumb_info_layout.addWidget(self.thumbnail_label, alignment=Qt.AlignLeft | Qt.AlignTop)

        self.info_label = QLabel("")
        self.info_label.setWordWrap(True)
        thumb_info_layout.addWidget(self.info_label, 1)
        self.progress_layout.addLayout(thumb_info_layout)

        # Element progress
        elem_layout = QHBoxLayout()
        self.progress_label = QLabel("Element progress :")
        elem_layout.addWidget(self.progress_label)

        self.video_progress = QProgressBar()
        self.video_progress.setRange(0, 1000)
        self.video_progress.setValue(0)
        self.video_progress.setFixedWidth(300)
        self.video_progress.setTextVisible(False)
        elem_layout.addWidget(self.video_progress)

        self.video_progress_percent = QLabel(" 0.0%")
        self.video_progress_percent.setFixedWidth(80)
        elem_layout.addWidget(self.video_progress_percent)
        elem_layout.addStretch()
        self.progress_layout.addLayout(elem_layout)

        # Total progress (for playlists)
        if is_playlist:
            total_layout = QHBoxLayout()
            self.total_progress_label = QLabel("Total progress :")
            total_layout.addWidget(self.total_progress_label)

            self.total_progress = QProgressBar()
            self.total_progress.setRange(0, 1000)
            self.total_progress.setValue(0)
            self.total_progress.setFixedWidth(300)
            self.total_progress.setTextVisible(False)
            total_layout.addWidget(self.total_progress)

            self.total_progress_percent = QLabel(" 0.0%")
            self.total_progress_percent.setFixedWidth(80)
            total_layout.addWidget(self.total_progress_percent)
            total_layout.addStretch()
            self.progress_layout.addLayout(total_layout)

            # ETA label
            self.eta_label = QLabel("")
            self.progress_layout.addWidget(self.eta_label)
            self._eta_callback = None
            self._eta_timer = QTimer(self)
            self._eta_timer.timeout.connect(self._update_eta_timer)
            self._eta_timer.start(1000)

        self.main_layout.insertWidget(self.main_layout.indexOf(self.convert_button), self.progress_frame)

        # Create stop button
        self.stop_button = QPushButton("Stop download")
        self.stop_button.setFont(QFont("Bahnschrift", 12))
        self.stop_button.setCursor(Qt.PointingHandCursor)
        self.stop_button.setStyleSheet("""
            QPushButton {
                background-color: #a63333; color: white; border: none;
                border-radius: 4px; padding: 8px 16px;
            }
            QPushButton:hover { background-color: #c94444; }
        """)
        self.stop_button.clicked.connect(self._on_stop_click)
        self.main_layout.insertWidget(self.main_layout.indexOf(self.convert_button), self.stop_button, alignment=Qt.AlignCenter)

        self.adjust_window_size()

    def hide_progress_widgets(self):
        """Hide progress widgets and restore convert button."""
        # Stop ETA timer
        self._stop_eta_timer()

        if hasattr(self, 'stop_button') and self.stop_button is not None:
            self.stop_button.hide()
            self.stop_button.deleteLater()
            self.stop_button = None

        if hasattr(self, '_skipped_frame') and self._skipped_frame is not None:
            self._skipped_frame.hide()
            self._skipped_frame.deleteLater()
            self._skipped_frame = None

        if hasattr(self, 'progress_frame') and self.progress_frame is not None:
            self.progress_frame.hide()
            self.progress_frame.deleteLater()
            self.progress_frame = None

        if hasattr(self, 'normalize_outer_frame') and self.normalize_outer_frame is not None:
            self.normalize_outer_frame.hide()
            self.normalize_outer_frame.deleteLater()
            self.normalize_outer_frame = None
            self._normalize_labels = None
            self._info_item_count = None

        self.convert_button.show()
        self.set_convert_button_enabled(True)
        self.enable_interactive_widgets()
        self.adjust_window_size()

    # ------------------------------------------------------------------
    # Download-again button
    # ------------------------------------------------------------------

    def show_new_download_button(self):
        """Transform the stop button into a 'New download' button."""
        for attr in ('progress_label', 'video_progress', 'video_progress_percent',
                      'total_progress_label', 'total_progress', 'total_progress_percent',
                      'eta_label', 'thumbnail_label', 'info_label'):
            widget = getattr(self, attr, None)
            if widget is not None:
                widget.hide()

        if hasattr(self, 'stop_button') and self.stop_button is not None:
            self.stop_button.setEnabled(True)
            self.stop_button.setText("New download")
            self.stop_button.setStyleSheet("""
                QPushButton {
                    background-color: #238a45; color: white; border: none;
                    border-radius: 4px; padding: 8px 16px;
                }
                QPushButton:hover { background-color: #449468; }
            """)
            self.stop_button.clicked.disconnect()
            self.stop_button.clicked.connect(self._on_download_again_click)

        self.adjust_window_size()

    # ------------------------------------------------------------------
    # ETA management
    # ------------------------------------------------------------------

    def set_eta_callback(self, callback):
        """Set the callback used to compute the ETA string."""
        self._eta_callback = callback

    def _update_eta_timer(self):
        """Refresh the ETA label every second."""
        if hasattr(self, 'eta_label') and self.eta_label is not None:
            if callable(getattr(self, '_eta_callback', None)):
                eta_text = self._eta_callback()
                self.eta_label.setText(eta_text)

    def _stop_eta_timer(self):
        """Stop the ETA refresh timer."""
        if hasattr(self, '_eta_timer') and self._eta_timer is not None:
            self._eta_timer.stop()

    def update_eta(self, eta_text: str):
        """Update the estimated remaining time label."""
        if hasattr(self, 'eta_label') and self.eta_label is not None:
            self.eta_label.setText(eta_text)

    # ------------------------------------------------------------------
    # Progress updates
    # ------------------------------------------------------------------

    def update_progress_info(self, video_info: VideoInfo, song_name: str, is_playlist: bool = False):
        """Update progress display with video information."""
        if not hasattr(self, 'progress_frame') or self.progress_frame is None:
            return

        self.song_label.setText(song_name)

        info_text = (
            f"Title : \"{video_info.title}\"\n"
            f"Channel : \"{video_info.uploader}\"\n"
            f"Duration : {video_info.duration_formatted}"
        )
        self.info_label.setText(info_text)

        # Update thumbnail
        if video_info.thumbnail:
            thumbnail = load_thumbnail(video_info.thumbnail, (100, 60), video_info.is_music)
            if thumbnail:
                # Convert PIL Image to QPixmap
                buf = BytesIO()
                thumbnail.save(buf, format="PNG")
                buf.seek(0)
                qimg = QImage()
                qimg.loadFromData(buf.getvalue())
                pixmap = QPixmap.fromImage(qimg)
                self.thumbnail_label.setPixmap(pixmap)

                # Adjust thumbnail label size for square images
                is_square = abs(thumbnail.size[0] - thumbnail.size[1]) < 5
                if is_square:
                    self.thumbnail_label.setFixedSize(60, 60)
                else:
                    self.thumbnail_label.setFixedSize(100, 60)

        self.adjust_window_size()

    def update_video_progress(self, percentage: float, status: str = ""):
        """Update video download progress."""
        if not hasattr(self, 'video_progress') or self.video_progress is None:
            return
        if status == "processing":
            self.video_progress.setRange(0, 0)  # indeterminate
            self.video_progress_percent.setText("Processing")
        else:
            if self.video_progress.maximum() == 0:
                self.video_progress.setRange(0, 1000)
            self.video_progress.setValue(int(percentage * 10))
            self.video_progress_percent.setText(f" {percentage:.1f}%")

    def update_total_progress(self, percentage: float):
        """Update total progress for playlists."""
        if not hasattr(self, 'total_progress') or self.total_progress is None:
            return
        self.total_progress.setValue(int(percentage * 10))
        if percentage >= 100:
            self.total_progress_percent.setText("Done")
        else:
            self.total_progress_percent.setText(f" {percentage:.1f}%")

    # ------------------------------------------------------------------
    # Skipped entries panel
    # ------------------------------------------------------------------

    def show_skipped_entries(self, hidden_entries: list):
        """Show a panel listing entries that were skipped."""
        if not hasattr(self, 'progress_frame') or self.progress_frame is None or not hidden_entries:
            return

        self._skipped_frame = QFrame()
        skipped_layout = QVBoxLayout(self._skipped_frame)
        skipped_layout.setContentsMargins(5, 2, 5, 2)

        header = QLabel("Skipped unavailable elements")
        header.setFont(QFont("Arial", 9, QFont.Bold))
        skipped_layout.addWidget(header)

        # Build text content
        lines = []
        for i, entry in enumerate(hidden_entries, start=1):
            title = entry.get('title', 'Unknown')
            channel = entry.get('channel', '')
            if entry.get('age_restricted'):
                suffix = '  [Age-restricted]'
            elif entry.get('format_unavailable'):
                suffix = '  [Format unavailable]'
            elif entry.get('video_unavailable'):
                suffix = '  [Unavailable]'
            else:
                suffix = ''
            if channel:
                lines.append(f"{i}. {channel} - {title}{suffix}")
            else:
                lines.append(f"{i}. {title}{suffix}")

        self._skipped_text = QTextEdit()
        self._skipped_text.setReadOnly(True)
        self._skipped_text.setFont(QFont("Arial", 8))
        self._skipped_text.setPlainText("\n".join(lines))
        self._skipped_text.setFixedHeight(min(len(lines) * 18 + 10, 120))
        self._skipped_text.setStyleSheet("border: none;")
        skipped_layout.addWidget(self._skipped_text)

        self.progress_layout.addWidget(self._skipped_frame)
        self.adjust_window_size()

    def show_age_restricted_entries(self, entries: list):
        """Show age-restricted entries in the skipped panel."""
        self._show_skipped_error_entries(entries, 'age_restricted', 'Age-restricted')

    def show_format_unavailable_entries(self, entries: list):
        """Show format-unavailable entries in the skipped panel."""
        self._show_skipped_error_entries(entries, 'format_unavailable', 'Format unavailable')

    def show_video_unavailable_entries(self, entries: list):
        """Show video-unavailable entries in the skipped panel."""
        self._show_skipped_error_entries(entries, 'video_unavailable', 'Unavailable')

    def _show_skipped_error_entries(self, entries: list, flag_key: str, label: str):
        """Show error entries in the skipped panel."""
        if not entries:
            return
        formatted = []
        for entry in entries:
            title = entry.get('title', 'Unknown')
            channel = entry.get('channel', '')
            formatted.append({'title': title, 'channel': channel or '', flag_key: True})

        if hasattr(self, '_skipped_frame') and self._skipped_frame is not None and hasattr(self, '_skipped_text'):
            # Append to existing
            current = self._skipped_text.toPlainText()
            current_lines = current.count('\n') + 1
            new_lines = []
            for entry in formatted:
                title = entry['title']
                channel = entry['channel']
                if channel:
                    line = f"{current_lines}. {channel} - {title}  [{label}]"
                else:
                    line = f"{current_lines}. {title}  [{label}]"
                new_lines.append(line)
                current_lines += 1
            self._skipped_text.setPlainText(current + "\n" + "\n".join(new_lines))
            total_lines = self._skipped_text.toPlainText().count('\n') + 1
            self._skipped_text.setFixedHeight(min(total_lines * 18 + 10, 120))
            self.adjust_window_size()
        else:
            self.show_skipped_entries(formatted)

    # ------------------------------------------------------------------
    # Normalize feedback (per-track summary)
    # ------------------------------------------------------------------

    def show_normalize_feedback(self, info: dict):
        """Show per-track summary feedback below the progress widgets."""
        if not hasattr(self, 'progress_frame') or self.progress_frame is None:
            return

        if not hasattr(self, '_info_item_count') or self._info_item_count is None:
            self._info_item_count = 0
        self._info_item_count += 1
        num = self._info_item_count

        display_name = info.get('display_name', info.get('title', 'Unknown'))

        parts = []
        if info.get('metadata_found'):
            parts.append("Metadatas")
        elif info.get('type') == 'track_summary':
            parts.append("No metadatas")
        if info.get('lyrics_found'):
            parts.append("Lyrics")
        elif info.get('type') == 'track_summary':
            parts.append("No lyrics")
        volume = info.get('volume')
        if volume:
            measured = volume['measured']
            target = volume['target']
            diff = measured - target
            if diff > 0:
                parts.append(f"-{abs(diff):.1f} dB")
            else:
                parts.append(f"+{abs(diff):.1f} dB")

        separator = "  |  "
        feedback = f"{num}. {display_name}{separator}{separator.join(parts)}" if parts else f"{num}. {display_name}"

        MAX_VISIBLE = 5
        ITEM_HEIGHT = 18

        if not hasattr(self, '_normalize_labels') or self._normalize_labels is None:
            self._normalize_labels = []

            self.normalize_outer_frame = QFrame()
            norm_layout = QVBoxLayout(self.normalize_outer_frame)
            norm_layout.setContentsMargins(5, 2, 5, 8)

            header_lbl = QLabel("Downloaded elements")
            header_lbl.setFont(QFont("Arial", 9, QFont.Bold))
            norm_layout.addWidget(header_lbl)

            line = QFrame()
            line.setFrameShape(QFrame.HLine)
            norm_layout.addWidget(line)

            self._normalize_text = QTextEdit()
            self._normalize_text.setReadOnly(True)
            self._normalize_text.setFont(QFont("Arial", 8))
            self._normalize_text.setStyleSheet("border: none;")
            self._normalize_text.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            norm_layout.addWidget(self._normalize_text)

            self.progress_layout.addWidget(self.normalize_outer_frame)

        # Append the new line
        if self._normalize_labels:
            current = self._normalize_text.toPlainText()
            self._normalize_text.setPlainText(current + "\n" + feedback)
        else:
            self._normalize_text.setPlainText(feedback)
        self._normalize_labels.append(feedback)

        count = len(self._normalize_labels)
        if count <= MAX_VISIBLE:
            self._normalize_text.setFixedHeight(count * ITEM_HEIGHT + 10)
        else:
            self._normalize_text.setFixedHeight(MAX_VISIBLE * ITEM_HEIGHT + 10)

        # Scroll to bottom
        scrollbar = self._normalize_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

        if count <= MAX_VISIBLE:
            self.adjust_window_size()

    # ------------------------------------------------------------------
    # Fetching progress (pre-download info retrieval)
    # ------------------------------------------------------------------

    def show_fetching_progress(self, is_playlist: bool = False):
        """Show fetching progress bar."""
        self.disable_interactive_widgets()
        self.convert_button.hide()

        self.fetching_frame = QFrame()
        fetching_layout = QVBoxLayout(self.fetching_frame)
        fetching_layout.setAlignment(Qt.AlignCenter)

        self.fetching_label = QLabel(
            "Retrieving information..." if not is_playlist else "Retrieving playlist information..."
        )
        self.fetching_label.setAlignment(Qt.AlignCenter)
        fetching_layout.addWidget(self.fetching_label)

        self.fetching_progress = QProgressBar()
        self.fetching_progress.setFixedWidth(300)
        if is_playlist:
            self.fetching_progress.setRange(0, 100)
            self.fetching_progress.setValue(0)
        else:
            self.fetching_progress.setRange(0, 0)  # indeterminate
        fetching_layout.addWidget(self.fetching_progress, alignment=Qt.AlignCenter)

        self.main_layout.insertWidget(self.main_layout.indexOf(self.convert_button), self.fetching_frame)
        self.adjust_window_size()

    def update_fetching_progress(self, current: int, total: int = None):
        """Update the fetching progress bar and label."""
        if not hasattr(self, 'fetching_label') or not hasattr(self, 'fetching_progress'):
            return

        if total and total > 0:
            percentage = (current / total) * 100
            self.fetching_progress.setValue(int(percentage))
            self.fetching_label.setText(
                f"Retrieving playlist information... ({current}/{total})"
            )
        else:
            self.fetching_label.setText(
                f"Retrieving playlist information... ({current} titles found)"
            )
            self.fetching_progress.setValue(min(current % 100, 95))

    def hide_fetching_progress(self):
        """Hide fetching progress widgets and restore convert button."""
        if hasattr(self, 'fetching_frame') and self.fetching_frame is not None:
            self.fetching_frame.hide()
            self.fetching_frame.deleteLater()
            self.fetching_frame = None

        self.enable_interactive_widgets()
        self.convert_button.show()
        self.set_convert_button_enabled(True)
