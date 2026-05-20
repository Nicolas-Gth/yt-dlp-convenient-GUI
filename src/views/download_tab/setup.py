from PySide6.QtWidgets import QVBoxLayout, QGroupBox
from PySide6.QtCore import Qt

from utils.i18n_utils import t


class DownloadSetupMixin:
    """Mixin that orchestrates widget creation for the download tab."""

    def setup_widgets(self):
        """Create and layout all GUI widgets."""
        self.settings_box = QGroupBox(t("settings.group_title"))
        self.settings_layout = QVBoxLayout(self.settings_box)
        self.settings_layout.setContentsMargins(5, 10, 5, 10)
        self.settings_layout.setSpacing(8)

        self.create_url_input()
        self.create_path_input()
        self.create_format_selection()
        self.create_playlist_selection()
        self.create_options_selection()
        self.settings_layout.addStretch()
        self.create_convert_button()
        self.settings_layout.addStretch()
        self.create_disclaimer()

        self.input_layout.addWidget(self.settings_box)
        self.adjust_window_size(margin=1.0)
        self.setMinimumWidth(self.width() + 20)

    def set_pre_button_spacer_collapsed(self, collapsed: bool):
        """No-op — spacers are no longer manipulated in the side-by-side layout."""

    def set_post_button_spacer_collapsed(self, collapsed: bool):
        """No-op — spacers are no longer manipulated in the side-by-side layout."""
