"""
Main entry point for the yt-dlp Convenient GUI application.

This application provides a user-friendly graphical interface for downloading
videos and audio from YouTube using yt-dlp.

Architecture:
- main.py: Entry point
- config.py: Configuration and constants
- models/: Data models and structures
- views/: GUI components and layouts
- controllers/: Business logic and coordination
- utils/: Utility functions and helpers

Author: Nicolas-Gth
"""

import sys
import os

# Add the src directory to the Python path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from version import __version__
from controllers import ApplicationController

def main():
    """Main entry point for the application."""
    app = ApplicationController()
    app.run()

if __name__ == "__main__":
    main()
