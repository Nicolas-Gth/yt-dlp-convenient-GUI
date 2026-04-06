"""
Window management mixin for the main application view.

Handles window initialisation, font/style configuration,
and dynamic window resizing.
"""
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
    # Window sizing
    # ------------------------------------------------------------------

    def adjust_window_size(self, extra_height: int = 0):
        """Adjust window size to fit content automatically."""
        self.root.update_idletasks()
        req_width = self.root.winfo_reqwidth()
        req_height = self.root.winfo_reqheight() + extra_height
        # Ensure at least the base width, but never shrink below content
        width = max(req_width, PLATFORM_SCALE['width_base'])
        # Force size via minsize/maxsize instead of geometry() to avoid
        # WM repositioning the window on every resize (KDE/Wayland bug).
        self.root.minsize(width, req_height)
        self.root.maxsize(width, req_height)
