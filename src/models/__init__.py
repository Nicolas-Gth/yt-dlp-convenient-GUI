"""
Data models package for yt-dlp Convenient GUI.

This package contains all data structures and models used throughout the application.
"""

from .data_models import DownloadConfig, VideoInfo, PlaylistInfo, DownloadProgress

__all__ = ['DownloadConfig', 'VideoInfo', 'PlaylistInfo', 'DownloadProgress']
