"""
Download controller handling yt-dlp operations and download orchestration.
"""
import os
import threading
from typing import Optional, Dict, Callable
import yt_dlp
from config import COOKIES_PATH, get_ffmpeg_path

from models import DownloadConfig, DownloadProgress
from utils.playlist_utils import normalize_playlist_url, compute_playlist_offset
from utils.post_processor_utils import CustomPostProcessor
from utils.ydl_options_utils import build_ydl_options
from utils.error_messages_utils import cookie_error_message, age_restricted_error_message
from utils.notification_utils import send_completion_notification



class DownloadController:
    """Main controller for download operations."""
    
    def __init__(self):
        self.progress = DownloadProgress()
        self.ffmpeg_path = get_ffmpeg_path()
        self.progress_callback: Optional[Callable] = None
        self.completion_callback: Optional[Callable] = None
        self.normalize_callback: Optional[Callable] = None
        self.cancel_callback: Optional[Callable] = None
        self.error_callback: Optional[Callable] = None
        self.age_restricted_callback: Optional[Callable] = None
        self.format_unavailable_callback: Optional[Callable] = None
        self.video_unavailable_callback: Optional[Callable] = None
        self.video_infos: Optional[Dict] = None
        self._cancelled = False
        self._current_config: Optional[DownloadConfig] = None
        self._ydl_instance: Optional[yt_dlp.YoutubeDL] = None
        self._playlist_urls: list = []
        self._current_playlist_index: int = 0
        self._playlist_total_count: int = 0
        self._hidden_entries: list = []  # Entries in API but hidden on YouTube
        self._age_restricted_entries: list = []  # Entries skipped due to age restriction
        self._format_unavailable_entries: list = []  # Entries skipped due to format errors
        self._video_unavailable_entries: list = []  # Entries skipped because the video is unavailable
    
    def set_progress_callback(self, callback: Callable):
        """Set the callback function for progress updates."""
        self.progress_callback = callback
    
    def set_completion_callback(self, callback: Callable):
        """Set the callback function for download completion."""
        self.completion_callback = callback
    
    def set_normalize_callback(self, callback: Callable):
        """Set the callback function for normalization info."""
        self.normalize_callback = callback
    
    def set_cancel_callback(self, callback: Callable):
        """Set the callback function for when download is cancelled."""
        self.cancel_callback = callback
    
    def set_error_callback(self, callback: Callable):
        """Set the callback function for download errors that need UI display."""
        self.error_callback = callback
    
    def set_age_restricted_callback(self, callback: Callable):
        """Set the callback for age-restricted entries detected during download."""
        self.age_restricted_callback = callback

    def set_format_unavailable_callback(self, callback: Callable):
        """Set the callback for format-unavailable entries detected during download."""
        self.format_unavailable_callback = callback

    def set_video_unavailable_callback(self, callback: Callable):
        """Set the callback for video-unavailable entries detected during download."""
        self.video_unavailable_callback = callback
    
    def cancel_download(self):
        """Cancel the current download and clean up partial files."""
        self._cancelled = True
        print("Download cancellation requested...")
        
        # Abort the yt-dlp instance if running
        if self._ydl_instance:
            try:
                # yt-dlp checks this flag between downloads
                self._ydl_instance._download_retcode = 1
                # For the current file being downloaded, raise in progress hook
            except Exception:
                pass
        
        # Clean up partial files in output directory
        if self._current_config:
            self._cleanup_partial_files(self._current_config.output_directory)
    
    def _cleanup_partial_files(self, output_dir: str):
        """Remove .part, .ytdl, and other temporary download files."""
        if not output_dir or not os.path.isdir(output_dir):
            return
        try:
            for f in os.listdir(output_dir):
                fp = os.path.join(output_dir, f)
                if os.path.isfile(fp) and (f.endswith('.part') or f.endswith('.ytdl') or f.endswith('.temp')):
                    print(f"  Removing partial file: {f}")
                    os.remove(fp)
        except Exception as e:
            print(f"Warning: could not clean up partial files: {e}")
    
    def fetch_video_info(self, config: DownloadConfig, fetch_progress_callback: Optional[Callable] = None) -> tuple[Optional[Dict], Optional[str]]:
        """Fetch video information without downloading. Returns (info, error_message)."""
        self._playlist_urls = []

        # Normalise watch?v=…&list=… URLs to pure playlist URLs so that
        # yt-dlp always extracts the playlist (not the single video).
        if config.is_playlist:
            config.url = normalize_playlist_url(config.url)

        # Lightweight logger that captures error messages so we can detect
        # specific errors even when ignoreerrors=True swallows exceptions.
        class _ErrorCapture:
            def __init__(self):
                self.errors: list[str] = []
            def debug(self, msg):
                pass
            def info(self, msg):
                pass
            def warning(self, msg):
                pass
            def error(self, msg):
                self.errors.append(str(msg))

        error_capture = _ErrorCapture()

        ydl_opts = {
            'verbose': config.verbose,
            'quiet': True,
            'ignoreerrors': True,
            'extractor_args': {'youtubetab': {'skip': ['authcheck']}},
            'external_downloader_args': ['-loglevel', 'panic'],
            'simulate': True,
            'cachedir': False,
            'noplaylist': not config.is_playlist,
            'logger': error_capture,
        }
        
        # Use cookies file if available
        if os.path.isfile(COOKIES_PATH):
            ydl_opts['cookiefile'] = COOKIES_PATH
        
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
                # Check captured errors for cookie / bot-check
                for err in error_capture.errors:
                    if "Sign in to confirm" in err and "bot" in err:
                        return None, cookie_error_message()
                # Check if this is a known DRM-protected site
                if ("spotify.com" in config.url.lower() or 
                    "netflix.com" in config.url.lower() or
                    "disney" in config.url.lower() or
                    "hulu.com" in config.url.lower() or
                    "amazon" in config.url.lower()):
                    return None, "This content is protected by DRM and cannot be downloaded.\n\nDRM (Digital Rights Management) prevents downloading from services like Spotify, Netflix, etc."
                else:
                    return None, "Could not retrieve video information. Please check the URL."
            
            # For playlists, slice entries to the user's requested range.
            if config.is_playlist and self.video_infos and 'entries' in self.video_infos:
                all_entries = self.video_infos.get('entries', [])
                if isinstance(all_entries, list) and len(all_entries) > 0:
                    total_count = len(all_entries)
                    start_idx = max(0, config.playlist_start - 1)
                    end_idx = min(config.playlist_end, total_count)

                    # Detect numbering offset between YouTube's displayed
                    # positions and yt-dlp's flat-extracted list.
                    # YouTube may hide certain entries (deleted, private,
                    # region-restricted…) that the API still includes,
                    # causing the user-visible position N to differ from
                    # API index N.
                    if start_idx > 0:
                        offset, self._hidden_entries = compute_playlist_offset(
                            config.url, config.playlist_start,
                            config.playlist_end, all_entries)
                        start_idx += offset
                        end_idx += offset
                        # Clamp to valid range
                        start_idx = max(0, min(start_idx, total_count - 1))
                        end_idx = min(end_idx, total_count)

                    # Only use individual downloads if user specified a sub-range
                    if start_idx > 0 or end_idx < total_count:
                        sliced = all_entries[start_idx:end_idx]
                        # Filter only None/truly-broken entries from the slice
                        valid = [e for e in sliced if e and isinstance(e, dict) and e.get('id')]
                        self._playlist_urls = []
                        for entry in valid:
                            vid_id = entry.get('id') or entry.get('url')
                            url = entry.get('url', '')
                            if not url.startswith('http'):
                                url = f"https://www.youtube.com/watch?v={vid_id}"
                            self._playlist_urls.append(url)

                        self.video_infos['entries'] = valid
                        self.video_infos['playlist_count'] = len(valid)

            return self.video_infos, None
        except yt_dlp.utils.ExtractorError as error:
            error_message = str(error)
            
            # Handle cookie / bot-check errors
            if "Sign in to confirm" in error_message and "bot" in error_message:
                return None, cookie_error_message()
            # Handle ExtractorError specifically (includes DRM errors)
            elif ("DRM protection" in error_message or "DRM protected" in error_message or 
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
            elif "Sign in to confirm" in error_message and "bot" in error_message:
                return None, cookie_error_message()
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
        self._cancelled = False
        self._current_config = config
        thread = threading.Thread(target=self._download_process, args=(config,))
        thread.daemon = True
        thread.start()
    
    def _download_process(self, config: DownloadConfig):
        """Main download process."""
        self._age_restricted_entries = []
        self._format_unavailable_entries = []
        self._video_unavailable_entries = []
        try:
            ydl_opts = build_ydl_options(config, self.ffmpeg_path, self._progress_hook, self._cancel_filter)

            # Logger that captures error messages to detect cookie/bot errors
            # even when ignoreerrors=True swallows the exception.
            class _ErrorCapture:
                def __init__(self):
                    self.errors: list[str] = []
                def debug(self, msg):
                    if msg and isinstance(msg, str) and msg.startswith('[debug]'):
                        print(f"  {msg}")
                def info(self, msg):
                    pass
                def warning(self, msg):
                    if msg:
                        print(f"  [warning] {msg}")
                def error(self, msg):
                    print(f"  [error] {msg}")
                    self.errors.append(str(msg))

            error_capture = _ErrorCapture()
            ydl_opts['logger'] = error_capture

            def _check_cookie_error():
                """Return True and fire error callback if a cookie/bot error was logged."""
                for err in error_capture.errors:
                    if "Sign in to confirm" in err and "bot" in err:
                        print("Cookie authentication required.")
                        self._cleanup_partial_files(config.output_directory)
                        if self.error_callback:
                            self.error_callback(cookie_error_message())
                        return True
                return False

            def _check_age_restricted(video_title: str = '', video_channel: str = ''):
                """Check captured errors for age-restriction and track the entry."""
                for err in error_capture.errors:
                    if "Sign in to confirm your age" in err:
                        entry = {
                            'title': video_title or 'Unknown',
                            'channel': video_channel or '',
                        }
                        self._age_restricted_entries.append(entry)
                        # Notify UI immediately so entry appears live
                        if self.age_restricted_callback:
                            self.age_restricted_callback(entry)
                        error_capture.errors.clear()
                        return True
                return False

            def _check_format_unavailable(video_title: str = '', video_channel: str = ''):
                """Check captured errors for format/signature issues and track the entry."""
                for err in error_capture.errors:
                    if "Requested format is not available" in err:
                        entry = {
                            'title': video_title or 'Unknown',
                            'channel': video_channel or '',
                        }
                        self._format_unavailable_entries.append(entry)
                        if self.format_unavailable_callback:
                            self.format_unavailable_callback(entry)
                        error_capture.errors.clear()
                        return True
                return False

            _VIDEO_UNAVAILABLE_PATTERNS = (
                "Video unavailable",
                "This video is not available",
                "Private video",
                "This video has been removed",
                "video is no longer available",
                "Join this channel to get access",
                "This video requires payment",
            )

            def _check_video_unavailable(video_title: str = '', video_channel: str = ''):
                """Check captured errors for generic video unavailability."""
                for err in error_capture.errors:
                    if any(pat in err for pat in _VIDEO_UNAVAILABLE_PATTERNS):
                        entry = {
                            'title': video_title or 'Unknown',
                            'channel': video_channel or '',
                        }
                        self._video_unavailable_entries.append(entry)
                        if self.video_unavailable_callback:
                            self.video_unavailable_callback(entry)
                        error_capture.errors.clear()
                        return True
                return False

            if config.is_playlist and self._playlist_urls:
                # Download individual videos by URL to avoid playlist
                # indexing offset caused by deleted/unavailable entries.
                ydl_opts['noplaylist'] = True
                self._playlist_total_count = len(self._playlist_urls)
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    self._ydl_instance = ydl
                    ydl.add_post_processor(
                        CustomPostProcessor(config, normalize_callback=self.normalize_callback),
                        when='post_process'
                    )
                    for i, url in enumerate(self._playlist_urls, 1):
                        if self._cancelled:
                            break
                        self._current_playlist_index = i
                        # Resolve video title/channel from fetched info for error tracking
                        video_title = ''
                        video_channel = ''
                        if self.video_infos and 'entries' in self.video_infos:
                            entries = self.video_infos['entries']
                            if isinstance(entries, list) and i - 1 < len(entries) and entries[i - 1]:
                                video_title = entries[i - 1].get('title', '')
                                video_channel = (entries[i - 1].get('channel')
                                                 or entries[i - 1].get('uploader', ''))
                        ydl.download([url])
                        if _check_cookie_error():
                            self._ydl_instance = None
                            return
                        _check_age_restricted(video_title, video_channel)
                        _check_format_unavailable(video_title, video_channel)
                        _check_video_unavailable(video_title, video_channel)
            else:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    self._ydl_instance = ydl
                    ydl.add_post_processor(
                        CustomPostProcessor(config, normalize_callback=self.normalize_callback),
                        when='post_process'
                    )
                    ydl.download([config.url])
                    # For single videos, check age restriction and format errors
                    vi = self.video_infos or {}
                    _check_age_restricted(
                        vi.get('title', ''),
                        vi.get('channel') or vi.get('uploader', '')
                    )
                    _check_format_unavailable(
                        vi.get('title', ''),
                        vi.get('channel') or vi.get('uploader', '')
                    )
                    _check_video_unavailable(
                        vi.get('title', ''),
                        vi.get('channel') or vi.get('uploader', '')
                    )
            
            self._ydl_instance = None

            # Check for cookie errors that were swallowed by ignoreerrors
            if _check_cookie_error():
                return
            
            if self._cancelled:
                self._cleanup_partial_files(config.output_directory)
                print("Download cancelled.")
                if self.cancel_callback:
                    self.cancel_callback()
                return
            
            send_completion_notification(config, self.video_infos, self.progress)
            
            # Call completion callback to reset UI
            if self.completion_callback:
                self.completion_callback()
            
        except (yt_dlp.utils.ExistingVideoReached, yt_dlp.utils.RejectedVideoReached):
            # Raised by progress hook to abort the entire playlist immediately
            self._ydl_instance = None
            self._cleanup_partial_files(config.output_directory)
            print("Download cancelled.")
            if self.cancel_callback:
                self.cancel_callback()
        except yt_dlp.utils.DownloadError as error:
            self._ydl_instance = None
            if self._cancelled:
                self._cleanup_partial_files(config.output_directory)
                print("Download cancelled.")
                if self.cancel_callback:
                    self.cancel_callback()
                return
            error_message = str(error)
            # Handle cookie / bot-check errors during download
            if "Sign in to confirm" in error_message and "bot" in error_message:
                print("Cookie authentication required.")
                self._cleanup_partial_files(config.output_directory)
                if self.error_callback:
                    self.error_callback(cookie_error_message())
                return
            print(f"Download error: {error}")
            self._retry_download(config)
    
    def _cancel_filter(self, info_dict, *, incomplete):
        """Match filter that rejects all entries once download is cancelled.
        
        This runs before yt-dlp starts extracting/downloading each entry,
        so it prevents wasted network requests after cancellation.
        Returning a string means 'reject this entry with this reason'.
        """
        if self._cancelled:
            raise yt_dlp.utils.ExistingVideoReached()
        return None

    def _progress_hook(self, d: Dict):
        """Handle progress updates from yt-dlp."""
        if self._cancelled:
            # Use ExistingVideoReached to make yt-dlp abort the entire
            # playlist loop immediately, instead of DownloadError which
            # is caught by ignoreerrors and moves to the next entry.
            raise yt_dlp.utils.ExistingVideoReached()
        # For individual-URL playlist downloads, inject playlist context
        # so the progress display works correctly.
        if self._playlist_urls and 'info_dict' in d:
            d['info_dict'].setdefault('playlist_autonumber', self._current_playlist_index)
            d['info_dict'].setdefault('n_entries', self._playlist_total_count)
        if self.progress_callback:
            self.progress_callback(d, self.video_infos, self.progress)
    
    def _retry_download(self, config: DownloadConfig):
        """Retry download on error."""
        print("There was a problem during the download, automatically restarting!")
        # Implementation for retry logic
        pass
