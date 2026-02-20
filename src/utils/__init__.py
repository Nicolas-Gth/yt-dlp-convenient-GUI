"""
Utilities package for yt-dlp Convenient GUI.

This package contains helper functions and utility modules.
"""

from .ui_utils import get_platform_fonts, calculate_window_size
from .image_utils import load_thumbnail, load_icon, crop_album_cover
from .settings import settings_manager
from .metadata_enricher import enrich_metadata, apply_enriched_metadata_mp3, _parse_artist_title_from_video
from .cookies_validator import validate_cookies_file

__all__ = [
    'get_platform_fonts', 
    'calculate_window_size',
    'load_thumbnail', 
    'load_icon', 
    'crop_album_cover',
    'settings_manager',
    'enrich_metadata',
    'apply_enriched_metadata_mp3',
    '_parse_artist_title_from_video'
]
