"""
Window management mixin for the main application view.

Handles window initialisation, font/style configuration,
menu bar, and dynamic window resizing.
"""
from PySide6.QtGui import QFont, QIcon, QAction, QActionGroup
from PySide6.QtWidgets import QMenuBar, QMenu, QMessageBox
from config import APP_TITLE, APP_NAME, APP_VERSION, ICON_PATH, PLATFORM_SCALE
from utils.i18n_utils import t, AVAILABLE_LANGUAGES, MENU_LANGUAGES


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
        self._lang_menu = menu_bar.addMenu(t("menu.language"))
        self._lang_group = QActionGroup(self)
        self._lang_group.setExclusive(True)
        for code, label_key in MENU_LANGUAGES:
            action = QAction(t(label_key) if code == "system" else label_key, self)
            action.setCheckable(True)
            action.setData(code)
            action.triggered.connect(lambda checked, c=code: self._on_language_changed(c))
            self._lang_group.addAction(action)
            self._lang_menu.addAction(action)
        self._lang_group.actions()[0].setChecked(True)

        # --- Theme menu ---
        self._theme_menu = menu_bar.addMenu(t("menu.theme"))
        self._theme_group = QActionGroup(self)
        self._theme_group.setExclusive(True)
        for key, data in [("menu.theme.system", "system"), ("menu.theme.dark", "dark"), ("menu.theme.light", "light")]:
            action = QAction(t(key), self)
            action.setCheckable(True)
            action.setData(data)
            action.triggered.connect(lambda checked, n=data: self._on_theme_changed(n))
            self._theme_group.addAction(action)
            self._theme_menu.addAction(action)
        self._theme_group.actions()[0].setChecked(True)

        # --- Legal notice ---
        self._legal_action = menu_bar.addAction(t("menu.legal_notice"))
        self._legal_action.triggered.connect(self._show_legal_notice)

    def _on_language_changed(self, code: str):
        """Handle language selection and retranslate the UI."""
        from utils.i18n_utils import set_language
        set_language(code)
        if hasattr(self, 'on_language_change_callback') and self.on_language_change_callback:
            self.on_language_change_callback(code)
        self.retranslate_ui()

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

    def set_language_checked(self, code: str):
        """Check the matching language action in the menu bar."""
        for action in self._lang_group.actions():
            if action.data() == code:
                action.setChecked(True)
                break

    def retranslate_ui(self):
        """Retranslate all static UI strings after a language change."""
        # Menu titles
        self._lang_menu.setTitle(t("menu.language"))
        self._theme_menu.setTitle(t("menu.theme"))
        self._legal_action.setText(t("menu.legal_notice"))

        # "System" language action label
        for action in self._lang_group.actions():
            if action.data() == "system":
                action.setText(t("menu.language.system"))
                break

        # Theme action labels
        theme_keys = ["menu.theme.system", "menu.theme.dark", "menu.theme.light"]
        for action, key in zip(self._theme_group.actions(), theme_keys):
            action.setText(t(key))

        # URL & path placeholders
        if hasattr(self, 'url_entry'):
            self.url_entry.setPlaceholderText(t("url.placeholder"))
        if hasattr(self, 'path_entry') and not self.path_entry.text():
            self.path_entry.setPlaceholderText(t("path.placeholder"))

        # GroupBox titles
        if hasattr(self, 'format_box'):
            self.format_box.setTitle(t("format.group_title"))
            self.mp3_radio.setText(t("format.mp3"))
            self.mp4_radio.setText(t("format.mp4"))
            self.opus_radio.setText(t("format.opus"))
            self.quality_label.setText(t("quality.label"))
            # Re-populate quality/bitrate dropdown with translated labels
            if self.mp4_radio.isChecked():
                self._populate_quality_menu()
            else:
                self._populate_bitrate_menu()
        if hasattr(self, 'playlist_box'):
            self.playlist_box.setTitle(t("playlist.group_title"))
            self.no_playlist_radio.setText(t("playlist.no"))
            self.yes_playlist_radio.setText(t("playlist.yes"))
            self.playlist_from_label.setText(t("playlist.from_video"))
            self.playlist_to_label.setText(t("playlist.to"))

        # Options
        if hasattr(self, 'options_box'):
            self.options_box.setTitle(t("options.group_title"))
            self.normalize_check.setText(t("options.normalize_volume"))
            self.normalize_target_label.setText(t("options.normalize_target"))
            self.normalize_hint_label.setText(t("options.normalize_hint"))
        if hasattr(self, 'enrich_check'):
            self.enrich_check.setText(t("options.enrich_metadata"))
            self.enrich_hint.setText(t("options.enrich_hint"))
        if hasattr(self, 'prevent_sleep_check'):
            self.prevent_sleep_check.setText(t("options.prevent_sleep"))

        # Convert button (only if not mid-download)
        if hasattr(self, 'convert_button') and self.convert_button.isVisible():
            self.convert_button.setText(" " + t("button.download"))

    def _show_legal_notice(self):
        """Show the legal notice dialog."""
        msg = QMessageBox(self)
        msg.setWindowTitle(t("legal.title"))
        msg.setIcon(QMessageBox.Information)
        msg.setText(t("legal.text", app_name=APP_NAME, app_version=APP_VERSION))
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
