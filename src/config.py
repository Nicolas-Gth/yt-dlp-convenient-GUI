"""
Configuration and constants for the yt-dlp GUI application.
"""
import os

# Application version
APP_VERSION = "3.0.1"

# Application name
APP_NAME = "yt-dlp Convenient GUI"

# Application constants
APP_TITLE = f"{APP_NAME} [v{APP_VERSION}] - Made by Nicolas-Gth"

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
DEFAULT_BITRATES = ["Best", "Max 32Kbps", "Max 96Kbps", "Max 128Kbps", "Max 192Kbps", "Max 256Kbps", "Max 320Kbps"]
DEFAULT_QUALITIES = ["Best", "Max 144p", "Max 360p", "Max 480p", "Max 720p", "Max 1080p", "Max 1440p", "Max 2160p"]
DEFAULT_BITRATE = "Best"
DEFAULT_QUALITY = "Max 720p"
DEFAULT_NORMALIZE_TARGET = -14.0  # LUFS

# File formats
FILE_FORMATS = {
    1: "mp3",
    2: "mp4",
    3: "opus"
}

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ICON_PATH = os.path.join(SCRIPT_DIR, '..', 'assets', 'icon.ico')
DOWNLOAD_ICON_PATH = os.path.join(SCRIPT_DIR, '..', 'assets', 'download-icon.svg')
REFRESH_ICON_PATH = os.path.join(SCRIPT_DIR, '..', 'assets', 'refresh-icon.svg')
COOKIES_PATH = os.path.join(SCRIPT_DIR, '..', 'cookies.txt')
COOKIES_DIR = os.path.dirname(COOKIES_PATH)

# Cookie export instructions (shared across all cookie-related messages)
COOKIES_INSTRUCTIONS = (
    "1. Install the \"Get cookies.txt LOCALLY\" extension in your browser (Chrome / Firefox / Edge).\n\n"
    "2. Open a new private / incognito window and sign in to YouTube.\n\n"
    "3. In the same window and same tab, navigate to: https://www.youtube.com/robots.txt "
    "(this must be the only private/incognito tab open)\n\n"
    "4. Click the extension icon and export your cookies (\"Export as cookies.txt\"), "
    "then close the private window so the session is never reopened in the browser.\n\n"
    f"5. Place the cookies.txt file at the application root: {COOKIES_DIR}{os.sep}\n\n"
    "6. Restart the download.\n\n"
    "YouTube rotates cookies on open browser tabs. "
    "Using a private window ensures exported cookies stay valid."
)

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
            return os.path.dirname(ffmpeg_executable)
