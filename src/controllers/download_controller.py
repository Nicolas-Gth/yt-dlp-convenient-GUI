"""
Download controller handling yt-dlp operations and metadata processing.
"""
import os
import re
import io
import json
import subprocess
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
    
    def __init__(self, download_config: DownloadConfig, normalize_callback: Optional[Callable] = None):
        super().__init__()
        self.config = download_config
        self.normalize_callback = normalize_callback
    
    def run(self, video_infos):
        """Process downloaded file: add metadata, rename, and set album cover."""
        file_format = self.config.file_format
        file_path = f"{self.config.output_directory}/{video_infos['title']}.{file_format}"

        # Check if the file actually exists
        if not os.path.exists(file_path):
            print(f"Warning: File {file_path} not found. Conversion may have failed.")
            return [], video_infos

        # Analyze loudness after normalization if enabled
        if self.config.normalize_volume:
            self._analyze_and_report_loudness(file_path, video_infos.get('title', 'Unknown'))

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
    
    def _analyze_and_report_loudness(self, file_path: str, title: str):
        """Analyze the file loudness using ffmpeg and report via callback."""
        try:
            from config import get_ffmpeg_path
            ffmpeg_dir = get_ffmpeg_path()
            if ffmpeg_dir:
                ffmpeg_bin = os.path.join(ffmpeg_dir, 'ffmpeg')
                if not os.path.exists(ffmpeg_bin):
                    ffmpeg_bin = 'ffmpeg'
            else:
                ffmpeg_bin = 'ffmpeg'
            
            result = subprocess.run(
                [ffmpeg_bin, '-i', file_path, '-af', 'loudnorm=print_format=json', '-f', 'null', '-'],
                capture_output=True, text=True, timeout=60
            )
            
            # Parse the loudnorm JSON output from stderr
            stderr = result.stderr
            json_start = stderr.rfind('{')
            json_end = stderr.rfind('}') + 1
            
            if json_start != -1 and json_end > json_start:
                loudness_data = json.loads(stderr[json_start:json_end])
                input_i = float(loudness_data.get('input_i', 0))
                target = self.config.normalize_target
                
                normalize_info = {
                    'title': title,
                    'measured_loudness': input_i,
                    'target': target,
                }
                
                print(f"Normalization: \"{title}\" measured at {input_i:.1f} LUFS (target: {target:.1f} LUFS)")
                
                if self.normalize_callback:
                    self.normalize_callback(normalize_info)
        except Exception as e:
            print(f"Warning: Could not analyze loudness: {e}")
    
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
        self.normalize_callback: Optional[Callable] = None
        self.video_infos: Optional[Dict] = None
        
    def set_progress_callback(self, callback: Callable):
        """Set the callback function for progress updates."""
        self.progress_callback = callback
    
    def set_completion_callback(self, callback: Callable):
        """Set the callback function for download completion."""
        self.completion_callback = callback
    
    def set_normalize_callback(self, callback: Callable):
        """Set the callback function for normalization info."""
        self.normalize_callback = callback
    
    def fetch_video_info(self, config: DownloadConfig, fetch_progress_callback: Optional[Callable] = None) -> tuple[Optional[Dict], Optional[str]]:
        """Fetch video information without downloading. Returns (info, error_message)."""
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
        
        # For playlists, use extract_flat for much faster extraction
        # (no per-video HTTP request, just playlist API pagination)
        if config.is_playlist:
            ydl_opts['extract_flat'] = 'in_playlist'
        
        try:
            if config.is_playlist and fetch_progress_callback:
                # Two-step extraction with progress tracking:
                # 1) Get raw result without processing (entries stay as generator)
                # 2) Wrap entries generator to count progress, then process
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ie_result = ydl.extract_info(config.url, download=False, process=False)
                    
                    if ie_result and ie_result.get('_type') in ('playlist', 'multi_video') and 'entries' in ie_result:
                        total_hint = ie_result.get('playlist_count')  # May be None
                        original_entries = ie_result['entries']
                        
                        def counting_entries():
                            count = 0
                            for entry in original_entries:
                                count += 1
                                fetch_progress_callback(count, total_hint)
                                yield entry
                        
                        ie_result['entries'] = counting_entries()
                        self.video_infos = ydl.process_ie_result(ie_result, download=False)
                    else:
                        self.video_infos = ie_result
            else:
                self.video_infos = yt_dlp.YoutubeDL(ydl_opts).extract_info(config.url, download=False)
            
            # Check if video_infos is None or empty (which happens with ignoreerrors=True for DRM sites)
            if not self.video_infos:
                # Check if this is a known DRM-protected site
                if ("spotify.com" in config.url.lower() or 
                    "netflix.com" in config.url.lower() or
                    "disney" in config.url.lower() or
                    "hulu.com" in config.url.lower() or
                    "amazon" in config.url.lower()):
                    return None, "This content is protected by DRM and cannot be downloaded.\n\nDRM (Digital Rights Management) prevents downloading from services like Spotify, Netflix, etc."
                else:
                    return None, "Could not retrieve video information. Please check the URL."
            
            return self.video_infos, None
        except yt_dlp.utils.ExtractorError as error:
            error_message = str(error)
            
            # Handle ExtractorError specifically (includes DRM errors)
            if ("DRM protection" in error_message or "DRM protected" in error_message or 
                "use DRM protection" in error_message or "known to use DRM" in error_message):
                return None, "This content is protected by DRM and cannot be downloaded.\n\nDRM (Digital Rights Management) prevents downloading from services like Spotify, Netflix, etc."
            else:
                clean_error = error_message.replace("ERROR: ", "").strip()
                return None, f"Download failed: {clean_error}"
        except yt_dlp.utils.DownloadError as error:
            error_message = str(error)
            
            # Try to extract meaningful error messages
            if ("DRM protection" in error_message or "DRM protected" in error_message or 
                "use DRM protection" in error_message or "known to use DRM" in error_message):
                return None, "This content is protected by DRM and cannot be downloaded.\n\nDRM (Digital Rights Management) prevents downloading from services like Spotify, Netflix, etc."
            elif "Video unavailable" in error_message:
                return None, "This video is unavailable or has been removed."
            elif "Private video" in error_message:
                return None, "This video is private and cannot be downloaded."
            elif "This video is only available for Music Premium members" in error_message:
                return None, "This video requires YouTube Music Premium."
            elif "Video not found" in error_message or "does not exist" in error_message:
                return None, "Video not found. Please check the URL."
            elif "Unsupported URL" in error_message:
                return None, "Unsupported URL format. Please check the URL."
            elif "Sign in to confirm your age" in error_message:
                return None, "This video requires age verification and cannot be downloaded."
            elif "This video is not available" in error_message:
                return None, "This video is not available in your region or has been removed."
            else:
                # For other errors, show the actual yt-dlp error message
                clean_error = error_message.replace("ERROR: ", "").strip()
                return None, f"Download failed: {clean_error}"
        except Exception as e:
            return None, f"Unexpected error: {str(e)}"
    
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
                ydl.add_post_processor(
                    CustomPostProcessor(config, normalize_callback=self.normalize_callback),
                    when='post_process'
                )
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
            
            # Add volume normalization if enabled
            # Keys must be lowercase — yt-dlp's _configuration_args does .lower() lookups.
            if config.normalize_volume:
                target = config.normalize_target
                opts['postprocessor_args'] = {
                    'extractaudio': [
                        '-af', f'loudnorm=I={target}:TP=-1.5:LRA=11'
                    ]
                }
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
            
            # Add volume normalization if enabled
            # For MP4, apply loudnorm during the merge step.
            # We override the audio codec to re-encode audio with loudnorm
            # while keeping video as stream copy.
            # Key must be lowercase — yt-dlp's _configuration_args does .lower() lookups.
            if config.normalize_volume:
                target = config.normalize_target
                opts['postprocessor_args'] = {
                    'merger+ffmpeg_o': [
                        '-c:v', 'copy',
                        '-c:a', 'aac', '-b:a', '192k',
                        '-af', f'loudnorm=I={target}:TP=-1.5:LRA=11'
                    ]
                }
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
