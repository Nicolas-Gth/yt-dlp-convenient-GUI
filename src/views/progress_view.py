"""
Progress display mixin for the main application view.

Contains all progress-related UI: download progress bars, ETA,
thumbnails, normalize feedback, skipped entries, and fetching progress.
"""
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QFrame, QGroupBox, QSizePolicy, QSpacerItem,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QApplication, QMenu, QSplitter, QWidget
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
    # Layout helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _clear_layout(layout):
        """Remove and delete all items from a layout."""
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()
            else:
                child_layout = item.layout()
                if child_layout is not None:
                    ProgressMixin._clear_layout(child_layout)
            del item

    # ------------------------------------------------------------------
    # Download progress widgets
    # ------------------------------------------------------------------

    def show_progress_widgets(self, is_playlist: bool = False):
        """Show download progress widgets in the right panel."""
        self.disable_interactive_widgets()
        self.convert_button.hide()

        # Show and clear the right panel
        self.progress_container.show()
        self._clear_layout(self.progress_container_layout)

        row_h = self.fontMetrics().height() + 6

        # Create progress frame inside the right panel (stretches to fill)
        self.progress_frame = QGroupBox(t("progress.group_title"))
        self.progress_frame.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.progress_frame.setAlignment(Qt.AlignLeft)
        frame_layout = QVBoxLayout(self.progress_frame)
        frame_layout.setContentsMargins(7, 5, 7, 5)

        num_rows = 4 if is_playlist else 3

        # Thumbnail + info row
        thumb_info_layout = QHBoxLayout()
        thumb_info_layout.setSpacing(4)
        thumb_info_layout.setContentsMargins(0, 0, 0, 0)
        self.thumbnail_label = ScaledPixmapLabel()
        self.thumbnail_label.setFixedSize(60, num_rows * row_h + 2)
        thumb_info_layout.addWidget(self.thumbnail_label, alignment=Qt.AlignLeft | Qt.AlignTop)

        self.info_table = QTableWidget(num_rows, 2)
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
        row = 0
        if is_playlist:
            self._info_row_playlist = row
            item = QTableWidgetItem(t("progress.info.playlist"))
            f = item.font(); f.setBold(True); item.setFont(f)
            item.setFlags(Qt.ItemIsEnabled)
            self.info_table.setItem(row, 0, item)
            val_item = QTableWidgetItem(""); val_item.setFlags(Qt.ItemIsEnabled)
            self.info_table.setItem(row, 1, val_item)
            row += 1
        else:
            self._info_row_playlist = -1
        self._info_row_title = row
        for label in [t("progress.info.title"), t("progress.info.author"), t("progress.info.duration")]:
            item = QTableWidgetItem(label)
            f = item.font(); f.setBold(True); item.setFont(f)
            item.setFlags(Qt.ItemIsEnabled)
            self.info_table.setItem(row, 0, item)
            val_item = QTableWidgetItem(""); val_item.setFlags(Qt.ItemIsEnabled)
            self.info_table.setItem(row, 1, val_item)
            row += 1
        self._info_row_author = self._info_row_title + 1
        self._info_row_duration = self._info_row_title + 2
        self.info_table.setFixedHeight(num_rows * row_h + 2)
        thumb_info_layout.addWidget(self.info_table, 1)
        frame_layout.addLayout(thumb_info_layout)

        # Element progress
        self.progress_label = QLabel(t("progress.element"))
        frame_layout.addWidget(self.progress_label)

        self.video_progress = TextProgressBar()
        self.video_progress.setRange(0, 1000)
        self.video_progress.setValue(0)
        self.video_progress.setTextVisible(True)
        self.video_progress.setFormat("0.0%")
        self.video_progress.setAlignment(Qt.AlignCenter)
        frame_layout.addWidget(self.video_progress)
        self.video_progress_percent = None

        # Total progress (for playlists)
        if is_playlist:
            self.total_progress_label = QLabel(t("progress.total"))
            frame_layout.addWidget(self.total_progress_label)

            self.total_progress = TextProgressBar()
            self.total_progress.setRange(0, 1000)
            self.total_progress.setValue(0)
            self.total_progress.setTextVisible(True)
            self.total_progress.setFormat("0.0%")
            self.total_progress.setAlignment(Qt.AlignCenter)
            frame_layout.addWidget(self.total_progress)
            self.total_progress_percent = None

            # ETA labels (elapsed left, remaining right)
            eta_layout = QHBoxLayout()
            self.eta_elapsed_label = QLabel("")
            self.eta_remaining_label = QLabel("")
            self.eta_remaining_label.setAlignment(Qt.AlignRight)
            eta_layout.addWidget(self.eta_elapsed_label)
            eta_layout.addWidget(self.eta_remaining_label)
            frame_layout.addLayout(eta_layout)
            self._eta_callback = None
            self._eta_timer = QTimer(self)
            self._eta_timer.timeout.connect(self._update_eta_timer)
            self._eta_timer.start(1000)

        # Stop button centered in remaining vertical space
        frame_layout.addStretch()
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
        frame_layout.addWidget(self.stop_button, alignment=Qt.AlignCenter)
        frame_layout.addStretch()

        self.progress_container_layout.addWidget(self.progress_frame, 1)

        # Reset tables-related state
        self._tables_splitter = None
        self._splitter_user_moved = False
        self.normalize_outer_frame = None
        self._normalize_labels = None
        self._normalize_table = None
        self._info_item_count = None
        self._skipped_group = None
        self._skipped_table = None
        self._skipped_count = None

    def hide_progress_widgets(self):
        """Hide progress widgets and restore convert button."""
        self._stop_eta_timer()

        if hasattr(self, 'stop_button') and self.stop_button is not None:
            self.stop_button.hide()
            self.stop_button.deleteLater()
            self.stop_button = None

        if hasattr(self, '_skipped_group') and self._skipped_group is not None:
            self._skipped_group.hide()
            self._skipped_group.deleteLater()
            self._skipped_group = None

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

        # Clear both panels
        self._clear_layout(self.progress_container_layout)
        self._clear_layout(self.tables_layout)
        self.progress_container.hide()
        self.tables_container.hide()

        self._tables_splitter = None
        self._splitter_user_moved = False

        self.convert_button.show()
        self._reset_convert_button()
        self.set_convert_button_enabled(True)
        self.enable_interactive_widgets()

        # Restore input widgets
        if hasattr(self, 'input_container') and self.input_container is not None:
            self.input_container.show()

        self.adjust_window_size(margin=1.0)

    def _reset_convert_button(self):
        """Reset the convert button to its original download state."""
        if not hasattr(self, 'convert_button') or self.convert_button is None:
            return
        self.convert_button.setText(" " + t("button.download"))
        self.convert_button.setIcon(QIcon(DOWNLOAD_ICON_PATH))
        self.convert_button.setIconSize(QSize(18, 18))
        try:
            self.convert_button.clicked.disconnect()
        except RuntimeError:
            pass
        self.convert_button.clicked.connect(self._on_convert_click)

        self._new_download_mode = False

    # ------------------------------------------------------------------
    # Download-again button
    # ------------------------------------------------------------------

    def show_new_download_button(self):
        """Transform the UI for the completed state."""
        self._stop_eta_timer()

        # Hide the right panel
        self.progress_container.hide()

        # Transform convert button into "New download"
        if hasattr(self, 'convert_button') and self.convert_button is not None:
            self.convert_button.show()
            self.convert_button.setEnabled(True)
            self.convert_button.setText(" " + t("button.new_download"))
            self.convert_button.setIcon(QIcon(REFRESH_ICON_PATH))
            self.convert_button.setIconSize(QSize(18, 18))
            try:
                self.convert_button.clicked.disconnect()
            except RuntimeError:
                pass
            self.convert_button.clicked.connect(self._on_download_again_click)

        self._new_download_mode = True

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

    # ------------------------------------------------------------------
    # Splitter for the two summary tables
    # ------------------------------------------------------------------

    def _get_or_create_tables_splitter(self):
        """Lazily create the QSplitter that holds the two summary tables."""
        if not hasattr(self, '_tables_splitter') or self._tables_splitter is None:
            self._tables_splitter = QSplitter(Qt.Vertical)
            self._tables_splitter.setChildrenCollapsible(False)
            self._splitter_user_moved = False
            self._tables_splitter.splitterMoved.connect(
                lambda: setattr(self, '_splitter_user_moved', True)
            )
            self.tables_layout.addWidget(self._tables_splitter, 1)
            self.tables_container.show()
        return self._tables_splitter

    def _snap_splitter_to_skipped(self):
        """Give the skipped table its natural size and leave the rest to normalize."""
        if getattr(self, '_splitter_user_moved', False):
            return
        splitter = getattr(self, '_tables_splitter', None)
        if splitter is None or splitter.count() < 2:
            return
        def _do():
            if splitter is None or splitter.count() < 2:
                return
            total = splitter.height()
            if total < 20:
                return
            skipped_h = self._skipped_group.sizeHint().height()
            norm_h = max(80, total - skipped_h)
            splitter.setSizes([norm_h, skipped_h])
        QTimer.singleShot(0, _do)

    # ------------------------------------------------------------------
    # Skipped entries panel
    # ------------------------------------------------------------------

    def add_skipped_entry(self, entry: dict, reason: str, reason_key: str = ""):
        """Add one unavailable entry to the skipped entries table."""
        if not hasattr(self, 'progress_frame') or self.progress_frame is None:
            return

        ROW_HEIGHT = 24

        # Lazy-create the group box and table
        if not hasattr(self, '_skipped_group') or self._skipped_group is None:
            self._skipped_group = QGroupBox()
            skipped_layout = QVBoxLayout(self._skipped_group)
            skipped_layout.setContentsMargins(5, 10, 5, 8)

            self._skipped_table = CopyableTableWidget()
            self._skipped_table.setColumnCount(4)
            self._skipped_table.setHorizontalHeaderLabels([
                "#",
                t("progress.table.artist"),
                t("progress.table.title"),
                t("progress.table.reason"),
            ])
            self._skipped_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
            self._skipped_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
            self._skipped_table.verticalHeader().setVisible(False)
            self._skipped_table.setShowGrid(False)
            self._skipped_table.setStyleSheet(
                "QTableWidget { border: none; background: transparent; }"
                "QTableWidget QTableCornerButton::section { background: transparent; }"
                "QHeaderView { background: transparent; }"
                "QHeaderView::section { border: none; border-bottom: 1px solid palette(mid); background: transparent; }"
            )
            header = self._skipped_table.horizontalHeader()
            header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
            header.setSectionResizeMode(1, QHeaderView.Stretch)
            header.setSectionResizeMode(2, QHeaderView.Stretch)
            header.setSectionResizeMode(3, QHeaderView.Stretch)
            header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)

            skipped_layout.addWidget(self._skipped_table, 1)
            splitter = self._get_or_create_tables_splitter()
            splitter.addWidget(self._skipped_group)
            self._skipped_count = 0
            self._snap_splitter_to_skipped()

        # Add row
        self._skipped_count += 1
        row = self._skipped_table.rowCount()
        self._skipped_table.insertRow(row)
        self._skipped_table.setRowHeight(row, ROW_HEIGHT)

        num_item = QTableWidgetItem(str(self._skipped_count))
        num_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._skipped_table.setItem(row, 0, num_item)
        self._skipped_table.setItem(row, 1, QTableWidgetItem(entry.get('channel', '') or ''))
        self._skipped_table.setItem(row, 2, QTableWidgetItem(entry.get('title', '') or ''))
        self._skipped_table.setItem(row, 3, QTableWidgetItem(reason))
        if reason_key:
            self._skipped_table.item(row, 3).setData(Qt.UserRole, reason_key)

        # Update group title
        key = "progress.skipped_header"
        self._skipped_group.setTitle(t(key))

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

        ROW_HEIGHT = 24

        if not hasattr(self, '_normalize_labels') or self._normalize_labels is None:
            self._normalize_labels = []

            self.normalize_outer_frame = QGroupBox(t("progress.downloaded_elements"))
            norm_layout = QVBoxLayout(self.normalize_outer_frame)
            norm_layout.setContentsMargins(5, 10, 5, 8)

            self._normalize_table = CopyableTableWidget(0, 6)
            self._normalize_table.setHorizontalHeaderLabels(
                [t("progress.table.number"), t("progress.table.artist"), t("progress.table.title"),
                 t("progress.table.metadatas"), t("progress.table.lyrics"), t("progress.table.norm")]
            )
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
            header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # #
            header.setSectionResizeMode(1, QHeaderView.Stretch)          # Artist
            header.setSectionResizeMode(2, QHeaderView.Stretch)          # Title
            header.setSectionResizeMode(3, QHeaderView.Stretch)          # Metadatas
            header.setSectionResizeMode(4, QHeaderView.Stretch)          # Lyrics
            header.setSectionResizeMode(5, QHeaderView.Stretch)          # Norm.
            header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)

            norm_layout.addWidget(self._normalize_table, 1)
            splitter = self._get_or_create_tables_splitter()
            splitter.insertWidget(0, self.normalize_outer_frame)
            self._snap_splitter_to_skipped()

        # Add a row
        row = self._normalize_table.rowCount()
        self._normalize_table.insertRow(row)
        self._normalize_table.setRowHeight(row, ROW_HEIGHT)
        for col, text in enumerate([str(num), artist, title, metadata, lyrics_type, norm_str]):
            item = QTableWidgetItem(text)
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self._normalize_table.setItem(row, col, item)
        # Store translation keys for retranslation (col 3 = metadatas, col 4 = lyrics, col 5 = norm)
        meta_key = "table.yes" if info.get('metadata_found') else "table.none"
        self._normalize_table.item(row, 3).setData(Qt.UserRole, meta_key)
        if info.get('lyrics_type', 'No') == 'No':
            self._normalize_table.item(row, 4).setData(Qt.UserRole, "table.none")
        if not info.get('volume'):
            self._normalize_table.item(row, 5).setData(Qt.UserRole, "table.none")
        self._normalize_labels.append(num)

        count = len(self._normalize_labels)
        key = "progress.downloaded_element" if count == 1 else "progress.downloaded_elements"
        self.normalize_outer_frame.setTitle(t(key))

        self._normalize_table.scrollToBottom()

    # ------------------------------------------------------------------
    # Fetching progress (pre-download info retrieval)
    # ------------------------------------------------------------------

    def show_fetching_progress(self, is_playlist: bool = False):
        """Show fetching progress bar in the right panel."""
        self.disable_interactive_widgets()
        self.convert_button.hide()

        # Show and clear the right panel
        self.progress_container.show()
        self._clear_layout(self.progress_container_layout)

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

        self.progress_container_layout.addWidget(self.fetching_frame)

        self.adjust_window_size(margin=1.6)

    def update_fetching_progress(self, current: int, total: int = None):
        """Update the fetching progress bar — count shown inside the bar."""
        if not hasattr(self, 'fetching_label') or not hasattr(self, 'fetching_progress'):
            return

        if total and total > 0:
            percentage = (current / total) * 100
            self.fetching_progress.setValue(int(percentage))
            self.fetching_progress.setFormat(f"{current}/{total}")
        else:
            self.fetching_progress.setRange(0, 0)
            self.fetching_progress.setFormat(str(current))

    def hide_fetching_progress(self):
        """Hide fetching progress widgets and restore convert button."""
        if hasattr(self, 'fetching_frame') and self.fetching_frame is not None:
            self.fetching_frame.hide()
            self.fetching_frame.deleteLater()
            self.fetching_frame = None

        self._clear_layout(self.progress_container_layout)

        self.enable_interactive_widgets()
        self.convert_button.show()
        self.set_convert_button_enabled(True)
