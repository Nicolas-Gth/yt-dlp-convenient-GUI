from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel, QProgressBar
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt

from config import STOP_ICON_PATH
from utils.i18n_utils import t


class ProgressFetchingMixin:
    """Mixin that shows pre-download fetching progress."""

    def show_fetching_progress(self, is_playlist: bool = False):
        """Show fetching progress bar in the right panel."""
        self.disable_interactive_widgets()
        self.convert_button.hide()
        self.stop_button.setEnabled(True)
        self.stop_button.setText(" " + t("button.stop"))
        self.stop_button.setIcon(QIcon(STOP_ICON_PATH))
        self.stop_button.setStyleSheet("""
            QPushButton {
                background-color: #a63333; color: white; border: none;
                border-radius: 4px; padding: 8px 16px;
            }
            QPushButton:hover { background-color: #c94444; }
        """)
        self.stop_button.show()

        self.progress_container.show()
        self._clear_layout(self.progress_inner_layout)
        self.group_layout.setStretchFactor(self.progress_inner, 1)

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

        self.progress_inner_layout.addStretch(1)
        self.progress_inner_layout.addWidget(self.fetching_frame)
        self.progress_inner_layout.addStretch(1)

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

        self._clear_layout(self.progress_inner_layout)

        self.enable_interactive_widgets()
        self.convert_button.show()
        self.stop_button.hide()
        self.set_convert_button_enabled(True)
