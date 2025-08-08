"""
Download controller handling yt-dlp operations and metadata processing.
"""
import os
import re
import io
import threading
import warnings
from typing import Optional, Dict, Any, Callable
import yt_dlp
from config import (ICON_PATH)

# Suppress plyer dbus warnings
warnings.filterwarnings("ignore", message="The Python dbus package is not installed")

try:
    from plyer import notification
    NOTIFICATIONS_AVAILABLE = True
except ImportError:
    NOTIFICATIONS_AVAILABLE = False
    
from mutagen.id3 import ID3, APIC
from mutagen.mp3 import MP3
from mutagen.easyid3 import EasyID3

from models import DownloadConfig, VideoInfo, PlaylistInfo, DownloadProgress
from utils import crop_album_cover
from config import get_ffmpeg_path, FILE_FORMATS


class CustomPostProcessor(yt_dlp.postprocessor.PostProcessor):
    """Custom post-processor for handling metadata and file organization."""
    
    def __init__(self, download_config: DownloadConfig):
        super().__init__()
        self.config = download_config
    
    def run(self, video_infos):
        """Process downloaded file: add metadata, rename, and set album cover."""
        file_format = self.config.file_format
        file_path = f"{self.config.output_directory}/{video_infos['title']}.{file_format}"

        # Check if the file actually exists
        if not os.path.exists(file_path):
            print(f"Warning: File {file_path} not found. Conversion may have failed.")
            return [], video_infos

        # Add metadata to the file
        try:
            artist_name = video_infos.get('artists', [video_infos.get('uploader', '').replace(" - Topic", "")])[0]
        except (KeyError, IndexError):
            artist_name = video_infos.get('uploader', '').replace(" - Topic", "")
        
        if file_format == "mp3":
            self._add_mp3_metadata(file_path, video_infos, artist_name)
        
        # Rename and sanitize the file name
        new_file_path = self._sanitize_and_rename_file(file_path, video_infos, artist_name, file_format)
        
        # Add album cover for MP3 files
        if file_format == "mp3" and os.path.exists(new_file_path):
            self._add_album_cover(new_file_path, video_infos)

        return [], video_infos
    
    def _add_mp3_metadata(self, file_path: str, video_infos: Dict, artist_name: str):
        """Add metadata to MP3 file."""
        try:
            metadatas = MP3(file_path, ID3=EasyID3)
            metadatas['artist'] = artist_name
            
            album_name = video_infos.get('album')
            if album_name:
                metadatas['album'] = album_name
            
            metadatas.save()
        except Exception as e:
            print(f"Warning: Could not add metadata to MP3 file: {e}")
    
    def _sanitize_and_rename_file(self, file_path: str, video_infos: Dict, artist_name: str, file_format: str) -> str:
        """Sanitize filename and rename the file."""
        title = video_infos.get('title', '')
        sanitized_artist = re.sub(r'[!?:#%&{}<>|*/$@]', '', artist_name)
        sanitized_title = re.sub(r'[!?:#%&{}<>|*/$@]', '', title)
        
        new_file_path = f"{self.config.output_directory}/{sanitized_artist} - {sanitized_title}.{file_format}"
        
        try:
            os.rename(file_path, new_file_path)
            return new_file_path
        except Exception as e:
            print(f"Warning: Could not rename file: {e}")
            return file_path
    
    def _add_album_cover(self, file_path: str, video_infos: Dict):
        """Add album cover to MP3 file."""
        thumbnail_url = video_infos.get('thumbnail', '')
        if not thumbnail_url:
            return
        
        try:
            album_cover_data = crop_album_cover(thumbnail_url)
            if album_cover_data:
                audio = ID3(file_path)
                audio['APIC'] = APIC(
                    encoding=0,
                    mime='image/jpeg',
                    type=3,
                    desc=u'Cover',
                    data=album_cover_data
                )
                audio.save()
        except Exception as e:
            print(f"Warning: Could not add album cover to MP3: {e}")


