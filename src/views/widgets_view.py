"""
Widget creation mixin for the main application view.

Contains all create_* methods and related show/hide helpers for
URL input, path input, format selection, playlist options,
normalize options, enrich metadata, convert button, and disclaimer.
"""
from PySide6.QtWidgets import (
    QHBoxLayout, QVBoxLayout, QLabel, QLineEdit, QPushButton,
    QRadioButton, QCheckBox, QComboBox, QButtonGroup, QSpinBox,
    QSizePolicy, QGroupBox, QMessageBox
)
from PySide6.QtGui import QFont, QIcon
from PySide6.QtCore import Qt, QSize

from config import DEFAULT_BITRATES, DEFAULT_QUALITIES, DOWNLOAD_ICON_PATH, INFO_ICON_PATH
from utils import settings_manager
from utils.i18n_utils import t


class WidgetsMixin:
    """Mixin that provides widget creation methods for MainApplicationView."""

    def setup_widgets(self):
        """Create and layout all GUI widgets."""
        self.create_url_input()
        self.create_path_input()
        self.create_format_selection()
        self.create_playlist_selection()
        self.create_options_selection()
        self.main_layout.addStretch()
        # Keep a handle to the spacer above the main action button.
        # This lets the progress summary snap under the checkboxes when active.
        spacer_item = self.main_layout.itemAt(self.main_layout.count() - 1)
        self._pre_button_spacer = spacer_item.spacerItem() if spacer_item is not None else None
        self.create_convert_button()
        self.main_layout.addStretch()
        # Keep a handle to the spacer below the main action button.
        spacer_item = self.main_layout.itemAt(self.main_layout.count() - 1)
        self._post_button_spacer = spacer_item.spacerItem() if spacer_item is not None else None
        self.create_disclaimer()
        self.adjust_window_size()

    def set_pre_button_spacer_collapsed(self, collapsed: bool):
        """Collapse/restore the spacer above the convert button."""
        if not hasattr(self, '_pre_button_spacer') or self._pre_button_spacer is None:
            return

        if collapsed:
            self._pre_button_spacer.changeSize(0, 0, QSizePolicy.Minimum, QSizePolicy.Fixed)
        else:
            self._pre_button_spacer.changeSize(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.main_layout.invalidate()

    def set_post_button_spacer_collapsed(self, collapsed: bool):
        """Collapse/restore the spacer below the convert button."""
        if not hasattr(self, '_post_button_spacer') or self._post_button_spacer is None:
            return

        if collapsed:
            self._post_button_spacer.changeSize(0, 0, QSizePolicy.Minimum, QSizePolicy.Fixed)
        else:
            self._post_button_spacer.changeSize(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.main_layout.invalidate()

    # ------------------------------------------------------------------
    # URL input
    # ------------------------------------------------------------------

    def create_url_input(self):
        """Create URL input field with built-in clear button."""
        url_layout = QHBoxLayout()
        url_layout.setContentsMargins(5, 10, 5, 0)

        self.url_entry = QLineEdit()
        self.url_entry.setPlaceholderText(t("url.placeholder"))
        self.url_entry.setMinimumWidth(400)
        self.url_entry.setClearButtonEnabled(True)
        url_layout.addWidget(self.url_entry, 1)

        self.main_layout.addLayout(url_layout)

    # ------------------------------------------------------------------
    # Path input
    # ------------------------------------------------------------------

    def create_path_input(self):
        """Create path input with integrated browse icon."""
        path_layout = QHBoxLayout()
        path_layout.setContentsMargins(5, 5, 5, 5)

        self.path_entry = QLineEdit()
        self.path_entry.setMinimumWidth(350)
        self.path_entry.setReadOnly(True)
        self.path_entry.setCursor(Qt.PointingHandCursor)

        last_directory = settings_manager.get_last_download_directory()
        if last_directory:
            self.path_entry.setText(last_directory)
        else:
            self.path_entry.setPlaceholderText(t("path.placeholder"))

        self.path_entry.mousePressEvent = lambda e: self._on_browse_click()

        path_layout.addWidget(self.path_entry, 1)

        self.main_layout.addLayout(path_layout)

    # ------------------------------------------------------------------
    # Format selection
    # ------------------------------------------------------------------

    def create_format_selection(self):
        """Create file format selection widgets."""
        self.format_box = QGroupBox(t("format.group_title"))
        format_layout = QHBoxLayout(self.format_box)

        self.format_group = QButtonGroup(self)
        self.mp3_radio = QRadioButton(t("format.mp3"))
        self.mp3_radio.setCursor(Qt.PointingHandCursor)
        self.mp4_radio = QRadioButton(t("format.mp4"))
        self.mp4_radio.setCursor(Qt.PointingHandCursor)
        self.opus_radio = QRadioButton(t("format.opus"))
        self.opus_radio.setCursor(Qt.PointingHandCursor)

        self.format_group.addButton(self.mp3_radio, 1)
        self.format_group.addButton(self.mp4_radio, 2)
        self.format_group.addButton(self.opus_radio, 3)

        format_layout.addWidget(self.mp3_radio)
        format_layout.addWidget(self.mp4_radio)
        format_layout.addWidget(self.opus_radio)

        # Quality label + combo box
        self.quality_label = QLabel(t("quality.label"))
        self.quality_menu = QComboBox()
        self.quality_menu.setMinimumWidth(120)
        format_layout.addWidget(self.quality_label)
        format_layout.addWidget(self.quality_menu)
        format_layout.addStretch()

        format_wrapper = QHBoxLayout()
        format_wrapper.setContentsMargins(5, 0, 5, 0)
        format_wrapper.addWidget(self.format_box)
        self.main_layout.addLayout(format_wrapper)

        # Set initial format from preferences
        fmt = self._format_var
        if fmt == 1:
            self.mp3_radio.setChecked(True)
            self._populate_bitrate_menu()
        elif fmt == 2:
            self.mp4_radio.setChecked(True)
            self._populate_quality_menu()
        elif fmt == 3:
            self.opus_radio.setChecked(True)
            self._populate_bitrate_menu()

        # Connect signals
        self.mp3_radio.toggled.connect(lambda checked: self._on_mp3_selected() if checked else None)
        self.mp4_radio.toggled.connect(lambda checked: self._on_mp4_selected() if checked else None)
        self.opus_radio.toggled.connect(lambda checked: self._on_opus_selected() if checked else None)
        self.quality_menu.currentIndexChanged.connect(self._on_quality_or_bitrate_changed)

    @staticmethod
    def _translate_quality_item(item: str) -> str:
        """Return the translated display label for a quality/bitrate item."""
        if item == "Best":
            return t("quality.best")
        # "Max 128Kbps" → t("quality.max", value="128Kbps")
        if item.startswith("Max "):
            return t("quality.max", value=item[4:])
        return item

    def _populate_bitrate_menu(self):
        """Populate quality_menu with bitrate options."""
        self.quality_menu.blockSignals(True)
        self.quality_menu.clear()
        for item in DEFAULT_BITRATES:
            self.quality_menu.addItem(self._translate_quality_item(item), item)
        active = self._opus_bitrate_var if self.opus_radio.isChecked() else self._mp3_bitrate_var
        idx = self.quality_menu.findData(active)
        if idx >= 0:
            self.quality_menu.setCurrentIndex(idx)
        self.quality_menu.blockSignals(False)

    def _populate_quality_menu(self):
        """Populate quality_menu with quality options."""
        self.quality_menu.blockSignals(True)
        self.quality_menu.clear()
        for item in DEFAULT_QUALITIES:
            self.quality_menu.addItem(self._translate_quality_item(item), item)
        idx = self.quality_menu.findData(self._quality_var)
        if idx >= 0:
            self.quality_menu.setCurrentIndex(idx)
        self.quality_menu.blockSignals(False)

    def switch_to_quality_menu(self):
        """Switch from bitrate to quality menu (MP4)."""
        self._populate_quality_menu()

    def switch_to_bitrate_menu(self):
        """Switch from quality to bitrate menu (MP3/Opus)."""
        self._populate_bitrate_menu()

    # ------------------------------------------------------------------
    # Playlist selection
    # ------------------------------------------------------------------

    def create_playlist_selection(self):
        """Create playlist selection widgets."""
        self.playlist_box = QGroupBox(t("playlist.group_title"))
        self.playlist_layout = QHBoxLayout(self.playlist_box)

        self.playlist_group = QButtonGroup(self)
        self.no_playlist_radio = QRadioButton(t("playlist.no"))
        self.no_playlist_radio.setCursor(Qt.PointingHandCursor)
        self.yes_playlist_radio = QRadioButton(t("playlist.yes"))
        self.yes_playlist_radio.setCursor(Qt.PointingHandCursor)

        self.playlist_group.addButton(self.no_playlist_radio, 1)
        self.playlist_group.addButton(self.yes_playlist_radio, 0)

        self.playlist_layout.addWidget(self.no_playlist_radio)
        self.playlist_layout.addWidget(self.yes_playlist_radio)

        # Playlist range widgets (hidden by default)
        self.playlist_from_label = QLabel(t("playlist.from_video"))
        self.playlist_start_entry = QSpinBox()
        self.playlist_start_entry.setRange(1, 9999)
        self.playlist_start_entry.setValue(self._playlist_start_var)
        self.playlist_start_entry.setFixedWidth(70)
        self.playlist_to_label = QLabel(t("playlist.to"))
        self.playlist_end_entry = QSpinBox()
        self.playlist_end_entry.setRange(1, 9999)
        self.playlist_end_entry.setValue(self._playlist_end_var)
        self.playlist_end_entry.setFixedWidth(70)

        self.playlist_layout.addWidget(self.playlist_from_label)
        self.playlist_layout.addWidget(self.playlist_start_entry)
        self.playlist_layout.addWidget(self.playlist_to_label)
        self.playlist_layout.addWidget(self.playlist_end_entry)
        self.playlist_layout.addStretch()

        playlist_wrapper = QHBoxLayout()
        playlist_wrapper.setContentsMargins(5, 0, 5, 0)
        playlist_wrapper.addWidget(self.playlist_box)
        self.main_layout.addLayout(playlist_wrapper)

        # Set initial state from preferences
        if self._playlist_var == 0:
            self.yes_playlist_radio.setChecked(True)
            self._set_playlist_options_visible(True)
        else:
            self.no_playlist_radio.setChecked(True)
            self._set_playlist_options_visible(False)

        # Connect signals
        self.yes_playlist_radio.toggled.connect(
            lambda checked: self._on_playlist_selected() if checked else None
        )
        self.no_playlist_radio.toggled.connect(
            lambda checked: self._on_no_playlist_selected() if checked else None
        )
        self.playlist_start_entry.valueChanged.connect(self._on_playlist_range_changed)
        self.playlist_end_entry.valueChanged.connect(self._on_playlist_range_changed)

    def _set_playlist_options_visible(self, visible: bool):
        """Show or hide playlist range widgets."""
        self.playlist_from_label.setVisible(visible)
        self.playlist_start_entry.setVisible(visible)
        self.playlist_to_label.setVisible(visible)
        self.playlist_end_entry.setVisible(visible)

    def show_playlist_options(self):
        """Show playlist range selection widgets."""
        self._set_playlist_options_visible(True)

    def hide_playlist_options(self):
        """Hide playlist range selection widgets."""
        self._set_playlist_options_visible(False)

    # ------------------------------------------------------------------
    # Normalize selection
    # ------------------------------------------------------------------

    def create_options_selection(self):
        """Create options fieldset with normalize, enrich and prevent-sleep checkboxes."""
        self.options_box = QGroupBox(t("options.group_title"))
        options_layout = QVBoxLayout(self.options_box)

        # Normalize volume
        self.normalize_layout = QHBoxLayout()

        self.normalize_check = QCheckBox(t("options.normalize_volume"))
        self.normalize_check.setCursor(Qt.PointingHandCursor)
        self.normalize_check.setChecked(self._normalize_var)
        self.normalize_check.toggled.connect(self._on_normalize_toggled)
        self.normalize_layout.addWidget(self.normalize_check)

        # Normalize target widgets (hidden by default)
        self.normalize_target_label = QLabel(t("options.normalize_target"))
        self.normalize_layout.addWidget(self.normalize_target_label)

        self.normalize_target_entry = QLineEdit()
        self.normalize_target_entry.setFixedWidth(50)
        self.normalize_target_entry.setText(str(self._normalize_target_var))
        self.normalize_layout.addWidget(self.normalize_target_entry)

        self.normalize_info_btn = QPushButton()
        self.normalize_info_btn.setIcon(QIcon(INFO_ICON_PATH))
        self.normalize_info_btn.setIconSize(QSize(14, 14))
        self.normalize_info_btn.setFlat(True)
        self.normalize_info_btn.setCursor(Qt.PointingHandCursor)
        self.normalize_info_btn.setFixedSize(20, 20)
        self.normalize_info_btn.clicked.connect(
            lambda: QMessageBox.information(self, t("options.normalize_volume"), t("options.normalize_tooltip"))
        )
        self.normalize_layout.addWidget(self.normalize_info_btn)
        self.normalize_layout.addStretch()

        options_layout.addLayout(self.normalize_layout)

        # Set initial visibility
        visible = self._normalize_var
        self.normalize_target_label.setVisible(visible)
        self.normalize_target_entry.setVisible(visible)
        self.normalize_info_btn.setVisible(visible)

        # Enrich metadata
        enrich_layout = QHBoxLayout()

        self.enrich_check = QCheckBox(t("options.enrich_metadata"))
        self.enrich_check.setCursor(Qt.PointingHandCursor)
        self.enrich_check.setChecked(self._enrich_var)
        self.enrich_check.toggled.connect(self._on_enrich_toggled)
        enrich_layout.addWidget(self.enrich_check)

        self.enrich_info_btn = QPushButton()
        self.enrich_info_btn.setIcon(QIcon(INFO_ICON_PATH))
        self.enrich_info_btn.setIconSize(QSize(14, 14))
        self.enrich_info_btn.setFlat(True)
        self.enrich_info_btn.setCursor(Qt.PointingHandCursor)
        self.enrich_info_btn.setFixedSize(20, 20)
        self.enrich_info_btn.clicked.connect(
            lambda: QMessageBox.information(self, t("options.enrich_metadata"), t("options.enrich_tooltip"))
        )
        enrich_layout.addWidget(self.enrich_info_btn)
        enrich_layout.addStretch()

        options_layout.addLayout(enrich_layout)

        # Prevent sleep
        sleep_layout = QHBoxLayout()

        self.prevent_sleep_check = QCheckBox(t("options.prevent_sleep"))
        self.prevent_sleep_check.setCursor(Qt.PointingHandCursor)
        self.prevent_sleep_check.setChecked(self._prevent_sleep_var)
        self.prevent_sleep_check.toggled.connect(self._on_prevent_sleep_toggled)
        sleep_layout.addWidget(self.prevent_sleep_check)
        sleep_layout.addStretch()

        options_layout.addLayout(sleep_layout)

        options_wrapper = QHBoxLayout()
        options_wrapper.setContentsMargins(5, 0, 5, 0)
        options_wrapper.addWidget(self.options_box)

        self.main_layout.addLayout(options_wrapper)

    def show_normalize_input(self):
        """Show the normalize target LUFS input."""
        self.normalize_target_label.setVisible(True)
        self.normalize_target_entry.setVisible(True)
        self.normalize_info_btn.setVisible(True)

    def hide_normalize_input(self):
        """Hide the normalize target LUFS input."""
        self.normalize_target_label.setVisible(False)
        self.normalize_target_entry.setVisible(False)
        self.normalize_info_btn.setVisible(False)

    # ------------------------------------------------------------------
    # Convert button
    # ------------------------------------------------------------------

    def create_convert_button(self):
        """Create the main convert button."""
        self.convert_button = QPushButton(" " + t("button.download"))
        self.convert_button.setIcon(QIcon(DOWNLOAD_ICON_PATH))
        self.convert_button.setIconSize(QSize(18, 18))
        self.convert_button.setFont(QFont("Bahnschrift", 12))
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
        self.main_layout.addWidget(self.convert_button, alignment=Qt.AlignCenter)

    # ------------------------------------------------------------------
    # Disclaimer
    # ------------------------------------------------------------------

    def create_disclaimer(self):
        """Create the disclaimer text."""
        # Placeholder — the original was an empty frame
        pass
