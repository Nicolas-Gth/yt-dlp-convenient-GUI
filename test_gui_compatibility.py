#!/usr/bin/env python3
"""
Test script for GUI font and layout compatibility
This script shows font metrics and window sizing information
"""

import tkinter as tk
import tkinter.font as tkFont
import os

def test_font_metrics():
    """Test font metrics across platforms"""
    root = tk.Tk()
    root.withdraw()  # Hide the window
    
    # Test different fonts
    fonts_to_test = []
    
    if os.name == 'nt':  # Windows
        fonts_to_test = [
            ('Segoe UI', 9),
            ('Arial', 9),
            ('MS Sans Serif', 8)
        ]
    else:  # Linux
        fonts_to_test = [
            ('Liberation Sans', 9),
            ('DejaVu Sans', 9),
            ('Arial', 9),
            ('sans-serif', 9)
        ]
    
    print("Font Metrics Test")
    print("=" * 50)
    print(f"Platform: {'Windows' if os.name == 'nt' else 'Linux/Unix'}")
    print()
    
    for font_name, size in fonts_to_test:
        try:
            font = tkFont.Font(family=font_name, size=size)
            char_width = font.measure('M')
            char_height = font.metrics('linespace')
            ascent = font.metrics('ascent')
            descent = font.metrics('descent')
            
            print(f"Font: {font_name} {size}pt")
            print(f"  Character 'M' width: {char_width}px")
            print(f"  Line height: {char_height}px")
            print(f"  Ascent: {ascent}px, Descent: {descent}px")
            print(f"  Text sample: '{font.measure('Hello World!')}px'")
            print()
            
        except tk.TclError as e:
            print(f"Font {font_name} not available: {e}")
            print()
    
    root.destroy()

def test_window_scaling():
    """Test window scaling calculations"""
    print("Window Scaling Test")
    print("=" * 50)
    
    # Reference values (Windows)
    ref_width, ref_height = 466, 250
    ref_char_width, ref_char_height = 8, 13
    
    print(f"Reference dimensions: {ref_width}x{ref_height}")
    print(f"Reference character metrics: {ref_char_width}x{ref_char_height}")
    print()
    
    # Platform-specific adjustments
    if os.name != 'nt':
        adjusted_width = 500
        adjusted_height = 270
        print(f"Linux adjusted dimensions: {adjusted_width}x{adjusted_height}")
        print(f"Width increase: +{adjusted_width - ref_width}px ({((adjusted_width/ref_width)-1)*100:.1f}%)")
        print(f"Height increase: +{adjusted_height - ref_height}px ({((adjusted_height/ref_height)-1)*100:.1f}%)")
    else:
        print("Windows: Using reference dimensions")
    
    print()

def main():
    """Run all tests"""
    print("yt-dlp GUI Cross-Platform Compatibility Test")
    print("=" * 60)
    print()
    
    test_font_metrics()
    test_window_scaling()
    
    print("Test completed!")
    print()
    print("If you see font issues in the GUI:")
    print("1. The window size will auto-adjust")
    print("2. Window is now resizable")
    print("3. Platform-specific fonts are configured")

if __name__ == "__main__":
    main()
