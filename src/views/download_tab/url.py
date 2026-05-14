from PySide6.QtWidgets import QHBoxLayout, QLineEdit

from utils.i18n_utils import t


class DownloadURLMixin:
    """Mixin that creates the URL input widget."""

    def create_url_input(self):
        """Create URL input field with built-in clear button."""
        url_layout = QHBoxLayout()
        url_layout.setContentsMargins(5, 10, 5, 0)

        self.url_entry = QLineEdit()
        self.url_entry.setPlaceholderText(t("url.placeholder"))
        self.url_entry.setClearButtonEnabled(True)
        url_layout.addWidget(self.url_entry, 1)

        self.settings_layout.addLayout(url_layout)

    def _clear_url_input(self):
        """Clear the URL input field."""
        self.url_entry.clear()
        self.url_entry.clearFocus()
