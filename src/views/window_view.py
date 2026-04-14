"""
Window management mixin for the main application view.

Handles window initialisation, font/style configuration,
menu bar, and dynamic window resizing.
"""
from PySide6.QtGui import QFont, QIcon, QAction, QActionGroup
from PySide6.QtWidgets import QMenuBar, QMenu, QMessageBox
from config import APP_TITLE, APP_NAME, APP_VERSION, ICON_PATH, PLATFORM_SCALE


class WindowMixin:
    """Mixin that provides window setup, styling, and sizing methods."""

    def setup_window(self):
        """Initialize the main window."""
        self.setWindowTitle(APP_TITLE)
        self.setMinimumWidth(PLATFORM_SCALE['width_base'])

        icon = QIcon(ICON_PATH)
        if not icon.isNull():
            self.setWindowIcon(icon)

        self._setup_menu_bar()

    def _setup_menu_bar(self):
        """Create the application menu bar."""
        menu_bar = self.menuBar()

        # --- Language menu ---
        lang_menu = menu_bar.addMenu("Language")
        self._lang_group = QActionGroup(self)
        self._lang_group.setExclusive(True)
        for code, label in [("en", "English"), ("fr", "Français")]:
            action = QAction(label, self)
            action.setCheckable(True)
            action.setData(code)
            action.triggered.connect(lambda checked, c=code: self._on_language_changed(c))
            self._lang_group.addAction(action)
            lang_menu.addAction(action)
        self._lang_group.actions()[0].setChecked(True)

        # --- Theme menu ---
        theme_menu = menu_bar.addMenu("Theme")
        self._theme_group = QActionGroup(self)
        self._theme_group.setExclusive(True)
        for name in ("System", "Dark", "Light"):
            action = QAction(name, self)
            action.setCheckable(True)
            action.setData(name.lower())
            action.triggered.connect(lambda checked, n=name.lower(): self._on_theme_changed(n))
            self._theme_group.addAction(action)
            theme_menu.addAction(action)
        self._theme_group.actions()[0].setChecked(True)

        # --- Legal notice ---
        legal_action = menu_bar.addAction("Legal notice")
        legal_action.triggered.connect(self._show_legal_notice)

    def _on_language_changed(self, code: str):
        """Handle language selection (placeholder)."""
        pass

    def _on_theme_changed(self, name: str):
        """Handle theme selection."""
        if hasattr(self, 'on_theme_change_callback') and self.on_theme_change_callback:
            self.on_theme_change_callback(name)

    def set_theme_checked(self, name: str):
        """Check the matching theme action in the menu bar."""
        for action in self._theme_group.actions():
            if action.data() == name:
                action.setChecked(True)
                break

    def _show_legal_notice(self):
        """Show the legal notice dialog."""
        msg = QMessageBox(self)
        msg.setWindowTitle("Legal notice")
        msg.setIcon(QMessageBox.Information)
        msg.setText(
            f"{APP_NAME} v{APP_VERSION}\n\n"
            "This software is provided as-is for personal use only.\n\n"
            "It relies on yt-dlp, an open-source project licensed under the Unlicense.\n"
            "Users are solely responsible for ensuring their use complies with "
            "applicable laws and the terms of service of content platforms.\n\n"
            "This tool does not host, store, or distribute any copyrighted content.\n\n"
            "Made by Nicolas-Gth"
        )
        ok_button = msg.addButton(QMessageBox.Ok)
        ok_button.setIcon(QIcon())
        msg.exec()

    def setup_fonts(self):
        """Configure fonts."""
        self.default_font = QFont("Arial", 9)
        self.title_font = QFont("Arial", 10, QFont.Bold)
        self.setFont(self.default_font)

    def adjust_window_size(self, extra_height: int = 0):
        """Adjust window size to fit content automatically."""
        self.adjustSize()
