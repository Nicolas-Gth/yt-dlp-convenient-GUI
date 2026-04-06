"""
Window management mixin for the main application view.

Handles window initialisation, display scaling detection (HiDPI),
font/style configuration, and dynamic window resizing.
"""
import os
import tkinter.ttk as ttk
from ttkthemes import ThemedTk

from config import APP_TITLE, COLORS, ICON_PATH, PLATFORM_SCALE
from utils import get_platform_fonts, load_icon


class WindowMixin:
    """Mixin that provides window setup, styling, and sizing methods."""

    # ------------------------------------------------------------------
    # Window setup
    # ------------------------------------------------------------------

    def setup_window(self):
        """Initialize the main window."""
        self.root = ThemedTk(theme="equilux")

        # Detect and apply display scaling for HiDPI screens
        self._dpi_scale = self._detect_display_scale()
        if self._dpi_scale > 1.0:
            self.root.tk.call('tk', 'scaling', self._dpi_scale * (96.0 / 72.0))

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
    # Display scaling
    # ------------------------------------------------------------------

    def _detect_display_scale(self):
        """Detect the display scaling factor for HiDPI screens."""
        # Environment variables set by desktop environments (most reliable)
        for env_var in ('GDK_SCALE', 'QT_SCALE_FACTOR'):
            value = os.environ.get(env_var)
            if value:
                try:
                    factor = float(value)
                    if factor >= 1.0:
                        return factor
                except (ValueError, TypeError):
                    pass

        # Compute from screen physical size vs pixel resolution
        try:
            width_mm = self.root.winfo_screenmmwidth()
            if width_mm > 0:
                dpi = self.root.winfo_screenwidth() / (width_mm / 25.4)
                factor = dpi / 96.0
                if factor >= 1.25:
                    return round(factor * 4) / 4  # Round to nearest 0.25
        except Exception:
            pass

        return 1.0

    # ------------------------------------------------------------------
    # Window sizing
    # ------------------------------------------------------------------

    def adjust_window_size(self, extra_height: int = 0):
        """Adjust window size to fit content automatically."""
        self.root.update_idletasks()
        req_width = self.root.winfo_reqwidth()
        req_height = self.root.winfo_reqheight() + extra_height
        # Clamp width between minimum and maximum, scaled for HiDPI
        scale = getattr(self, '_dpi_scale', 1.0)
        min_width = int(PLATFORM_SCALE['width_base'] * scale)
        max_width = int(560 * scale)
        width = max(req_width, min_width)
        width = min(width, max_width)
        # Force size via minsize/maxsize instead of geometry() to avoid
        # WM repositioning the window on every resize (KDE/Wayland bug).
        self.root.minsize(width, req_height)
        self.root.maxsize(width, req_height)
