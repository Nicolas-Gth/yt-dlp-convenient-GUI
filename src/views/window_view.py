"""
Window management mixin for the main application view.

Handles window initialisation, font/style configuration,
and dynamic window resizing.
"""
from PySide6.QtGui import QFont, QIcon
from config import APP_TITLE, ICON_PATH, PLATFORM_SCALE


class WindowMixin:
    """Mixin that provides window setup, styling, and sizing methods."""

    def setup_window(self):
        """Initialize the main window."""
        self.setWindowTitle(APP_TITLE)
        self.setMinimumWidth(PLATFORM_SCALE['width_base'])

        icon = QIcon(ICON_PATH)
        if not icon.isNull():
            self.setWindowIcon(icon)

    def setup_fonts(self):
        """Configure fonts."""
        self.default_font = QFont("Arial", 9)
        self.title_font = QFont("Arial", 10, QFont.Bold)
        self.setFont(self.default_font)

    def adjust_window_size(self, extra_height: int = 0):
        """Adjust window size to fit content automatically."""
        self.adjustSize()
