"""
Main application view — orchestrator that composes all view mixins.

The heavy lifting is split across:
    - window_view.py    : window setup, styling & sizing (WindowMixin)
    - widgets_view.py   : widget creation (WidgetsMixin)
    - progress_view.py  : download progress UI (ProgressMixin)
    - event_handlers_view.py : callbacks & validation (EventHandlersMixin)
"""
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QMessageBox
from PySide6.QtCore import Qt

from config import DEFAULT_BITRATE, DEFAULT_QUALITY, DEFAULT_NORMALIZE_TARGET, FILE_FORMATS
from utils import settings_manager
from utils.i18n_utils import t
from models import DownloadConfig

from .window_view import WindowMixin
from .download_tab import DownloadTabMixin
from .progress_tab import ProgressMixin
from .event_handlers_view import EventHandlersMixin
from .refresh_view import RefreshMixin
from .files_tab import FilesMixin


class MainApplicationView(QMainWindow, WindowMixin, DownloadTabMixin, ProgressMixin, EventHandlersMixin, RefreshMixin, FilesMixin):
    """Main application window and GUI components."""

    def __init__(self):
        super().__init__()

        # Tab widget
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Tab 0: Download
        self._download_tab = QWidget()
        self.main_layout = QVBoxLayout(self._download_tab)
        self.main_layout.setContentsMargins(8, 8, 8, 8)
        self.main_layout.setSpacing(8)

        # Left panel — download settings
        self.input_container = QWidget()
        self.input_layout = QVBoxLayout(self.input_container)
        self.input_layout.setContentsMargins(0, 0, 0, 0)
        self.input_layout.setSpacing(8)

        # Right panel — progress / download status (hidden until a download starts)
        self.progress_container = QWidget()
        self.progress_container.setMinimumWidth(250)
        self.progress_container.hide()
        self.progress_container_layout = QVBoxLayout(self.progress_container)
        self.progress_container_layout.setContentsMargins(0, 0, 0, 0)
        self.progress_container_layout.setSpacing(8)

        # Horizontal layout: settings left | progress right
        self._top_layout = QHBoxLayout()
        self._top_layout.setSpacing(8)
        self._top_layout.addWidget(self.input_container, 1)
        self._top_layout.addWidget(self.progress_container, 1)
        self.main_layout.addLayout(self._top_layout)

        # Bottom panel — downloaded / skipped tables (initially hidden, stretches to fill)
        self.tables_container = QWidget()
        self.tables_layout = QVBoxLayout(self.tables_container)
        self.tables_layout.setContentsMargins(0, 0, 0, 0)
        self.tables_layout.setSpacing(0)
        self.tables_container.hide()
        self.main_layout.addWidget(self.tables_container, 1)

        self.setup_window()
        self.setup_fonts()
        self.setup_variables()
        self.setup_widgets()
        self.progress_widgets = {}

        # Add tabs
        self.tabs.addTab(self._download_tab, t("tabs.download"))
        self.setup_files_tab()

        # Callbacks (set by controller)
        self.on_browse_callback = None
        self.on_convert_callback = None
        self.on_format_change_callback = None
        self.on_playlist_change_callback = None
        self.on_stop_callback = None
        self.on_theme_change_callback = None
        self.on_language_change_callback = None

        self._restore_window_geometry()

    def closeEvent(self, event):
        """Save window geometry before closing."""
        if not self.isMaximized() and not self.isMinimized() and not self.isFullScreen():
            geo = self.geometry()
            settings_manager.set_setting("window_geometry",
                (geo.x(), geo.y(), geo.width(), geo.height()))
        super().closeEvent(event)

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
        self._output_template_var = preferences.get("output_template", "")
        self._widgets_locked = False

        # Menu settings state
        settings = settings_manager.load_settings()
        if hasattr(self, '_prevent_sleep_check'):
            self._prevent_sleep_check.blockSignals(True)
            self._prevent_sleep_check.setChecked(settings.get("prevent_sleep", False))
            self._prevent_sleep_check.blockSignals(False)
        if hasattr(self, '_experimental_check'):
            self._experimental_check.blockSignals(True)
            self._experimental_check.setChecked(settings.get("use_experimental_branch", False))
            self._experimental_check.blockSignals(False)
        if hasattr(self, '_update_window_title'):
            self._update_window_title(experimental=settings.get("use_experimental_branch", False))

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
        config.output_template = self.template_entry.text().strip() if hasattr(self, 'template_entry') else ""

        # Validate template before proceeding
        if config.output_template:
            invalid_vars = self._get_invalid_template_vars(config.output_template)
            if invalid_vars:
                QMessageBox.warning(
                    self,
                    t("validation.invalid_template_title"),
                    t("format.template_invalid_vars", vars=', '.join(invalid_vars))
                )
                return None

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
            output_template=config.output_template
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
