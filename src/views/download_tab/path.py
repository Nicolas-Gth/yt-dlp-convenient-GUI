from PySide6.QtWidgets import QHBoxLayout, QLineEdit
from PySide6.QtCore import Qt

from utils import settings_manager
from utils.i18n_utils import t


class DownloadPathMixin:
    """Mixin that creates the download path input widget."""

    def create_path_input(self):
        """Create path input with integrated browse icon."""
        path_layout = QHBoxLayout()
        path_layout.setContentsMargins(5, 5, 5, 5)

        self.path_entry = QLineEdit()
        self.path_entry.setReadOnly(True)
        self.path_entry.setCursor(Qt.PointingHandCursor)

        last_directory = settings_manager.get_last_download_directory()
        if last_directory:
            self.path_entry.setText(last_directory)
        else:
            self.path_entry.setPlaceholderText(t("path.placeholder"))

        self.path_entry.mousePressEvent = lambda e: self._on_browse_click()

        path_layout.addWidget(self.path_entry, 1)

        self.settings_layout.addLayout(path_layout)
