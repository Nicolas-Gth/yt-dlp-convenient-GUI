"""
Utilities package for yt-dlp Convenient GUI.

This package contains helper functions and utility modules.
"""

from .ui_utils import get_platform_fonts, calculate_window_size
from .image_utils import load_thumbnail, load_icon, crop_album_cover
from .settings_utils import settings_manager
from .metadata_enricher_utils import enrich_metadata, apply_enriched_metadata_mp3, apply_enriched_metadata_opus, _parse_artist_title_from_video
from .cookies_validator_utils import validate_cookies_file
from .sleep_inhibitor_utils import sleep_inhibitor
from .playlist_utils import (
    normalize_playlist_url, extract_playlist_id,
    compute_playlist_offset, get_youtube_visible_ids,
)

__all__ = [
    'get_platform_fonts', 
    'calculate_window_size',
    'load_thumbnail', 
    'load_icon', 
    'crop_album_cover',
    'settings_manager',
    'sleep_inhibitor',
    'enrich_metadata',
    'apply_enriched_metadata_mp3',
    'apply_enriched_metadata_opus',
    '_parse_artist_title_from_video'
]
