"""
Main application view — orchestrator that composes all view mixins.

The heavy lifting is split across:
    - window_view.py    : window setup, styling & sizing (WindowMixin)
    - widgets_view.py   : widget creation (WidgetsMixin)
    - progress_view.py  : download progress UI (ProgressMixin)
    - event_handlers_view.py : callbacks & validation (EventHandlersMixin)
"""
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout
from PySide6.QtCore import Qt

from config import DEFAULT_BITRATE, DEFAULT_QUALITY, DEFAULT_NORMALIZE_TARGET, FILE_FORMATS
from utils import settings_manager
from utils.i18n_utils import t
from models import DownloadConfig

from .window_view import WindowMixin
from .widgets_view import WidgetsMixin
from .progress_view import ProgressMixin
from .event_handlers_view import EventHandlersMixin


class MainApplicationView(QMainWindow, WindowMixin, WidgetsMixin, ProgressMixin, EventHandlersMixin):
    """Main application window and GUI components."""

    def __init__(self):
        super().__init__()

        # Central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QVBoxLayout(central_widget)
        self.main_layout.setContentsMargins(5, 5, 5, 10)
        self.main_layout.setSpacing(8)

        self.setup_window()
        self.setup_fonts()
        self.setup_variables()
        self.setup_widgets()
        self.progress_widgets = {}

        # Callbacks (set by controller)
        self.on_browse_callback = None
        self.on_convert_callback = None
        self.on_format_change_callback = None
        self.on_playlist_change_callback = None
        self.on_stop_callback = None
        self.on_theme_change_callback = None
        self.on_language_change_callback = None

    # ------------------------------------------------------------------
    # Variables (simple Python attributes instead of Tk vars)
    # ------------------------------------------------------------------

    def setup_variables(self):
        """Initialize state variables."""
        preferences = settings_manager.get_last_format_preferences()

        self._mp3_bitrate_var = preferences.get("bitrate", DEFAULT_BITRATE)
        self._opus_bitrate_var = preferences.get("opus_bitrate", DEFAULT_BITRATE)
        self._quality_var = preferences.get("quality", DEFAULT_QUALITY)
        self._format_var = preferences.get("format_var", 1)
        self._playlist_var = 0 if preferences.get("playlist_mode", False) else 1
        self._playlist_start_var = preferences.get("playlist_start", 1)
        self._playlist_end_var = preferences.get("playlist_end", 999)
        self._normalize_var = preferences.get("normalize_volume", False)
        self._normalize_target_var = preferences.get("normalize_target", DEFAULT_NORMALIZE_TARGET)
        self._enrich_var = preferences.get("enrich_metadata", False)
        self._prevent_sleep_var = preferences.get("prevent_sleep", False)
        self._widgets_locked = False

    # ------------------------------------------------------------------
    # Download config builder
    # ------------------------------------------------------------------

    def get_download_config(self) -> DownloadConfig:
        """Create DownloadConfig from current UI state."""
        url_valid, url_error = self._validate_url()
        if not url_valid:
            self._show_url_tooltip(url_error)
            return None

        if not self._validate_download_path():
            self._show_path_tooltip()
            return None

        config = DownloadConfig()
        config.url = self.url_entry.text().strip()
        config.output_directory = self.path_entry.text().strip()
        config.file_format = FILE_FORMATS.get(self.format_group.checkedId(), "mp3")
        config.is_playlist = self.yes_playlist_radio.isChecked()
        config.normalize_volume = self.normalize_check.isChecked()
        config.normalize_target = self._get_normalize_target()
        config.enrich_metadata = self.enrich_check.isChecked()

        # Save the output directory
        if config.output_directory and config.output_directory != 'Choose a path for your file':
            settings_manager.set_last_download_directory(config.output_directory)

        # Save all format preferences
        settings_manager.save_format_preferences(
            format_var=self.format_group.checkedId(),
            bitrate=self._mp3_bitrate_var,
            opus_bitrate=self._opus_bitrate_var,
            quality=self._get_current_quality(),
            playlist_mode=config.is_playlist,
            playlist_start=self.playlist_start_entry.value(),
            playlist_end=self.playlist_end_entry.value(),
            normalize_volume=config.normalize_volume,
            normalize_target=config.normalize_target,
            enrich_metadata=config.enrich_metadata,
            prevent_sleep=self.prevent_sleep_check.isChecked()
        )

        if config.file_format in ("mp3", "opus"):
            raw_bitrate = self.quality_menu.currentData() or "Best"
            config.bitrate = "best" if raw_bitrate == "Best" else raw_bitrate.replace("Max ", "").split("Kbps")[0]
        else:
            raw_quality = self.quality_menu.currentData() or "Best"
            config.quality = "best" if raw_quality == "Best" else raw_quality.replace("Max ", "").split("p")[0]

        if config.is_playlist and hasattr(self, 'playlist_start_entry'):
            try:
                config.playlist_start = self.playlist_start_entry.value()
                config.playlist_end = self.playlist_end_entry.value()
                if config.playlist_end < config.playlist_start:
                    from PySide6.QtWidgets import QMessageBox
                    QMessageBox.warning(
                        self,
                        t("validation.invalid_range_title"),
                        t("validation.invalid_range_msg", end=config.playlist_end, start=config.playlist_start)
                    )
                    return None
            except ValueError:
                config.playlist_start = 1
                config.playlist_end = 9999

        return config

    # ------------------------------------------------------------------
    # Convert button helpers
    # ------------------------------------------------------------------

    def set_convert_button_text(self, text: str):
        """Update convert button text."""
        if hasattr(self, 'convert_button') and self.convert_button is not None:
            self.convert_button.setText(text)

    def set_convert_button_enabled(self, enabled: bool):
        """Enable or disable the convert button."""
        if hasattr(self, 'convert_button') and self.convert_button is not None:
            self.convert_button.setEnabled(enabled)

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self):
        """Show the window (the QApplication event loop is managed externally)."""
        self.show()
