"""
Configuration and constants for the yt-dlp GUI application.
"""
import os

# Import version from the version module
try:
    from version import __version__
except ImportError:
    # Fallback for when this module is imported from outside the package
    import sys
    from pathlib import Path
    # Add the src directory to path if not already there
    src_dir = Path(__file__).parent
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))
    from version import __version__

# Application constants
APP_TITLE = f"yt-dlp Convenient GUI [v{__version__}] - Made by Nicolas-Gth"
APP_VERSION = __version__

# Default window dimensions
DEFAULT_WINDOW_SIZE = {
    'width': 466,
    'height': 250
}

# Platform-specific size adjustments
PLATFORM_SCALE = {
    'width_base': 480,
    'height_base': 218,
    'height_extended': 385,
    'height_single': 350
}

# Adjust for Linux font differences
if os.name != 'nt':
    PLATFORM_SCALE['width_base'] = 432
    PLATFORM_SCALE['height_base'] = 234
    # PLATFORM_SCALE['height_extended'] = 420
    # PLATFORM_SCALE['height_single'] = 380

# Font settings - Universal fonts that work cross-platform
DEFAULT_FONT = ('Arial', 9)
TITLE_FONT = ('Arial', 10, 'bold')

# Colors
COLORS = {
    'background': "#333333",
    'button_normal': "#238a45",
    'button_active': "#449468",
    'text_primary': 'white',
    'text_secondary': 'white'
}

# Default values
DEFAULT_BITRATES = ["32Kbps", "96Kbps", "128Kbps", "192Kbps", "256Kbps", "320Kbps"]
DEFAULT_QUALITIES = ["144p", "360p", "480p", "720p", "1080p", "1440p", "2160p"]
DEFAULT_BITRATE = "192Kbps"
DEFAULT_QUALITY = "720p"

# File formats
FILE_FORMATS = {
    1: "mp3",
    2: "mp4"
}

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ICON_PATH = os.path.join(SCRIPT_DIR, '..', 'assets', 'icon.ico')

# FFmpeg configuration
def get_ffmpeg_path():
    """Get the appropriate FFmpeg path for the current platform."""
    if os.name == 'nt':  # Windows
        ffmpeg_dir = os.path.join(SCRIPT_DIR, '..', 'ffmpeg', 'bin')
        os.environ["PATH"] += os.pathsep + ffmpeg_dir
        return ffmpeg_dir
    else:  # Linux/Unix
        import shutil
        ffmpeg_executable = shutil.which('ffmpeg')
        if ffmpeg_executable is None:
            print("Warning: ffmpeg not found in system PATH. Please install ffmpeg.")
            print("  Ubuntu/Debian: sudo apt install ffmpeg")
            print("  Fedora: sudo dnf install ffmpeg")
            print("  Arch: sudo pacman -S ffmpeg")
            return None
        else:
            print(f"Found ffmpeg at: {ffmpeg_executable}")
            return os.path.dirname(ffmpeg_executable)
