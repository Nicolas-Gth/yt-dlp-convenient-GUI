"""
Progress display mixin for the main application view.

Contains all progress-related UI: download progress bars, ETA,
thumbnails, normalize feedback, skipped entries, and fetching progress.
"""
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QFrame, QGroupBox, QSizePolicy, QSpacerItem,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QApplication, QMenu
)
from PySide6.QtGui import QFont, QPixmap, QImage, QIcon, QKeySequence, QPainter, QPainterPath
from PySide6.QtCore import Qt, QTimer, QByteArray, QBuffer, QSize

from config import DEFAULT_BITRATES, DEFAULT_QUALITIES, DOWNLOAD_ICON_PATH, REFRESH_ICON_PATH, STOP_ICON_PATH
from utils import load_thumbnail
from utils.i18n_utils import t
from models import VideoInfo

from io import BytesIO


class TextProgressBar(QProgressBar):
    """QProgressBar that displays format text even in indeterminate mode."""
    def text(self):
        if self.minimum() == 0 and self.maximum() == 0:
            return self.format()
        return super().text()


class CopyableTableWidget(QTableWidget):
    """QTableWidget that supports Ctrl+C to copy selected cells."""
    def keyPressEvent(self, event):
        if event.matches(QKeySequence.Copy):
            self._copy_selection()
        else:
            super().keyPressEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        copy_action = menu.addAction(t("table.copy"))
        copy_action.setEnabled(bool(self.selectedIndexes()))
        action = menu.exec(event.globalPos())
        if action == copy_action:
            self._copy_selection()

    def _copy_selection(self):
        selected = self.selectedIndexes()
        if not selected:
            return
        rows = sorted(set(idx.row() for idx in selected))
        cols = sorted(set(idx.column() for idx in selected))
        lines = []
        for r in rows:
            cells = []
            for c in cols:
                item = self.item(r, c)
                cells.append(item.text() if item else '')
            lines.append('\t'.join(cells))
        QApplication.clipboard().setText('\n'.join(lines))


def _round_pixmap(pixmap, radius=4):
    """Round the corners of a QPixmap."""
    rounded = QPixmap(pixmap.size())
    rounded.fill(Qt.transparent)
    painter = QPainter(rounded)
    painter.setRenderHint(QPainter.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(0, 0, pixmap.width(), pixmap.height(), radius, radius)
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, pixmap)
    painter.end()
    return rounded


class ScaledPixmapLabel(QLabel):
    """QLabel that scales its pixmap to fit, maintaining aspect ratio with rounded corners."""
    def __init__(self):
        super().__init__()
        self._original_pixmap = None
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    def setOriginalPixmap(self, pixmap):
        self._original_pixmap = pixmap
        self._update_scaled()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_scaled()

    def _update_scaled(self):
        if self._original_pixmap:
            target_height = self.height() if self.height() > 0 else self.minimumHeight()
            target_height = max(self.minimumHeight(), target_height)
            if self.maximumHeight() > 0:
                target_height = min(self.maximumHeight(), target_height)

            scaled = self._original_pixmap.scaledToHeight(target_height, Qt.SmoothTransformation)
            scaled = _round_pixmap(scaled)
            super().setPixmap(scaled)
            if self.width() != scaled.width():
                self.setFixedWidth(scaled.width())


