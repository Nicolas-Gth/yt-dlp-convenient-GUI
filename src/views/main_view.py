"""
Main application view — orchestrator that composes all view mixins.

The heavy lifting is split across:
    - widgets.py        : widget creation (WidgetsMixin)
    - progress_view.py  : download progress UI (ProgressMixin)
    - event_handlers.py : callbacks & validation (EventHandlersMixin)
"""
import tkinter as tk
from tkinter import StringVar, IntVar, DoubleVar, BooleanVar
import tkinter.ttk as ttk
from ttkthemes import ThemedTk

from config import (
    APP_TITLE, COLORS, DEFAULT_BITRATE, DEFAULT_QUALITY, ICON_PATH,
    DEFAULT_NORMALIZE_TARGET, PLATFORM_SCALE
)
from utils import get_platform_fonts, load_icon, settings_manager
from models import DownloadConfig

from .widgets import WidgetsMixin
from .progress_view import ProgressMixin
from .event_handlers import EventHandlersMixin


class MainApplicationView(WidgetsMixin, ProgressMixin, EventHandlersMixin):
    """Main application window and GUI components."""

    def __init__(self):
        self.root = None
        self.setup_window()
        self.setup_fonts()
        self.setup_variables()
        self.setup_widgets()       # provided by WidgetsMixin
        self.progress_widgets = {}

        # Callbacks (set by controller)
        self.on_browse_callback = None
        self.on_convert_callback = None
        self.on_format_change_callback = None
        self.on_playlist_change_callback = None
        self.on_stop_callback = None

    # ------------------------------------------------------------------
    # Window setup
    # ------------------------------------------------------------------

    def setup_window(self):
        """Initialize the main window."""
        self.root = ThemedTk(theme="equilux")
        self.root.title(APP_TITLE)
        self.root.configure(bg=COLORS['background'])
        self.root.resizable(False, False)

        # Allow column 0 to expand so centered widgets work
        self.root.columnconfigure(0, weight=1)

        # Set default background for all tk widgets
        self.root.option_add('*Background', COLORS['background'])
        self.root.option_add('*Foreground', COLORS['text_primary'])

        # Set application icon
        load_icon(ICON_PATH, self.root)

    # ------------------------------------------------------------------
    # Fonts & styles
    # ------------------------------------------------------------------

    def setup_fonts(self):
        """Configure fonts and styles."""
        self.fonts = get_platform_fonts()

        # Apply the default font
        self.root.option_add('*Font', self.fonts['default'])

        # Configure ttk styles
        self.style = ttk.Style()

        # Configure colors for all ttk widgets to match our theme
        self.style.configure('TLabel',
                           font=self.fonts['default'],
                           background=COLORS['background'],
                           foreground=COLORS['text_primary'])

        self.style.configure('TButton',
                           font=self.fonts['default'],
                           background=COLORS['background'],
                           foreground=COLORS['text_primary'])

        self.style.configure('TEntry',
                           font=self.fonts['default'],
                           background=COLORS['background'],
                           foreground=COLORS['text_primary'])

        self.style.configure('TCombobox',
                           font=self.fonts['default'],
                           background=COLORS['background'],
                           foreground=COLORS['text_primary'])

        self.style.configure('TRadiobutton',
                           font=self.fonts['default'],
                           background=COLORS['background'],
                           foreground=COLORS['text_primary'])

        self.style.configure('TCheckbutton',
                           font=self.fonts['default'],
                           background=COLORS['background'],
                           foreground=COLORS['text_primary'])

        self.style.configure('TMenubutton',
                           background=COLORS['background'],
                           foreground=COLORS['text_primary'])

        self.style.configure('TSpinbox',
                           background=COLORS['background'],
                           fieldbackground=COLORS['background'],
                           foreground=COLORS['text_primary'])

        self.style.configure('TFrame',
                           background=COLORS['background'])

        self.style.configure('TLabelframe',
                           background=COLORS['background'])

        # Configure scrollbar
        self.style.configure('Vertical.TScrollbar',
                           background=COLORS['background'],
                           troughcolor=COLORS['background'],
                           bordercolor=COLORS['background'],
                           arrowcolor=COLORS['text_primary'])

        # Configure progress bar
        self.style.configure('TProgressbar',
                           background=COLORS['button_normal'],
                           troughcolor=COLORS['background'])

    # ------------------------------------------------------------------
    # Tk variables
    # ------------------------------------------------------------------

    def setup_variables(self):
        """Initialize tkinter variables."""
        self.folder_path = StringVar()
        self.url_var = StringVar()
        self.bitrate_var = StringVar()
        self.quality_var = StringVar()
        self.format_var = IntVar()
        self.playlist_var = IntVar()

        # Load saved preferences
        preferences = settings_manager.get_last_format_preferences()

        # Set values from preferences
        self.bitrate_var.set(preferences.get("bitrate", DEFAULT_BITRATE))
        self.quality_var.set(preferences.get("quality", DEFAULT_QUALITY))
        self.format_var.set(preferences.get("format_var", 1))  # MP3 by default
        # For playlist_var: 0 = Yes, 1 = No (inverted logic)
        self.playlist_var.set(0 if preferences.get("playlist_mode", False) else 1)

        # Normalize volume variables
        self.normalize_var = BooleanVar(value=preferences.get("normalize_volume", False))
        self.normalize_target_var = DoubleVar(value=preferences.get("normalize_target", DEFAULT_NORMALIZE_TARGET))

        # Enrich metadata variable
        self.enrich_var = BooleanVar(value=preferences.get("enrich_metadata", False))

    # ------------------------------------------------------------------
    # Window sizing
    # ------------------------------------------------------------------

    def adjust_window_size(self, extra_height: int = 0):
        """Adjust window size to fit content automatically."""
        self.root.update_idletasks()
        req_width = self.root.winfo_reqwidth()
        req_height = self.root.winfo_reqheight() + extra_height
        # Clamp width between minimum and maximum
        width = max(req_width, PLATFORM_SCALE['width_base'])
        width = min(width, 560)  # Never wider than 560px
        # Force size via minsize/maxsize instead of geometry() to avoid
        # WM repositioning the window on every resize (KDE/Wayland bug).
        self.root.minsize(width, req_height)
        self.root.maxsize(width, req_height)

    # ------------------------------------------------------------------
    # Download config builder
    # ------------------------------------------------------------------

    def get_download_config(self) -> DownloadConfig:
        """Create DownloadConfig from current UI state."""
        # Validate URL first
        url_valid, url_error = self._validate_url()
        if not url_valid:
            self._show_url_tooltip(url_error)
            return None

        # Validate download path
        if not self._validate_download_path():
            self._show_path_tooltip()
            return None

        config = DownloadConfig()
        config.url = self.url_var.get().strip()
        config.output_directory = self.folder_path.get()
        config.file_format = "mp3" if self.format_var.get() == 1 else "mp4"
        config.is_playlist = self.playlist_var.get() == 0
        config.normalize_volume = self.normalize_var.get()
        config.normalize_target = self._get_normalize_target()
        config.enrich_metadata = self.enrich_var.get()

        # Save the output directory as the last used directory
        if config.output_directory and config.output_directory != 'Choose a path for your file':
            settings_manager.set_last_download_directory(config.output_directory)

        # Save all format preferences
        settings_manager.save_format_preferences(
            format_var=self.format_var.get(),
            bitrate=self.bitrate_var.get(),
            quality=self.quality_var.get(),
            playlist_mode=config.is_playlist,
            normalize_volume=config.normalize_volume,
            normalize_target=config.normalize_target,
            enrich_metadata=config.enrich_metadata
        )

        if config.file_format == "mp3":
            raw_bitrate = self.bitrate_var.get()
            config.bitrate = "best" if raw_bitrate == "Best" else raw_bitrate.split("Kbps")[0]
        else:
            raw_quality = self.quality_var.get()
            config.quality = "best" if raw_quality == "Best" else raw_quality.split("p")[0]

        if config.is_playlist and hasattr(self, 'playlist_start_entry'):
            try:
                start_val = self.playlist_start_entry.get().strip()
                end_val = self.playlist_end_entry.get().strip()
                config.playlist_start = int(start_val) if start_val else 1
                config.playlist_end = int(end_val) if end_val else 9999
                if config.playlist_end < config.playlist_start:
                    import tkinter.messagebox as messagebox
                    messagebox.showwarning(
                        "Invalid range",
                        f"The end value ({config.playlist_end}) cannot be less than the start value ({config.playlist_start})."
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
        if hasattr(self, 'convert_button') and self.convert_button.winfo_exists():
            self.convert_button.configure(text=text)

    def set_convert_button_enabled(self, enabled: bool):
        """Enable or disable the convert button."""
        if hasattr(self, 'convert_button') and self.convert_button.winfo_exists():
            if enabled:
                self.convert_button.configure(
                    state='normal',
                    bg=COLORS['button_normal'],
                    cursor="hand2"
                )
            else:
                self.convert_button.configure(
                    state='disabled',
                    bg=COLORS['background'],
                    cursor="arrow"
                )

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self):
        """Start the main event loop."""
        self.root.mainloop()
