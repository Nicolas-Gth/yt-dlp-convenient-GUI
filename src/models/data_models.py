"""
Data models for the yt-dlp GUI application.
"""
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import datetime

@dataclass
class VideoInfo:
    """Represents information about a single video."""
    title: str = "Unknown"
    uploader: str = "Unknown"
    duration: int = 0
    thumbnail: str = ""
    categories: List[str] = None
    album: str = ""
    raw_uploader: str = ""  # Original uploader name before cleaning
    
    def __post_init__(self):
        if self.categories is None:
            self.categories = []
    
    @property
    def duration_formatted(self) -> str:
        """Return formatted duration string."""
        return str(datetime.timedelta(seconds=int(self.duration)))
    
    @property
    def is_music(self) -> bool:
        """Check if the video is categorized as music."""
        # Check categories
        if 'Music' in self.categories:
            return True
        # YouTube Music auto-generated channels end with ' - Topic'
        uploader_to_check = self.raw_uploader or self.uploader
        if uploader_to_check and uploader_to_check.endswith(' - Topic'):
            return True
        # Has an album field => it's a music track
        if self.album:
            return True
        return False

@dataclass
class PlaylistInfo:
    """Represents information about a playlist."""
    title: str = "Unknown Playlist"
    entries: List[VideoInfo] = None
    
    def __post_init__(self):
        if self.entries is None:
            self.entries = []
    
    @property
    def length(self) -> int:
        """Return the number of videos in the playlist."""
        return len(self.entries)

@dataclass
class DownloadConfig:
    """Configuration for download operations."""
    url: str = ""
    output_directory: str = ""
    file_format: str = "mp3"  # mp3 or mp4
    bitrate: str = "192"  # for mp3
    quality: str = "720"  # for mp4
    is_playlist: bool = False
    playlist_start: int = 1
    playlist_end: int = 1
    verbose: bool = False
    normalize_volume: bool = False
    normalize_target: float = -14.0  # Target loudness in LUFS
    enrich_metadata: bool = False  # Fetch HD album cover + lyrics from MusicBrainz/LRCLIB
    output_template: str = ""  # User-defined filename template (e.g. "{artist} - {title}.{format}")

    @property
    def ydl_output_template(self) -> str:
        """Generate the output template for yt-dlp."""
        return f"{self.output_directory}/%(title)s.%(ext)s"

class DownloadProgress:
    """Manages download progress state."""
    
    def __init__(self):
        self.current_song = 0
        self.previous_song = -1
        self.current_percentage = 0.0
        self.total_percentage = 0.0
        self.status = "idle"  # idle, downloading, processing, finished, error
        
    def update_current_song(self, song_index: int):
        """Update the current song index."""
        self.previous_song = self.current_song
        self.current_song = song_index
        
    def reset(self):
        """Reset progress to initial state."""
        self.current_song = 0
        self.previous_song = -1
        self.current_percentage = 0.0
        self.total_percentage = 0.0
        self.status = "idle"
