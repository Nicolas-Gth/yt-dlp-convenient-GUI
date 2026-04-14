"""
Font and UI utilities for cross-platform compatibility.
"""
from config import DEFAULT_FONT, TITLE_FONT, PLATFORM_SCALE

def get_platform_fonts():
    """Get appropriate fonts for the current platform."""
    return {
        'default': DEFAULT_FONT,
        'title': TITLE_FONT
    }

def calculate_window_size(base_width=None, base_height=None, extra_height=0):
    """
    Calculate appropriate window size based on platform.
    """
    if base_width is None:
        base_width = PLATFORM_SCALE['width_base']
    if base_height is None:
        base_height = PLATFORM_SCALE['height_base']

    return base_width, base_height + extra_height
