#!/usr/bin/env python3
"""
Test script for yt-dlp Convenient GUI
This script tests the basic functionality without running the full GUI
"""

import sys
import os
sys.path.append('/home/nicolas/Code/yt-dlp-convenient-GUI/src')

def test_imports():
    """Test if all required modules can be imported"""
    try:
        import tkinter
        from tkinter import filedialog
        import tkinter.ttk as ttk
        from ttkthemes import ThemedTk
        from PIL import Image, ImageTk
        import urllib.request
        import yt_dlp
        import datetime
        import threading
        from plyer import notification
        import os
        from mutagen.id3 import ID3, APIC
        from mutagen.mp3 import MP3
        from mutagen.easyid3 import EasyID3
        import io
        import re
        print("✓ All imports successful")
        return True
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False

def test_yt_dlp():
    """Test basic yt-dlp functionality"""
    try:
        import yt_dlp
        # Test with a simple video URL extraction (no download)
        test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Rick Roll for testing
        ydl_opts = {
            'quiet': True,
            'simulate': True,
            'ignoreerrors': True
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(test_url, download=False)
            if info:
                print("✓ yt-dlp extraction test successful")
                print(f"  Title: {info.get('title', 'Unknown')}")
                return True
            else:
                print("✗ yt-dlp extraction returned None")
                return False
    except Exception as e:
        print(f"✗ yt-dlp test failed: {e}")
        return False

def main():
    print("Testing yt-dlp Convenient GUI dependencies...")
    print("-" * 50)
    
    # Test imports
    if not test_imports():
        print("Some imports failed. Please install missing dependencies.")
        return False
    
    # Test yt-dlp functionality
    print("\nTesting yt-dlp functionality...")
    if not test_yt_dlp():
        print("yt-dlp test failed. Please check your internet connection.")
        return False
    
    print("\n✓ All tests passed! The application should work correctly.")
    return True

if __name__ == "__main__":
    main()
