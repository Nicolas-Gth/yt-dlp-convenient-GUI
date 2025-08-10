"""
yt-dlp Convenient GUI - Source package.

A user-friendly graphical interface for downloading videos and audio from YouTube
using yt-dlp with advanced features and native desktop integration.

Architecture:
- main.py: Application entry point
- config.py: Configuration and constants
- models/: Data structures and models
- views/: User interface components
- controllers/: Business logic and application control
- utils/: Helper functions and utilities
"""

__author__ = "Nicolas-Gth"
__description__ = "A convenient GUI for yt-dlp with native desktop integration"

# Main application entry point
from .main import main

__all__ = ['main']
