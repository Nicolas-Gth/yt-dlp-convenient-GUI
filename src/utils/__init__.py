"""
Utilities package for yt-dlp Convenient GUI.

This package contains helper functions and utility modules.

Heavy third-party imports (Pillow, mutagen, …) are loaded lazily so that
the startup dialog can run before those packages are installed.
"""

# Lightweight — no third-party deps
from .ui_utils import get_platform_fonts, calculate_window_size
from .settings_utils import settings_manager
from .i18n_utils import t, init as i18n_init, set_language, get_language, AVAILABLE_LANGUAGES
from .cookies_validator_utils import validate_cookies_file
from .sleep_inhibitor_utils import sleep_inhibitor
from .playlist_utils import (
    normalize_playlist_url, extract_playlist_id,
    compute_playlist_offset, get_youtube_visible_ids,
)

# Lazy-loaded symbols that depend on Pillow / mutagen / yt-dlp
_LAZY_IMPORTS = {
    'load_thumbnail':                   ('.image_utils', 'load_thumbnail'),
    'load_icon':                        ('.image_utils', 'load_icon'),
    'crop_album_cover':                 ('.image_utils', 'crop_album_cover'),
    'enrich_metadata':                  ('.metadata_enricher_utils', 'enrich_metadata'),
    'apply_enriched_metadata_mp3':      ('.metadata_enricher_utils', 'apply_enriched_metadata_mp3'),
    'apply_enriched_metadata_opus':     ('.metadata_enricher_utils', 'apply_enriched_metadata_opus'),
    '_parse_artist_title_from_video':   ('.metadata_enricher_utils', '_parse_artist_title_from_video'),
}


def __getattr__(name):
    if name in _LAZY_IMPORTS:
        module_path, attr = _LAZY_IMPORTS[name]
        import importlib
        module = importlib.import_module(module_path, __package__)
        value = getattr(module, attr)
        # Cache on the package so __getattr__ is not called again
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
