from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QGroupBox, QSizePolicy, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QFrame, QSplitter, QWidget
)
from PySide6.QtGui import QFont, QIcon
from PySide6.QtCore import Qt, QSize, QTimer

from config import DOWNLOAD_ICON_PATH, REFRESH_ICON_PATH, STOP_ICON_PATH
from utils.i18n_utils import t

from .widgets import TextProgressBar, ScaledPixmapLabel
from .layout import ProgressLayoutMixin


class ProgressSetupMixin(ProgressLayoutMixin):
    """Mixin that shows/hides download progress widgets."""

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
