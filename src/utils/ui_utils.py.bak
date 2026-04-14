"""
Font and UI utilities for cross-platform compatibility.
"""
import os
import tkinter.font as tkFont
from config import DEFAULT_FONT, TITLE_FONT, PLATFORM_SCALE

def get_platform_fonts():
    """Get appropriate fonts for the current platform."""
    return {
        'default': DEFAULT_FONT,
        'title': TITLE_FONT
    }

def calculate_window_size(base_width=None, base_height=None, extra_height=0):
    """
    Calculate appropriate window size based on font metrics and platform.
    """
    if base_width is None:
        base_width = PLATFORM_SCALE['width_base']
    if base_height is None:
        base_height = PLATFORM_SCALE['height_base']
    
    try:
        # Get platform fonts
        fonts = get_platform_fonts()
        
        # Try advanced font-based scaling
        test_font = tkFont.Font(family=fonts['default'][0], size=fonts['default'][1])
        char_width = test_font.measure('M')
        char_height = test_font.metrics('linespace')
        
        # Base scaling factors (Windows reference)
        reference_char_width = 8
        reference_char_height = 13
        
        width_scale = max(char_width / reference_char_width, 0.8)  # Minimum scale
        height_scale = max(char_height / reference_char_height, 0.8)
        
        # Calculate new dimensions
        new_width = max(int(base_width * width_scale), base_width)
        new_height = max(int((base_height + extra_height) * height_scale), base_height + extra_height)
        
    except Exception:
        # Fallback to platform constants if font scaling fails
        new_width = base_width
        new_height = base_height + extra_height
    
    return new_width, new_height
