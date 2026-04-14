"""
Main application controller coordinating view and download operations.
"""
import datetime
import os
import time
from typing import Dict, Any, Optional

from views import MainApplicationView
from controllers.download_controller import DownloadController
from models import VideoInfo, PlaylistInfo, DownloadProgress
from config import FILE_FORMATS, COOKIES_PATH
from utils.cookies_validator_utils import validate_cookies_file
from utils.sleep_inhibitor_utils import sleep_inhibitor


class ApplicationController:
    """Main application controller."""
    
    def __init__(self):
        self.view = MainApplicationView()
        self.download_controller = DownloadController()
        self.current_video_info: Optional[Dict] = None
        self._current_config = None
        self._last_progress_update: float = 0.0
        self._playlist_start_time: float = 0.0
        self._playlist_current_index: int = 0
        self._completed_elapsed: float = 0.0      # total time for completed elements
        self._completed_duration: float = 0.0     # total video duration for completed elements
        self._element_start_time: float = 0.0      # when current element started
        self._current_dl_percent: float = 0.0      # latest download % for current element
        self._current_element_duration: float = 0.0  # duration of video currently being processed
        
        # Connect view callbacks to controller methods
        self.setup_callbacks()
        
        # Set download progress callback
        self.download_controller.set_progress_callback(self.on_download_progress)
        # Set download completion callback
        self.download_controller.set_completion_callback(self.on_download_complete)
        # Set normalization info callback
        self.download_controller.set_normalize_callback(self.on_normalize_info)
        # Set cancel callback
        self.download_controller.set_cancel_callback(self.on_download_cancelled)
        # Set error callback for errors during download
        self.download_controller.set_error_callback(self.on_download_error)
        # Set age-restricted callback for live skipped entry display
        self.download_controller.set_age_restricted_callback(self.on_age_restricted_entry)
        # Set format-unavailable callback for live skipped entry display
        self.download_controller.set_format_unavailable_callback(self.on_format_unavailable_entry)
        # Set video-unavailable callback for live skipped entry display
        self.download_controller.set_video_unavailable_callback(self.on_video_unavailable_entry)
    
    def setup_callbacks(self):
        """Connect view callbacks to controller methods."""
        self.view.on_convert_callback = self.start_conversion
        self.view.on_format_change_callback = self.on_format_change
        self.view.on_playlist_change_callback = self.on_playlist_change
        self.view.on_browse_callback = self.on_browse_directory
        self.view.on_stop_callback = self.on_stop_download
    
    def start_conversion(self):
        """Start the conversion process."""
        config = self.view.get_download_config()
        
        # Check if config is None (validation failed)
        if config is None:
            return
        
        # Validate input
        if not config.url or not config.output_directory:
            print("Error: Please provide both URL and output directory")
            return
        
        # Check cookies validity before starting download
        if not self._check_cookies_before_download():
            return
        
        # Show fetching progress with animated progress bar
        self.view.show_fetching_progress(config.is_playlist)
        
        # Start fetching in a separate thread to avoid blocking UI
        import threading
        fetch_thread = threading.Thread(target=self._fetch_and_start_download, args=(config,))
        fetch_thread.daemon = True
        fetch_thread.start()
    
    def _fetch_and_start_download(self, config):
        """Fetch video information and start download (runs in separate thread)."""
        # For playlists, provide a progress callback to update the fetching bar
        fetch_progress_cb = None
        if config.is_playlist:
            def fetch_progress_cb(current, total):
                self.view.root.after(0, lambda c=current, t=total:
                    self.view.update_fetching_progress(c, t))
        
        # Fetch video information
        video_info, error_message = self.download_controller.fetch_video_info(config, fetch_progress_cb)
        if not video_info:
            if error_message:
                # Show the yt-dlp error message on main thread
                self.view.root.after(0, lambda: self.view.show_ytdlp_error(error_message))
            else:
                print("Error: Could not retrieve video information. Please check the URL.")
            # Hide fetching progress and restore button on main thread
            self.view.root.after(0, lambda: self.view.hide_fetching_progress())
            return
        
        self.current_video_info = video_info
        
        # Update UI on main thread
        self.view.root.after(0, lambda: self._start_download_ui(config, video_info))
    
    def _start_download_ui(self, config, video_info):
        """Update UI and start download (runs on main thread)."""
        # Cache config for use during progress callbacks
        self._current_config = config
        self._last_progress_update = 0.0
        self._playlist_start_time = time.monotonic()
        self._playlist_current_index = 0
        self._completed_elapsed = 0.0
        self._completed_duration = 0.0
        self._element_start_time = time.monotonic()
        self._current_dl_percent = 0.0
        self._current_element_duration = 0.0
        
        # Hide fetching progress
        self.view.hide_fetching_progress()
        
        # Show download progress widgets
        self.view.show_progress_widgets(config.is_playlist)
        
        # Wire up ETA callback for playlist timer
        if config.is_playlist:
            self.view.set_eta_callback(self._compute_eta_for_timer)
        
        # Show skipped entries panel if any were detected
        hidden = self.download_controller._hidden_entries
        if hidden:
            self.view.show_skipped_entries(hidden)
        
        # Update initial progress display
        self.update_initial_progress_display(video_info, config)
        
        # Start download
        self.download_controller.start_download(config)

        # Prevent system sleep if option is enabled
        if self.view.prevent_sleep_var.get():
            sleep_inhibitor.inhibit()
    
    def update_initial_progress_display(self, video_info: Dict, config):
        """Update the initial progress display with video information."""
        if config.is_playlist:
            self.update_playlist_display(video_info, 0)
        else:
            self.update_single_video_display(video_info)
    
    def update_single_video_display(self, video_info: Dict):
        """Update display for single video download."""
        video = self.extract_video_info(video_info)
        song_name = f"Downloading \"{video.title}\""
        self.view.update_progress_info(video, song_name)
    
    def update_playlist_display(self, video_info: Dict, current_index: int):
        """Update display for playlist download."""
        try:
            playlist_length = (
                video_info.get('playlist_count')
                or 0
            )
            if not playlist_length:
                try:
                    playlist_length = len(video_info.get('entries', []))
                except TypeError:
                    playlist_length = 0
            
            if playlist_length > 0:
                self._playlist_total = playlist_length
            
            if 'entries' in video_info and isinstance(video_info['entries'], list) and len(video_info['entries']) > current_index:
                entry = video_info['entries'][current_index]
                video = self.extract_video_info(entry)
            else:
                video = VideoInfo()
            
            playlist_title = video_info.get('title', '') or ''
            if playlist_length > 0:
                song_name = f"Downloading element {current_index + 1} out of {playlist_length} from the playlist {playlist_title}"
            else:
                song_name = f"Downloading element {current_index + 1}..."
            self.view.update_progress_info(video, song_name, is_playlist=True)
        except Exception as e:
            print(f"Error updating playlist display: {e}")
            video = VideoInfo()
            song_name = "Processing playlist..."
            self.view.update_progress_info(video, song_name, is_playlist=True)
    
    def update_playlist_display_from_hook(self, video_info: Dict, info_dict: Dict, current_index: int):
        """Update display for playlist download using info_dict from progress hook (has full metadata)."""
        try:
            # Get total from info_dict (reliable), then video_info fallbacks
            playlist_length = (
                info_dict.get('n_entries')
                or info_dict.get('playlist_count')
                or (video_info or {}).get('playlist_count')
                or 0
            )
            if not playlist_length:
                try:
                    playlist_length = len(video_info.get('entries', []))
                except TypeError:
                    playlist_length = 0
            
            # Cache the total
            if playlist_length > 0:
                self._playlist_total = playlist_length
            else:
                playlist_length = getattr(self, '_playlist_total', 0)
            
            # info_dict from the progress hook has full metadata (thumbnail, categories, etc.)
            if info_dict and info_dict.get('title'):
                video = self.extract_video_info(info_dict)
            elif 'entries' in video_info and isinstance(video_info['entries'], list) and len(video_info['entries']) > current_index:
                video = self.extract_video_info(video_info['entries'][current_index])
            else:
                video = VideoInfo()
            
            playlist_title = info_dict.get('playlist_title', '') or (video_info or {}).get('title', '') or ''
            if playlist_length > 0:
                song_name = f"Downloading element {current_index + 1} out of {playlist_length} from the playlist {playlist_title}"
            else:
                song_name = f"Downloading element {current_index + 1}..."
            self.view.update_progress_info(video, song_name, is_playlist=True)
        except Exception as e:
            print(f"Error updating playlist display: {e}")
            video = VideoInfo()
            song_name = "Processing playlist..."
            self.view.update_progress_info(video, song_name, is_playlist=True)
    
    def extract_video_info(self, video_data: Dict) -> VideoInfo:
        """Extract VideoInfo object from video data dictionary."""
        raw_uploader = video_data.get('uploader', 'Unknown')
        return VideoInfo(
            title=video_data.get('title', 'Unknown'),
            uploader=raw_uploader.replace(' - Topic', ''),
            duration=video_data.get('duration', 0),
            thumbnail=video_data.get('thumbnail', ''),
            categories=video_data.get('categories', []),
            album=video_data.get('album', ''),
            raw_uploader=raw_uploader
        )
    
    def _compute_eta_for_timer(self) -> str:
        """Callback for the view's 1-second timer."""
        playlist_length = getattr(self, '_playlist_total', 0)
        # Subtract skipped entries (hidden + age-restricted) from the effective total
        skipped = (len(self.download_controller._hidden_entries)
                   + len(self.download_controller._age_restricted_entries)
                   + len(self.download_controller._format_unavailable_entries))
        effective_length = max(0, playlist_length - skipped)
        return self._compute_eta(self._playlist_current_index, effective_length)
    
    def _compute_eta(self, current_index: int, playlist_length: int) -> str:
        """Compute estimated remaining time for the playlist based on elapsed time,
        weighted by video duration when available."""
        if playlist_length <= 0:
            return ""
        
        now = time.monotonic()
        elapsed = now - self._playlist_start_time
        elapsed_int = int(elapsed)
        if elapsed_int < 60:
            elapsed_str = f"{elapsed_int}s"
        elif elapsed_int < 3600:
            em, es = divmod(elapsed_int, 60)
            elapsed_str = f"{em}m {es:02d}s"
        else:
            eh, er = divmod(elapsed_int, 3600)
            em, es = divmod(er, 60)
            elapsed_str = f"{eh}h {em:02d}m {es:02d}s"
        
        completed = current_index  # number of fully completed elements (download + processing)
        remaining_count = playlist_length - current_index
        
        if remaining_count <= 0:
            return f"Elapsed time: {elapsed_str} — Finishing..."
        
        # Collect durations of remaining entries (current + future)
        remaining_durations = []
        entries = []
        if self.current_video_info and 'entries' in self.current_video_info:
            entries = self.current_video_info.get('entries', []) or []
        for i in range(current_index, min(current_index + remaining_count, len(entries))):
            try:
                d = entries[i].get('duration', 0) or 0
                remaining_durations.append(d)
            except (IndexError, AttributeError):
                remaining_durations.append(0)
        
        # Current element elapsed and duration
        current_element_elapsed = now - self._element_start_time
        current_dur = self._current_element_duration
        
        # Try duration-weighted estimation if we have enough duration data
        use_weighted = (
            self._completed_duration > 0
            and completed >= 1
            and sum(1 for d in remaining_durations if d > 0) > 0
        )
        
        if completed >= 1 and use_weighted:
            # Ratio: real seconds spent per second of video duration
            ratio = self._completed_elapsed / self._completed_duration
            
            # Remaining time for current element
            if current_dur > 0:
                estimated_current_total = ratio * current_dur
                remaining_for_current = max(0, estimated_current_total - current_element_elapsed)
            else:
                avg = self._completed_elapsed / completed
                remaining_for_current = max(0, avg - current_element_elapsed)
            
            # Remaining time for future elements
            avg_per_element = self._completed_elapsed / completed
            remaining_for_rest = 0.0
            for d in remaining_durations[1:]:
                if d > 0:
                    remaining_for_rest += ratio * d
                else:
                    remaining_for_rest += avg_per_element
            # If we have fewer durations than remaining elements, fill with average
            missing = (remaining_count - 1) - len(remaining_durations[1:])
            if missing > 0:
                remaining_for_rest += avg_per_element * missing
            
            remaining_seconds = int(remaining_for_current + remaining_for_rest)
        elif completed >= 1:
            # Fallback: simple average (no duration data)
            avg_per_element = self._completed_elapsed / completed
            remaining_for_current = max(0, avg_per_element - current_element_elapsed)
            remaining_for_rest = avg_per_element * (remaining_count - 1)
            remaining_seconds = int(remaining_for_current + remaining_for_rest)
        elif self._current_dl_percent > 3:
            # First element: estimate from download progress percentage
            estimated_element_total = current_element_elapsed / (self._current_dl_percent / 100)
            remaining_for_current = max(0, estimated_element_total - current_element_elapsed)
            # Estimate future elements using duration ratio if possible
            if current_dur > 0 and len(remaining_durations) > 1:
                ratio = estimated_element_total / current_dur
                remaining_for_rest = 0.0
                for d in remaining_durations[1:]:
                    if d > 0:
                        remaining_for_rest += ratio * d
                    else:
                        remaining_for_rest += estimated_element_total
                missing = (remaining_count - 1) - len(remaining_durations[1:])
                if missing > 0:
                    remaining_for_rest += estimated_element_total * missing
            else:
                remaining_for_rest = estimated_element_total * (remaining_count - 1)
            remaining_seconds = int(remaining_for_current + remaining_for_rest)
        else:
            return f"Elapsed time: {elapsed_str} — Estimated remaining time: calculating..."
        
        if remaining_seconds < 60:
            eta_str = f"{remaining_seconds}s"
        elif remaining_seconds < 3600:
            minutes, secs = divmod(remaining_seconds, 60)
            eta_str = f"{minutes}m {secs:02d}s"
        else:
            hours, remainder = divmod(remaining_seconds, 3600)
            minutes, secs = divmod(remainder, 60)
            eta_str = f"{hours}h {minutes:02d}m {secs:02d}s"
        
        return f"Elapsed time: {elapsed_str} — Estimated remaining time: ~{eta_str}"
    
    def on_download_progress(self, progress_data: Dict, video_info: Dict, progress: DownloadProgress):
        """Handle download progress updates (called from download thread)."""
        # Get video index for playlists
        if 'info_dict' in progress_data and 'playlist_autonumber' in progress_data['info_dict']:
            video_index = progress_data['info_dict']['playlist_autonumber'] - 1
        else:
            video_index = 0
        
        # 'finished' status is always forwarded immediately
        if progress_data['status'] == 'finished':
            self.view.root.after(0, lambda pd=progress_data, vi=video_info, vx=video_index, p=progress:
                self.handle_finished_status(pd, vi, vx, p))
            return
        
        # For 'downloading' status, throttle UI updates to avoid flickering.
        # Only allow one update every 100ms.
        now = time.monotonic()
        if now - self._last_progress_update < 0.1:
            return
        self._last_progress_update = now
        
        self.view.root.after(0, lambda pd=progress_data, vi=video_info, vx=video_index, p=progress:
            self.handle_downloading_status(pd, vi, vx, p))
    
    def handle_downloading_status(self, progress_data: Dict, video_info: Dict, video_index: int, progress: DownloadProgress):
        """Handle downloading status updates."""
        # Update video information if song changed
        if progress.current_song != progress.previous_song:
            if self._current_config and self._current_config.is_playlist:
                # Use info_dict from progress_data which has full metadata (thumbnail, etc.)
                # The flat-extracted playlist entries lack this data.
                info_dict = progress_data.get('info_dict', {})
                self.update_playlist_display_from_hook(video_info, info_dict, video_index)
                # Track the current element's duration for ETA weighting
                self._current_element_duration = info_dict.get('duration', 0) or 0
            else:
                self.update_single_video_display(video_info)
            
            progress.update_current_song(video_index)
        
        # Update progress percentage
        try:
            progress_str = progress_data.get('_percent_str', '0.0%')
            # Strip ANSI escape codes
            progress_str = progress_str.replace("\x1b[0;94m ", "").replace("\x1b[0m", "")
            progress_str = progress_str.strip()
            percentage = float(progress_str.replace('%', ''))
            self.view.update_video_progress(percentage)
            self._current_dl_percent = percentage
        except (ValueError, KeyError):
            pass  # Don't reset to 0.0, just skip this update
    
    def handle_finished_status(self, progress_data: Dict, video_info: Dict, video_index: int, progress: DownloadProgress):
        """Handle finished status updates."""
        # Update to processing mode
        self.view.update_video_progress(100.0, "processing")
        
        # Get the title from info_dict (progress hook) which has full metadata,
        # unlike flat-extracted playlist entries which may lack 'title'.
        info_dict = progress_data.get('info_dict', {})
        title = info_dict.get('title', '')
        
        # Fallback: try from playlist entries
        if not title:
            try:
                if 'entries' in video_info and video_index < len(video_info['entries']):
                    title = video_info['entries'][video_index].get('title', '')
            except (KeyError, IndexError, TypeError):
                pass
        
        # Final fallback
        if not title:
            title = video_info.get('title', 'Unknown') if video_info else 'Unknown'
        
        # Update song name for finished video
        config = self._current_config
        if config and config.is_playlist:
            # Get total from info_dict (reliable), then video_info fallbacks
            playlist_length = (
                info_dict.get('n_entries')
                or info_dict.get('playlist_count')
                or (video_info or {}).get('playlist_count')
                or len((video_info or {}).get('entries', []) or [])
                or 0
            )
            
            # Store the total once we get it so it persists across calls
            if playlist_length > 0:
                self._playlist_total = playlist_length
            else:
                playlist_length = getattr(self, '_playlist_total', 0)
            
            playlist_title = info_dict.get('playlist_title', '') or (video_info or {}).get('title', '') or ''
            if playlist_length > 0:
                song_name = f"Downloading element {video_index + 1} out of {playlist_length} from the playlist {playlist_title}"
            else:
                song_name = f"Processing element {video_index + 1}..."
                
            # Update total progress for playlists
            if playlist_length > 0:
                total_percentage = ((video_index + 1) / playlist_length) * 100
                self.view.update_total_progress(total_percentage)
        else:
            song_name = f"Processing \"{title}\""
        
        # Update the song label
        if hasattr(self.view, 'song_label'):
            self.view.song_label.configure(text=song_name)
        
        progress.update_current_song(video_index + 1)
    
    def on_normalize_info(self, info: Dict):
        """Handle normalization info from post-processor."""
        # Record stable completion time for this element (download + processing)
        now = time.monotonic()
        element_time = now - self._element_start_time
        self._completed_elapsed += element_time
        # Accumulate video duration for ratio-based ETA
        vid_duration = info.get('duration', 0) or 0
        self._completed_duration += vid_duration
        self._element_start_time = now
        self._current_dl_percent = 0.0
        self._current_element_duration = 0.0
        self._playlist_current_index += 1
        self.view.root.after(0, lambda: self.view.show_normalize_feedback(info))
    
    def on_stop_download(self):
        """Handle stop button click — cancel the running download."""
        self.download_controller.cancel_download()
    
    def on_download_cancelled(self):
        """Handle download cancellation (called from download thread)."""
        self.view.root.after(0, lambda: self._on_download_complete_ui(cancelled=True))
    
    def on_download_error(self, error_message: str):
        """Handle a download error that requires a popup (called from download thread)."""
        self.view.root.after(0, lambda: self._on_download_error_ui(error_message))
    
    def _on_download_error_ui(self, error_message: str):
        """Show an error popup and reset the UI (runs on main thread)."""
        # Re-enable system sleep
        sleep_inhibitor.uninhibit()

        self.view.show_ytdlp_error(error_message)
        self._on_download_complete_ui(cancelled=True)
    
    def on_age_restricted_entry(self, entry: dict):
        """Handle a single age-restricted entry detected during download (called from download thread)."""
        self.view.root.after(0, lambda e=entry: self.view.show_age_restricted_entries([e]))

    def on_format_unavailable_entry(self, entry: dict):
        """Handle a single format-unavailable entry detected during download (called from download thread)."""
        self.view.root.after(0, lambda e=entry: self.view.show_format_unavailable_entries([e]))

    def on_video_unavailable_entry(self, entry: dict):
        """Handle a single video-unavailable entry detected during download (called from download thread)."""
        self.view.root.after(0, lambda e=entry: self.view.show_video_unavailable_entries([e]))
    
    def on_download_complete(self):
        """Handle download completion (called from download thread)."""
        self.view.root.after(0, lambda: self._on_download_complete_ui(cancelled=False))
    
    def _build_completion_message(self, cancelled: bool) -> str:
        """Build the completion/cancellation message for playlists."""
        config = self._current_config
        downloaded_count = getattr(self.view, '_info_item_count', 0)
        playlist_title = ''
        if config and config.is_playlist and self.current_video_info:
            playlist_title = self.current_video_info.get('title', '') or ''
        
        prefix = "Download aborted. " if cancelled else ""
        
        if downloaded_count > 0 and playlist_title:
            msg = f"{downloaded_count} element{'s' if downloaded_count > 1 else ''} downloaded from playlist {playlist_title}."
        elif downloaded_count > 0:
            msg = f"{downloaded_count} element{'s' if downloaded_count > 1 else ''} downloaded."
        elif playlist_title:
            msg = f"Playlist {playlist_title} downloaded."
        else:
            msg = "Download complete."
        
        return f"{prefix}{msg}"
    
    def _on_download_complete_ui(self, cancelled: bool = False):
        """Handle download completion UI updates (runs on main thread)."""
        # Re-enable system sleep
        sleep_inhibitor.uninhibit()

        # Show completion message
        completion_msg = self._build_completion_message(cancelled)
        if hasattr(self.view, 'song_label'):
            self.view.song_label.configure(text=completion_msg)
        
        # Reset progress
        self.download_controller.progress.reset()
        self._playlist_total = 0
        
        # Show "New download " button (resets progress bar) BEFORE the popup
        self.view.show_new_download_button()
        
        # Show age-restricted popup after UI is reset (dialog is blocking)
        age_restricted = self.download_controller._age_restricted_entries
        if age_restricted:
            from utils.error_messages_utils import age_restricted_error_message
            self.view.show_ytdlp_error(age_restricted_error_message(age_restricted))
    
    def on_format_change(self, format_type: str):
        """Handle format selection change."""
        # Additional logic if needed when format changes
        pass
    
    def on_playlist_change(self, is_playlist: bool):
        """Handle playlist option change."""
        # Additional logic if needed when playlist option changes
        pass
    
    def on_browse_directory(self):
        """Handle browse directory button click."""
        # This method is called by the view when browse button is clicked
        # The actual directory selection is handled in the view's _on_browse_click method
        pass
    
    def _check_cookies_before_download(self) -> bool:
        """Validate cookies and prompt the user. Returns True to proceed, False to cancel."""
        warning = validate_cookies_file()
        if warning is None:
            return True  # Cookies are fine (or absent), proceed

        import tkinter.messagebox as messagebox
        proceed = messagebox.askokcancel(
            "Cookies Warning",
            warning + "\n\nContinue download anyway?",
            icon="warning"
        )
        return proceed

    def run(self):
        """Start the application."""
        self.view.run()


def main():
    """Main entry point for the application."""
    app = ApplicationController()
    app.run()


if __name__ == "__main__":
    main()