class ProgressMixin:
    """Mixin that provides progress display methods for MainApplicationView."""

    # ------------------------------------------------------------------
    # Download progress widgets
    # ------------------------------------------------------------------

    def show_progress_widgets(self, is_playlist: bool = False):
        """Show download progress widgets."""
        self.disable_interactive_widgets()
        self.convert_button.hide()
        if hasattr(self, 'set_pre_button_spacer_collapsed'):
            self.set_pre_button_spacer_collapsed(True)

        row_h = self.fontMetrics().height() + 6

        # Create progress container as fieldset
        self.progress_frame = QGroupBox("")
        self.progress_frame.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        self.progress_frame.setAlignment(Qt.AlignLeft)
        self.progress_layout = QVBoxLayout(self.progress_frame)
        self.progress_layout.setContentsMargins(7, 5, 7, 5)

        # Thumbnail + info row
        thumb_info_layout = QHBoxLayout()
        thumb_info_layout.setSpacing(4)
        thumb_info_layout.setContentsMargins(0, 0, 0, 0)
        self.thumbnail_label = ScaledPixmapLabel()
        self.thumbnail_label.setFixedSize(60, 3 * row_h + 2)
        thumb_info_layout.addWidget(self.thumbnail_label, alignment=Qt.AlignLeft | Qt.AlignTop)

        self.info_table = QTableWidget(3, 2)
        self.info_table.horizontalHeader().setVisible(False)
        self.info_table.verticalHeader().setVisible(False)
        self.info_table.setShowGrid(False)
        self.info_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.info_table.setSelectionMode(QAbstractItemView.NoSelection)
        self.info_table.setFocusPolicy(Qt.NoFocus)
        self.info_table.setFrameShape(QFrame.NoFrame)
        self.info_table.setStyleSheet(
            "QTableWidget { border: none; background: transparent; padding: 0; margin: 0; }"
            "QTableWidget::item { padding: 0px; margin: 0px; }"
        )
        self.info_table.setContentsMargins(0, 0, 0, 0)
        self.info_table.setViewportMargins(0, 0, 0, 0)
        self.info_table.horizontalHeader().setMinimumSectionSize(0)
        self.info_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.info_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.info_table.verticalHeader().setDefaultSectionSize(row_h)
        for row, label in enumerate([t("progress.info.title"), t("progress.info.author"), t("progress.info.duration")]):
            item = QTableWidgetItem(label)
            f = item.font()
            f.setBold(True)
            item.setFont(f)
            item.setFlags(Qt.ItemIsEnabled)
            self.info_table.setItem(row, 0, item)
            val_item = QTableWidgetItem("")
            val_item.setFlags(Qt.ItemIsEnabled)
            self.info_table.setItem(row, 1, val_item)
        self.info_table.setFixedHeight(3 * row_h + 2)
        thumb_info_layout.addWidget(self.info_table, 1)
        self.progress_layout.addLayout(thumb_info_layout)

        # Element progress
        self.progress_label = QLabel(t("progress.element"))
        self.progress_layout.addWidget(self.progress_label)

        self.video_progress = TextProgressBar()
        self.video_progress.setRange(0, 1000)
        self.video_progress.setValue(0)
        self.video_progress.setTextVisible(True)
        self.video_progress.setFormat("0.0%")
        self.video_progress.setAlignment(Qt.AlignCenter)
        self.progress_layout.addWidget(self.video_progress)
        self.video_progress_percent = None

        # Total progress (for playlists)
        if is_playlist:
            self.total_progress_label = QLabel(t("progress.total"))
            self.progress_layout.addWidget(self.total_progress_label)

            self.total_progress = TextProgressBar()
            self.total_progress.setRange(0, 1000)
            self.total_progress.setValue(0)
            self.total_progress.setTextVisible(True)
            self.total_progress.setFormat("0.0%")
            self.total_progress.setAlignment(Qt.AlignCenter)
            self.progress_layout.addWidget(self.total_progress)
            self.total_progress_percent = None

            # ETA labels (elapsed left, remaining right)
            eta_layout = QHBoxLayout()
            self.eta_elapsed_label = QLabel("")
            self.eta_remaining_label = QLabel("")
            self.eta_remaining_label.setAlignment(Qt.AlignRight)
            eta_layout.addWidget(self.eta_elapsed_label)
            eta_layout.addWidget(self.eta_remaining_label)
            self.progress_layout.addLayout(eta_layout)
            self._eta_callback = None
            self._eta_timer = QTimer(self)
            self._eta_timer.timeout.connect(self._update_eta_timer)
            self._eta_timer.start(1000)

        progress_wrapper = QHBoxLayout()
        progress_wrapper.setContentsMargins(5, 0, 5, 0)
        progress_wrapper.addWidget(self.progress_frame)
        self.main_layout.insertLayout(self.main_layout.indexOf(self.convert_button), progress_wrapper)

        # Create stop button
        self.stop_button = QPushButton(" " + t("button.stop"))
        self.stop_button.setIcon(QIcon(STOP_ICON_PATH))
        self.stop_button.setIconSize(QSize(16, 16))
        self.stop_button.setCursor(Qt.PointingHandCursor)
        self.stop_button.setStyleSheet("""
            QPushButton {
                background-color: #a63333; color: white; border: none;
                border-radius: 4px; padding: 8px 16px;
            }
            QPushButton:hover { background-color: #c94444; }
        """)
        self.stop_button.clicked.connect(self._on_stop_click)
        stop_idx = self.main_layout.indexOf(self.convert_button)
        self._stop_btn_wrapper = QHBoxLayout()
        self._stop_btn_wrapper.setContentsMargins(0, 0, 0, 0)
        self._stop_btn_wrapper.addWidget(self.stop_button, alignment=Qt.AlignCenter)
        self.main_layout.insertLayout(stop_idx, self._stop_btn_wrapper)

    def hide_progress_widgets(self):
        """Hide progress widgets and restore convert button."""
        # Stop ETA timer
        self._stop_eta_timer()

        if hasattr(self, 'stop_button') and self.stop_button is not None:
            if hasattr(self, '_stop_btn_wrapper') and self._stop_btn_wrapper is not None:
                self.main_layout.removeItem(self._stop_btn_wrapper)
                self._stop_btn_wrapper = None
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
            self._normalize_table = None
            self._info_item_count = None

        self.convert_button.show()
        if hasattr(self, 'set_pre_button_spacer_collapsed'):
            self.set_pre_button_spacer_collapsed(False)
        self.set_convert_button_enabled(True)
        self.enable_interactive_widgets()

        # Restore input widgets
        if hasattr(self, 'input_container') and self.input_container is not None:
            self.input_container.show()

        self.adjust_window_size()

    # ------------------------------------------------------------------
    # Download-again button
    # ------------------------------------------------------------------

    def show_new_download_button(self):
        """Transform the stop button into a 'New download' button."""
        for attr in ('progress_label', 'video_progress', 'video_progress_percent',
                      'total_progress_label', 'total_progress', 'total_progress_percent',
                      'eta_elapsed_label', 'eta_remaining_label', 'thumbnail_label', 'info_table'):
            widget = getattr(self, attr, None)
            if widget is not None:
                widget.hide()

        # Hide input widgets so the summary aligns to the top
        if hasattr(self, 'input_container') and self.input_container is not None:
            self.input_container.hide()

        if hasattr(self, 'stop_button') and self.stop_button is not None:
            self.stop_button.setEnabled(True)
            self.stop_button.setText(" " + t("button.new_download"))
            self.stop_button.setIcon(QIcon(REFRESH_ICON_PATH))
            self.stop_button.setIconSize(QSize(18, 18))
            self.stop_button.setStyleSheet("""
                QPushButton {
                    background-color: #238a45; color: white; border: none;
                    border-radius: 4px; padding: 8px 16px;
                }
                QPushButton:hover { background-color: #449468; }
            """)
            self.stop_button.clicked.disconnect()
            self.stop_button.clicked.connect(self._on_download_again_click)

    # ------------------------------------------------------------------
    # ETA management
    # ------------------------------------------------------------------

    def set_eta_callback(self, callback):
        """Set the callback used to compute the ETA string."""
        self._eta_callback = callback

    def _update_eta_timer(self):
        """Refresh the ETA labels every second."""
        if hasattr(self, 'eta_elapsed_label') and self.eta_elapsed_label is not None:
            if callable(getattr(self, '_eta_callback', None)):
                result = self._eta_callback()
                if isinstance(result, tuple):
                    self.eta_elapsed_label.setText(result[0])
                    self.eta_remaining_label.setText(result[1])
                else:
                    self.eta_elapsed_label.setText(result)
                    self.eta_remaining_label.setText("")

    def _stop_eta_timer(self):
        """Stop the ETA refresh timer."""
        if hasattr(self, '_eta_timer') and self._eta_timer is not None:
            self._eta_timer.stop()

    def update_eta(self, eta_text: str):
        """Update the estimated remaining time labels."""
        if hasattr(self, 'eta_elapsed_label') and self.eta_elapsed_label is not None:
            if isinstance(eta_text, tuple):
                self.eta_elapsed_label.setText(eta_text[0])
                self.eta_remaining_label.setText(eta_text[1])
            else:
                self.eta_elapsed_label.setText(eta_text)
                self.eta_remaining_label.setText("")

    # ------------------------------------------------------------------
    # Progress updates
    # ------------------------------------------------------------------

    def update_progress_info(self, video_info: VideoInfo, song_name: str, is_playlist: bool = False):
        """Update progress display with video information."""
        if not hasattr(self, 'progress_frame') or self.progress_frame is None:
            return

        self.progress_frame.setTitle(song_name)

        self.info_table.item(0, 1).setText(video_info.title)
        self.info_table.item(1, 1).setText(video_info.uploader)
        self.info_table.item(2, 1).setText(video_info.duration_formatted)

        # Update thumbnail
        if video_info.thumbnail:
            thumbnail = load_thumbnail(video_info.thumbnail, (100, 100), video_info.is_music)
            if thumbnail:
                # Convert PIL Image to QPixmap
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

    def update_total_progress(self, percentage: float):
        """Update total progress for playlists."""
        if not hasattr(self, 'total_progress') or self.total_progress is None:
            return
        self.total_progress.setValue(int(percentage * 10))
        if percentage >= 100:
            self.total_progress.setFormat(t("progress.done"))
        else:
            self.total_progress.setFormat(f"{percentage:.1f}%")

    # ------------------------------------------------------------------
    # Skipped entries panel
    # ------------------------------------------------------------------

    def add_skipped_entry(self, entry: dict, reason: str):
        """Add one unavailable entry to the skipped entries table."""
        if not hasattr(self, 'progress_frame') or self.progress_frame is None:
            return

        MAX_VISIBLE = 5
        ROW_HEIGHT = 24

        # Lazy-create the group box and table
        if not hasattr(self, '_skipped_group') or self._skipped_group is None:
            self._skipped_group = QGroupBox()
            self._skipped_group.setFlat(True)
            group_layout = QVBoxLayout(self._skipped_group)
            group_layout.setContentsMargins(0, 4, 0, 0)
            group_layout.setSpacing(4)

            self._skipped_header_label = QLabel()
            self._skipped_header_label.setFont(QFont("", -1, QFont.Bold))
            group_layout.addWidget(self._skipped_header_label)

            self._skipped_table = CopyableTableWidget()
            self._skipped_table.setColumnCount(4)
            self._skipped_table.setHorizontalHeaderLabels([
                "#",
                t("progress.table.artist"),
                t("progress.table.title"),
                t("progress.table.reason"),
            ])
            self._skipped_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
            self._skipped_table.setSelectionBehavior(QAbstractItemView.SelectRows)
            self._skipped_table.verticalHeader().setVisible(False)
            self._skipped_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
            self._skipped_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
            self._skipped_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
            self._skipped_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
            self._skipped_table.setAlternatingRowColors(True)
            self._skipped_table.setFixedHeight(ROW_HEIGHT * MAX_VISIBLE + self._skipped_table.horizontalHeader().height())

            group_layout.addWidget(self._skipped_table)
            self.progress_layout.addWidget(self._skipped_group)
            self._skipped_count = 0

        # Add row
        self._skipped_count += 1
        row = self._skipped_table.rowCount()
        self._skipped_table.insertRow(row)
        self._skipped_table.setRowHeight(row, ROW_HEIGHT)

        num_item = QTableWidgetItem(str(self._skipped_count))
        num_item.setTextAlignment(Qt.AlignCenter)
        self._skipped_table.setItem(row, 0, num_item)
        self._skipped_table.setItem(row, 1, QTableWidgetItem(entry.get('channel', '') or ''))
        self._skipped_table.setItem(row, 2, QTableWidgetItem(entry.get('title', '') or ''))
        self._skipped_table.setItem(row, 3, QTableWidgetItem(reason))

        # Update table height if below max visible
        actual_rows = self._skipped_table.rowCount()
        if actual_rows <= MAX_VISIBLE:
            self._skipped_table.setFixedHeight(
                ROW_HEIGHT * actual_rows + self._skipped_table.horizontalHeader().height()
            )

        # Update header label
        self._skipped_header_label.setText(
            t("progress.skipped_header") + f" ({self._skipped_count})"
        )

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

        artist = info.get('artist', '')
        title = info.get('title', info.get('display_name', 'Unknown'))
        metadata = t("table.yes") if info.get('metadata_found') else t("table.none")
        lyrics_type = info.get('lyrics_type', 'No')
        if lyrics_type == 'No':
            lyrics_type = t("table.none")

        volume = info.get('volume')
        if volume:
            diff = volume['measured'] - volume['target']
            norm_str = f"{-diff:+.1f} dB" if diff > 0 else f"{abs(diff):+.1f} dB"
        else:
            norm_str = t("table.none")

        MAX_VISIBLE = 8
        ROW_HEIGHT = 24

        if not hasattr(self, '_normalize_labels') or self._normalize_labels is None:
            self._normalize_labels = []

            self.normalize_outer_frame = QGroupBox(t("progress.downloaded_elements"))
            self.normalize_outer_frame.setFont(QFont("Arial", 9, QFont.Bold))
            norm_layout = QVBoxLayout(self.normalize_outer_frame)
            norm_layout.setContentsMargins(5, 10, 5, 8)

            self._normalize_table = CopyableTableWidget(0, 6)
            self._normalize_table.setHorizontalHeaderLabels(
                [t("progress.table.number"), t("progress.table.artist"), t("progress.table.title"),
                 t("progress.table.metadatas"), t("progress.table.lyrics"), t("progress.table.norm")]
            )
            self._normalize_table.setFont(QFont("Arial", 8))
            self._normalize_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
            self._normalize_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
            self._normalize_table.verticalHeader().setVisible(False)
            self._normalize_table.setShowGrid(False)
            self._normalize_table.setStyleSheet(
                "QTableWidget { border: none; background: transparent; }"
                "QTableWidget QTableCornerButton::section { background: transparent; }"
                "QHeaderView { background: transparent; }"
                "QHeaderView::section { border: none; border-bottom: 1px solid palette(mid); background: transparent; }"
            )

            header = self._normalize_table.horizontalHeader()
            header.setFont(QFont("Arial", 8, QFont.Bold))
            header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # #
            header.setSectionResizeMode(1, QHeaderView.Stretch)          # Artist
            header.setSectionResizeMode(2, QHeaderView.Stretch)          # Title
            header.setSectionResizeMode(3, QHeaderView.Stretch)          # Metadatas
            header.setSectionResizeMode(4, QHeaderView.Stretch)          # Lyrics
            header.setSectionResizeMode(5, QHeaderView.Stretch)          # Norm.
            header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)

            norm_layout.addWidget(self._normalize_table, 1)
            self.progress_layout.addSpacing(10)
            self.progress_layout.addWidget(self.normalize_outer_frame)

            # Let the table area stretch immediately
            idx = self.progress_layout.indexOf(self.normalize_outer_frame)
            if idx >= 0:
                self.progress_layout.setStretch(idx, 1)
            self.progress_frame.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        # Add a row
        row = self._normalize_table.rowCount()
        self._normalize_table.insertRow(row)
        self._normalize_table.setRowHeight(row, ROW_HEIGHT)
        for col, text in enumerate([str(num), artist, title, metadata, lyrics_type, norm_str]):
            item = QTableWidgetItem(text)
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self._normalize_table.setItem(row, col, item)
        self._normalize_labels.append(num)

        count = len(self._normalize_labels)
        key = "progress.downloaded_element" if count == 1 else "progress.downloaded_elements"
        self.normalize_outer_frame.setTitle(f"{t(key)} ({count})")

        header_h = self._normalize_table.horizontalHeader().height()
        if count <= MAX_VISIBLE:
            self._normalize_table.setMinimumHeight(header_h + count * ROW_HEIGHT + 2)
        else:
            self._normalize_table.setMinimumHeight(header_h + MAX_VISIBLE * ROW_HEIGHT + 2)

        self._normalize_table.scrollToBottom()

    # ------------------------------------------------------------------
    # Fetching progress (pre-download info retrieval)
    # ------------------------------------------------------------------

    def show_fetching_progress(self, is_playlist: bool = False):
        """Show fetching progress bar."""
        self.disable_interactive_widgets()
        self.convert_button.hide()
        if hasattr(self, 'set_pre_button_spacer_collapsed'):
            self.set_pre_button_spacer_collapsed(True)

        self.fetching_frame = QFrame()
        fetching_layout = QVBoxLayout(self.fetching_frame)
        fetching_layout.setAlignment(Qt.AlignCenter)

        self.fetching_label = QLabel(
            t("fetching.info") if not is_playlist else t("fetching.playlist")
        )
        self.fetching_label.setAlignment(Qt.AlignCenter)
        fetching_layout.addWidget(self.fetching_label)

        self.fetching_progress = QProgressBar()
        if is_playlist:
            self.fetching_progress.setRange(0, 100)
            self.fetching_progress.setValue(0)
        else:
            self.fetching_progress.setRange(0, 0)  # indeterminate
        fetching_layout.addWidget(self.fetching_progress)

        self.main_layout.insertWidget(self.main_layout.indexOf(self.convert_button), self.fetching_frame)

    def update_fetching_progress(self, current: int, total: int = None):
        """Update the fetching progress bar and label."""
        if not hasattr(self, 'fetching_label') or not hasattr(self, 'fetching_progress'):
            return

        if total and total > 0:
            percentage = (current / total) * 100
            self.fetching_progress.setValue(int(percentage))
            self.fetching_label.setText(
                t("fetching.playlist_progress", current=current, total=total)
            )
        else:
            self.fetching_label.setText(
                t("fetching.playlist_count", current=current)
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
        if hasattr(self, 'set_pre_button_spacer_collapsed'):
            self.set_pre_button_spacer_collapsed(False)
        self.set_convert_button_enabled(True)