class DownloadController:
    """Main controller for download operations."""
    
    def __init__(self):
        self.progress = DownloadProgress()
        self.ffmpeg_path = get_ffmpeg_path()
        self.progress_callback: Optional[Callable] = None
        self.completion_callback: Optional[Callable] = None
        self.video_infos: Optional[Dict] = None
        
    def set_progress_callback(self, callback: Callable):
        """Set the callback function for progress updates."""
        self.progress_callback = callback
    
    def set_completion_callback(self, callback: Callable):
        """Set the callback function for download completion."""
        self.completion_callback = callback
    
    def fetch_video_info(self, config: DownloadConfig) -> Optional[Dict]:
        """Fetch video information without downloading."""
        ydl_opts = {
            'verbose': config.verbose,
            'quiet': True,
            'ignoreerrors': True,
            'extractor_args': {'youtubetab': {'skip': ['authcheck']}},
            'external_downloader_args': ['-loglevel', 'panic'],
            'simulate': True,
            'cachedir': False,
            'noplaylist': not config.is_playlist,
            'playliststart': config.playlist_start,
            'playlistend': config.playlist_end
        }
        
        try:
            self.video_infos = yt_dlp.YoutubeDL(ydl_opts).extract_info(config.url, download=False)
            return self.video_infos
        except yt_dlp.utils.DownloadError as error:
            print(f"Error fetching video info: {error}")
            return self._retry_fetch_info(config, ydl_opts)
    
    def _retry_fetch_info(self, config: DownloadConfig, ydl_opts: Dict) -> Optional[Dict]:
        """Retry fetching video info on error."""
        while True:
            print("There was a problem during the fetching, automatically restarting!")
            try:
                self.video_infos = yt_dlp.YoutubeDL(ydl_opts).extract_info(config.url, download=False)
                return self.video_infos
            except yt_dlp.utils.DownloadError:
                continue
            except Exception:
                return None
    
    def start_download(self, config: DownloadConfig):
        """Start the download process in a separate thread."""
        thread = threading.Thread(target=self._download_process, args=(config,))
        thread.daemon = True
        thread.start()
    
    def _download_process(self, config: DownloadConfig):
        """Main download process."""
        try:
            ydl_opts = self._build_ydl_options(config)
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.add_post_processor(CustomPostProcessor(config), when='post_process')
                ydl.download([config.url])
            
            self._send_completion_notification(config)
            
            # Call completion callback to reset UI
            if self.completion_callback:
                self.completion_callback()
            
        except yt_dlp.utils.DownloadError as error:
            print(f"Download error: {error}")
            self._retry_download(config)
    
    def _build_ydl_options(self, config: DownloadConfig) -> Dict[str, Any]:
        """Build yt-dlp options based on configuration."""
        base_opts = {
            'verbose': config.verbose,
            'no-part': True,
            'ignoreerrors': True,
            'quiet': True,
            'extractor_args': {'youtubetab': {'skip': ['authcheck']}},
            'external_downloader_args': ['-loglevel', 'panic'],
            'outtmpl': config.output_template,
            'noplaylist': not config.is_playlist,
            'progress_hooks': [self._progress_hook],
            'playliststart': config.playlist_start,
            'playlistend': config.playlist_end
        }
        
        if config.file_format == "mp3":
            return self._add_mp3_options(base_opts, config)
        elif config.file_format == "mp4":
            return self._add_mp4_options(base_opts, config)
        
        return base_opts
    
    def _add_mp3_options(self, opts: Dict, config: DownloadConfig) -> Dict:
        """Add MP3-specific options."""
        opts['format'] = 'bestaudio/best'
        
        if self.ffmpeg_path is not None:
            opts['ffmpeg_location'] = self.ffmpeg_path
            opts['postprocessors'] = [
                {
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': config.bitrate
                },
                {'key': 'FFmpegMetadata', 'add_metadata': True}
            ]
        else:
            print("Warning: MP3 conversion disabled - ffmpeg not found")
            opts['format'] = 'bestaudio'
        
        return opts
    
    def _add_mp4_options(self, opts: Dict, config: DownloadConfig) -> Dict:
        """Add MP4-specific options."""
        format_string = f'bestvideo[height<={config.quality}][vbr<=12000][ext=mp4]+bestaudio[ext=m4a]/best[vbr<=12000][ext=mp4]/best'
        opts['format'] = format_string
        
        if self.ffmpeg_path is not None:
            opts['ffmpeg_location'] = self.ffmpeg_path
            opts['postprocessors'] = [{'key': 'FFmpegVideoConvertor', 'preferedformat': 'mp4'}]
        else:
            print("Warning: MP4 conversion disabled - ffmpeg not found")
        
        return opts
    
    def _progress_hook(self, d: Dict):
        """Handle progress updates from yt-dlp."""
        if self.progress_callback:
            self.progress_callback(d, self.video_infos, self.progress)
    
    def _retry_download(self, config: DownloadConfig):
        """Retry download on error."""
        print("There was a problem during the download, automatically restarting!")
        # Implementation for retry logic
        pass
    
    def _send_completion_notification(self, config: DownloadConfig):
        """Send completion notification."""
        if self.video_infos:
            if config.is_playlist:
                title = self.video_infos.get('title', 'Unknown Playlist')
                message = f"Playlist \"{title}\" has been downloaded."
            else:
                title = self.video_infos.get('title', 'Unknown')
                message = f"Video \"{title}\" has been downloaded."
            
            # Try to send desktop notification
            if NOTIFICATIONS_AVAILABLE:
                try:
                    notification.notify(
                        title='Download Complete!',
                        message=message,
                        app_icon=ICON_PATH,
                        timeout=10
                    )
                except Exception:
                    # Fallback to console if notification fails
                    print(f"Download Complete! {message}")
            else:
                # No notification library available
                print(f"Download Complete! {message}")
