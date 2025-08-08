#!/usr/bin/env python3
"""
Launcher script for yt-dlp Convenient GUI
"""
import sys
import os

# Get the directory where this script is located
script_dir = os.path.dirname(os.path.abspath(__file__))

# Add src directory to Python path
src_dir = os.path.join(script_dir, 'src')
sys.path.insert(0, src_dir)

# Import and run the application
try:
    from main import main
    main()
except ImportError as e:
    print(f"Error importing application modules: {e}")
    print("Make sure all dependencies are installed:")
    print("pip install yt-dlp Pillow ttkthemes plyer mutagen")
    sys.exit(1)
except Exception as e:
    print(f"Error running application: {e}")
    sys.exit(1)
