from PySide6.QtWidgets import QHBoxLayout, QGroupBox, QRadioButton, QButtonGroup, QLabel, QSpinBox
from PySide6.QtCore import Qt

from utils.i18n_utils import t


class DownloadPlaylistMixin:
    """Mixin that creates playlist selection widgets."""

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
        self.settings_layout.addLayout(playlist_wrapper)

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
