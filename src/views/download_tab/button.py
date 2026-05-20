from PySide6.QtWidgets import QPushButton
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt, QSize

from config import DOWNLOAD_ICON_PATH
from utils.i18n_utils import t


class DownloadButtonMixin:
    """Mixin that creates the main download button."""

    def create_convert_button(self):
        """Create the main convert button."""
        self.convert_button = QPushButton(" " + t("button.download"))
        self.convert_button.setIcon(QIcon(DOWNLOAD_ICON_PATH))
        self.convert_button.setIconSize(QSize(18, 18))
        self.convert_button.setCursor(Qt.PointingHandCursor)
        self.convert_button.setStyleSheet("""
            QPushButton {
                background-color: #238a45;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton:hover { background-color: #449468; }
            QPushButton:disabled { background-color: palette(mid); color: palette(dark); }
        """)
        self.convert_button.clicked.connect(self._on_convert_click)
        self.settings_layout.addWidget(self.convert_button, alignment=Qt.AlignCenter)
