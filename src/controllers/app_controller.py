"""
Main application controller coordinating view and download operations.
"""
import datetime
import time
from typing import Dict, Any, Optional

from views import MainApplicationView
from controllers.download_controller import DownloadController
from models import VideoInfo, PlaylistInfo, DownloadProgress
from config import FILE_FORMATS


class ApplicationController:
    """Main application controller."""
    
    def __init__(self):
        self.view = MainApplicationView()
        self.download_controller = DownloadController()
        self.current_video_info: Optional[Dict] = None
        self._current_config = None
        self._last_progress_update: float = 0.0
        
        # Connect view callbacks to controller methods
        self.setup_callbacks()
        
        # Set download progress callback
        self.download_controller.set_progress_callback(self.on_download_progress)
        # Set download completion callback
        self.download_controller.set_completion_callback(self.on_download_complete)
        # Set normalization info callback
        self.download_controller.set_normalize_callback(self.on_normalize_info)
    
    def setup_callbacks(self):
        """Connect view callbacks to controller methods."""
        self.view.on_convert_callback = self.start_conversion
        self.view.on_format_change_callback = self.on_format_change
        self.view.on_playlist_change_callback = self.on_playlist_change
        self.view.on_browse_callback = self.on_browse_directory
    
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
        
        # Hide fetching progress
        self.view.hide_fetching_progress()
        
        # Show download progress widgets
        self.view.show_progress_widgets(config.is_playlist)
        
        # Update initial progress display
        self.update_initial_progress_display(video_info, config)
        
        # Start download
        self.download_controller.start_download(config)
    
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
            if 'entries' in video_info and len(video_info['entries']) > current_index:
                entry = video_info['entries'][current_index]
                video = self.extract_video_info(entry)
                playlist_title = video_info.get('title', 'Unknown Playlist')
                playlist_length = len(video_info['entries'])
                
                song_name = f"Downloading video {current_index + 1} of {playlist_length} from the playlist \"{playlist_title}\""
                self.view.update_progress_info(video, song_name, is_playlist=True)
            else:
                # Fallback for invalid playlist data
                video = VideoInfo()
                song_name = "Processing playlist..."
                self.view.update_progress_info(video, song_name, is_playlist=True)
        except Exception as e:
            print(f"Error updating playlist display: {e}")
            video = VideoInfo()
            song_name = "Processing playlist..."
            self.view.update_progress_info(video, song_name, is_playlist=True)
    
    def update_playlist_display_from_hook(self, video_info: Dict, info_dict: Dict, current_index: int):
        """Update display for playlist download using info_dict from progress hook (has full metadata)."""
        try:
            playlist_title = video_info.get('title', 'Unknown Playlist')
            playlist_length = len(video_info.get('entries', []))
            
            # info_dict from the progress hook has full metadata (thumbnail, categories, etc.)
            if info_dict and info_dict.get('title'):
                video = self.extract_video_info(info_dict)
            elif 'entries' in video_info and len(video_info['entries']) > current_index:
                video = self.extract_video_info(video_info['entries'][current_index])
            else:
                video = VideoInfo()
            
            song_name = f"Downloading video {current_index + 1} of {playlist_length} from the playlist \"{playlist_title}\""
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
        except (ValueError, KeyError):
            pass  # Don't reset to 0.0, just skip this update
    
    def handle_finished_status(self, progress_data: Dict, video_info: Dict, video_index: int, progress: DownloadProgress):
        """Handle finished status updates."""
        # Update to processing mode
        self.view.update_video_progress(100.0, "processing")
        
        # Update song name for finished video
        config = self._current_config
        if config and config.is_playlist:
            try:
                if 'entries' in video_info and video_index < len(video_info['entries']):
                    title = video_info['entries'][video_index].get('title', 'Unknown')
                else:
                    title = 'Unknown'
                song_name = f"Finished downloading \"{title}\""
            except (KeyError, IndexError):
                song_name = "Finished downloading video"
                
            # Update total progress for playlists
            playlist_length = len(video_info.get('entries', []))
            if playlist_length > 0:
                total_percentage = ((video_index + 1) / playlist_length) * 100
                self.view.update_total_progress(total_percentage)
        else:
            title = video_info.get('title', 'Unknown') if video_info else 'Unknown'
            song_name = f"Finished downloading \"{title}\""
        
        # Update the song label
        if hasattr(self.view, 'song_label'):
            self.view.song_label.configure(text=song_name)
        
        progress.update_current_song(video_index + 1)
    
    def on_normalize_info(self, info: Dict):
        """Handle normalization info from post-processor."""
        self.view.root.after(0, lambda: self.view.show_normalize_feedback(info))
    
    def on_download_complete(self):
        """Handle download completion (called from download thread)."""
        self.view.root.after(0, self._on_download_complete_ui)
    
    def _on_download_complete_ui(self):
        """Handle download completion UI updates (runs on main thread)."""
        # Reset progress
        self.download_controller.progress.reset()
        
        # Hide progress widgets and show convert button
        self.view.hide_progress_widgets()
        
        # Re-enable the convert button
        self.view.set_convert_button_enabled(True)
    
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
    
    def run(self):
        """Start the application."""
        self.view.run()


def main():
    """Main entry point for the application."""
    app = ApplicationController()
    app.run()


if __name__ == "__main__":
    main()
