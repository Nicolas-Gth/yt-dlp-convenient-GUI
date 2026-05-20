import re

from PySide6.QtWidgets import (
    QHBoxLayout, QVBoxLayout, QLabel, QLineEdit, QPushButton,
    QComboBox, QButtonGroup, QRadioButton, QMessageBox, QGroupBox
)
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt, QSize

from config import DEFAULT_BITRATES, DEFAULT_QUALITIES, INFO_ICON_PATH
from utils.i18n_utils import t


class DownloadFormatMixin:
    """Mixin that creates file-format and template selection widgets."""

    # Allowed template variables for validation
    _TEMPLATE_VARIABLES = {"title", "tracknumber", "artist", "album",
                           "Y", "y", "m", "d", "H", "M", "S", "B", "b"}
    _TEMPLATE_VAR_RE = re.compile(r'\{(\w+)\}')

    _TEMPLATE_PRESETS = [
        ("{artist} - {title}",          "format.template_preset_default"),
        ("{Y}-{m}-{d} - {artist} - {title}", "format.template_preset_date_artist"),
        ("{Y}{m}{d}_{H}{M}{S}_{title}", "format.template_preset_date_time"),
        ("{tracknumber} - {artist} - {title}", "format.template_preset_track_artist"),
        ("{artist}/{album}/{artist} - {title}", "format.template_preset_artist_album"),
        ("{artist}/{album}/{tracknumber} - {title}", "format.template_preset_album_track"),
        ("{title}",                      "format.template_preset_simple"),
    ]

    def create_format_selection(self):
        """Create file format selection widgets."""
        self.format_box = QGroupBox(t("format.group_title"))
        format_box_layout = QVBoxLayout(self.format_box)
        format_box_layout.setSpacing(6)

        # Row 1: format radios + quality
        format_row = QHBoxLayout()
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

        format_row.addWidget(self.mp3_radio)
        format_row.addWidget(self.mp4_radio)
        format_row.addWidget(self.opus_radio)

        # Quality label + combo box
        self.quality_label = QLabel(t("quality.label"))
        self.quality_menu = QComboBox()
        format_row.addWidget(self.quality_label)
        format_row.addWidget(self.quality_menu)
        format_row.addStretch()
        format_box_layout.addLayout(format_row)

        # Row 2: template input + preset dropdown + info button
        template_row = QHBoxLayout()
        self.template_entry = QLineEdit()
        self.template_entry.setPlaceholderText(t("format.template_placeholder"))
        if self._output_template_var:
            self.template_entry.setText(self._output_template_var)
        self.template_entry.textChanged.connect(self._on_template_text_changed)

        self.template_presets = QComboBox()
        self.template_presets.setCursor(Qt.PointingHandCursor)
        for template_val, label_key in self._TEMPLATE_PRESETS:
            self.template_presets.addItem(t(label_key), template_val)
        self.template_presets.addItem(t("format.template_preset_custom"), None)
        # Set initial dropdown selection based on saved template
        current_template = self.template_entry.text().strip()
        idx = self.template_presets.findData(current_template)
        self.template_presets.setCurrentIndex(idx if idx >= 0 else self.template_presets.count() - 1)
        self.template_presets.currentIndexChanged.connect(self._on_template_preset_changed)

        self.template_info_btn = QPushButton()
        self.template_info_btn.setIcon(QIcon(INFO_ICON_PATH))
        self.template_info_btn.setIconSize(QSize(14, 14))
        self.template_info_btn.setFlat(True)
        self.template_info_btn.setCursor(Qt.PointingHandCursor)
        self.template_info_btn.setFixedSize(20, 20)
        self.template_info_btn.clicked.connect(
            lambda: QMessageBox.information(self, t("format.template_info_title"), t("format.template_info_text"))
        )

        template_row.addWidget(self.template_entry, 1)
        template_row.addWidget(self.template_presets)
        template_row.addWidget(self.template_info_btn)
        format_box_layout.addLayout(template_row)

        format_wrapper = QHBoxLayout()
        format_wrapper.setContentsMargins(5, 0, 5, 0)
        format_wrapper.addWidget(self.format_box)
        self.settings_layout.addLayout(format_wrapper)

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

        # Initial validation of template field
        self._validate_template_visual(self.template_entry.text())

        # Connect signals
        self.mp3_radio.toggled.connect(lambda checked: self._on_mp3_selected() if checked else None)
        self.mp4_radio.toggled.connect(lambda checked: self._on_mp4_selected() if checked else None)
        self.opus_radio.toggled.connect(lambda checked: self._on_opus_selected() if checked else None)
        self.quality_menu.currentIndexChanged.connect(self._on_quality_or_bitrate_changed)

    def _validate_template_visual(self, text: str):
        """Apply visual feedback on the template entry: border colour for invalid variables."""
        if not text.strip():
            self.template_entry.setStyleSheet("")
            return
        invalid = self._get_invalid_template_vars(text)
        if invalid:
            self.template_entry.setStyleSheet(
                "QLineEdit { border: 1px solid #e06060; }"
            )
        else:
            self.template_entry.setStyleSheet("")

    @classmethod
    def _get_invalid_template_vars(cls, template: str) -> set:
        """Return the set of variable names in *template* that are not allowed."""
        used = set(re.findall(cls._TEMPLATE_VAR_RE, template))
        return used - cls._TEMPLATE_VARIABLES

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
