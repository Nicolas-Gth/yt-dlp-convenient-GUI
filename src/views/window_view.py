"""
Window management mixin for the main application view.

Handles window initialisation, font/style configuration,
menu bar, and dynamic window resizing.
"""
from PySide6.QtGui import QFont, QIcon, QAction, QActionGroup, QDesktopServices
from PySide6.QtCore import Qt, QUrl
from PySide6.QtWidgets import QMenuBar, QMenu, QMessageBox, QWidgetAction, QCheckBox
from config import APP_TITLE, APP_NAME, APP_VERSION, APP_AUTHOR, APP_AUTHOR_URL, ICON_PATH, COOKIES_DIR
from utils.i18n_utils import t, AVAILABLE_LANGUAGES, MENU_LANGUAGES


class WindowMixin:
    """Mixin that provides window setup, styling, and sizing methods."""

    def setup_window(self):
        """Initialize the main window."""
        self.setWindowTitle(APP_TITLE)

        icon = QIcon(ICON_PATH)
        if not icon.isNull():
            self.setWindowIcon(icon)

        self._setup_menu_bar()

    def _update_window_title(self, experimental: bool = False):
        """Update the window title to show an experimental indicator."""
        if experimental:
            self.setWindowTitle(f"{APP_TITLE}  [Experimental]")
        else:
            self.setWindowTitle(APP_TITLE)

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

        # --- Settings menu ---
        self._settings_menu = menu_bar.addMenu(t("menu.settings"))

        # Prevent sleep — use QWidgetAction so the menu stays open on click
        self._prevent_sleep_action = QWidgetAction(self)
        self._prevent_sleep_check = QCheckBox(t("menu.settings.prevent_sleep"))
        self._prevent_sleep_check.setCursor(Qt.PointingHandCursor)
        self._prevent_sleep_check.setStyleSheet("QCheckBox { padding-left: 8px; padding-right: 8px; padding-top: 4px; padding-bottom: 4px; }")
        self._prevent_sleep_check.toggled.connect(self._on_prevent_sleep_toggled)
        self._prevent_sleep_action.setDefaultWidget(self._prevent_sleep_check)
        self._settings_menu.addAction(self._prevent_sleep_action)

        # Experimental version
        self._experimental_action = QWidgetAction(self)
        self._experimental_check = QCheckBox(t("menu.settings.experimental_version"))
        self._experimental_check.setCursor(Qt.PointingHandCursor)
        self._experimental_check.setStyleSheet("QCheckBox { padding-left: 8px; padding-right: 8px; padding-top: 4px; padding-bottom: 4px; }")
        self._experimental_check.toggled.connect(self._on_experimental_toggled)
        self._experimental_action.setDefaultWidget(self._experimental_check)
        self._settings_menu.addAction(self._experimental_action)

        # --- Help menu ---
        self._help_menu = menu_bar.addMenu(t("menu.help"))
        self._cookies_help_action = QAction(t("menu.help.youtube_cookies"), self)
        self._cookies_help_action.triggered.connect(self._show_cookies_help)
        self._help_menu.addAction(self._cookies_help_action)

        # --- Infos menu ---
        self._infos_menu = menu_bar.addMenu(t("menu.infos"))
        self._legal_action = QAction(t("menu.legal_notice"), self)
        self._legal_action.triggered.connect(self._show_legal_notice)
        self._infos_menu.addAction(self._legal_action)
        self._author_action = QAction(t("menu.infos.author"), self)
        self._author_action.triggered.connect(self._show_author_info)
        self._infos_menu.addAction(self._author_action)
        self._open_folder_action = QAction(t("menu.infos.open_folder"), self)
        self._open_folder_action.triggered.connect(self._open_install_folder)
        self._infos_menu.addAction(self._open_folder_action)

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
        self._settings_menu.setTitle(t("menu.settings"))
        self._prevent_sleep_check.setText(t("menu.settings.prevent_sleep"))
        self._experimental_check.setText(t("menu.settings.experimental_version"))
        self._help_menu.setTitle(t("menu.help"))
        self._cookies_help_action.setText(t("menu.help.youtube_cookies"))
        self._infos_menu.setTitle(t("menu.infos"))
        self._legal_action.setText(t("menu.legal_notice"))
        self._author_action.setText(t("menu.infos.author"))
        self._open_folder_action.setText(t("menu.infos.open_folder"))

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
        if hasattr(self, 'settings_box'):
            self.settings_box.setTitle(t("settings.group_title"))
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
        if hasattr(self, 'template_entry'):
            self.template_entry.setPlaceholderText(t("format.template_placeholder"))
        if hasattr(self, 'template_presets'):
            # Repopulate preset dropdown with translated labels, preserving selection
            current_data = self.template_presets.currentData()
            self.template_presets.blockSignals(True)
            self.template_presets.clear()
            for template_val, label_key in self._TEMPLATE_PRESETS:
                self.template_presets.addItem(t(label_key), template_val)
            self.template_presets.addItem(t("format.template_preset_custom"), None)
            idx = self.template_presets.findData(current_data)
            self.template_presets.setCurrentIndex(idx if idx >= 0 else self.template_presets.count() - 1)
            self.template_presets.blockSignals(False)
        if hasattr(self, 'playlist_box'):
            self.playlist_box.setTitle(t("playlist.group_title"))
            self.no_playlist_radio.setText(t("playlist.no"))
            self.yes_playlist_radio.setText(t("playlist.yes"))
            self.playlist_from_label.setText(t("playlist.from_video"))
            self.playlist_to_label.setText(t("playlist.to"))

        # Options
        if hasattr(self, 'options_box'):
            self.options_box.setTitle(t("extras.group_title"))
            self.normalize_check.setText(t("options.normalize_volume"))
            self.normalize_target_label.setText(t("options.normalize_target"))
        if hasattr(self, 'enrich_check'):
            self.enrich_check.setText(t("options.enrich_metadata"))

        # Convert button (only if not mid-download)
        if hasattr(self, 'convert_button') and self.convert_button.isVisible():
            self.convert_button.setText(" " + t("button.download"))

        # Tab titles
        if hasattr(self, 'tabs'):
            self.tabs.setTabText(0, t("tabs.download"))
            idx = self.tabs.indexOf(getattr(self, '_files_tab', None))
            if idx >= 0:
                self.tabs.setTabText(idx, t("tabs.files"))

    def _open_install_folder(self):
        """Open the application installation folder in the system file browser."""
        QDesktopServices.openUrl(QUrl.fromLocalFile(COOKIES_DIR))

    def _show_legal_notice(self):
        """Show the legal notice dialog."""
        msg = QMessageBox(self)
        msg.setWindowTitle(t("legal.title"))
        msg.setIcon(QMessageBox.Information)
        msg.setText(t("legal.text", app_name=APP_NAME, app_version=APP_VERSION))
        ok_button = msg.addButton(QMessageBox.Ok)
        ok_button.setIcon(QIcon())
        msg.exec()

    def _show_author_info(self):
        """Show the author info dialog."""
        msg = QMessageBox(self)
        msg.setWindowTitle(t("author.title"))
        msg.setIcon(QMessageBox.Information)
        msg.setTextFormat(Qt.RichText)
        msg.setText(t("author.text", author=APP_AUTHOR, url=APP_AUTHOR_URL))
        ok_button = msg.addButton(QMessageBox.Ok)
        ok_button.setIcon(QIcon())
        msg.exec()

    def _show_cookies_help(self):
        """Show the YouTube cookies help dialog."""
        msg = QMessageBox(self)
        msg.setWindowTitle(t("help.cookies.title"))
        msg.setIcon(QMessageBox.Information)
        msg.setText(t("cookies.instructions", cookies_dir=COOKIES_DIR))
        ok_button = msg.addButton(QMessageBox.Ok)
        ok_button.setIcon(QIcon())
        msg.exec()

    def setup_fonts(self):
        """Configure fonts."""
        self.default_font = self.font()
        self.title_font = self.font()
        self.title_font.setBold(True)

    def adjust_window_size(self, extra_height: int = 0, margin: float = 1.2):
        """Adjust window size to fit content.

        Qt layouts do not update sizeHint() when a hidden child is shown
        after the window is already visible.  Walk down to leaf widgets
        (QLabel, QPushButton, …) whose sizeHints stay correct.
        """
        if self.isMaximized() or self.isFullScreen():
            return
        def _widest_leaf(lo):
            w = 0
            for i in range(lo.count()):
                item = lo.itemAt(i)
                child = item.widget()
                if child is not None:
                    if child.layout() is not None:
                        w = max(w, _widest_leaf(child.layout()))
                    w = max(w, child.sizeHint().width(), child.minimumWidth())
                elif item.layout() is not None:
                    w = max(w, _widest_leaf(item.layout()))
            return w

        cw = self.centralWidget()
        if hasattr(self, '_top_layout'):
            w = 0
            for i in range(self._top_layout.count()):
                child = self._top_layout.itemAt(i).widget()
                if child and not child.isHidden():
                    child.updateGeometry()
                    w += max(child.sizeHint().width(),
                            _widest_leaf(child.layout()) if child.layout() else 0)
        else:
            self.main_layout.activate()
            w = self.main_layout.sizeHint().width()

        w = int(w * margin)

        self.main_layout.activate()
        h = self.main_layout.sizeHint().height() + extra_height
        diff_w = max(0, self.frameGeometry().width() - cw.width())
        diff_h = max(0, self.frameGeometry().height() - cw.height())
        if w > diff_w:
            self.resize(w + diff_w, h + diff_h)
