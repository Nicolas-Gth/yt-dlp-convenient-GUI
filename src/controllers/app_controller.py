"""
Main application controller coordinating view and download operations.
"""
import datetime
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
        
        # Connect view callbacks to controller methods
        self.setup_callbacks()
        
        # Set download progress callback
        self.download_controller.set_progress_callback(self.on_download_progress)
        # Set download completion callback
        self.download_controller.set_completion_callback(self.on_download_complete)
    
    def setup_callbacks(self):
        """Connect view callbacks to controller methods."""
        self.view.on_convert_callback = self.start_conversion
        self.view.on_format_change_callback = self.on_format_change
        self.view.on_playlist_change_callback = self.on_playlist_change
        self.view.on_browse_callback = self.on_browse_directory
    
    def start_conversion(self):
        """Start the conversion process."""
        config = self.view.get_download_config()
        
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
        # Fetch video information
        video_info = self.download_controller.fetch_video_info(config)
        if not video_info:
            print("Error: Could not retrieve video information. Please check the URL.")
            # Hide fetching progress and restore button on main thread
            self.view.root.after(0, lambda: self.view.hide_fetching_progress())
            return
        
        self.current_video_info = video_info
        
        # Update UI on main thread
        self.view.root.after(0, lambda: self._start_download_ui(config, video_info))
    
    def _start_download_ui(self, config, video_info):
        """Update UI and start download (runs on main thread)."""
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
    
    def extract_video_info(self, video_data: Dict) -> VideoInfo:
        """Extract VideoInfo object from video data dictionary."""
        return VideoInfo(
            title=video_data.get('title', 'Unknown'),
            uploader=video_data.get('uploader', 'Unknown').replace(' - Topic', ''),
            duration=video_data.get('duration', 0),
            thumbnail=video_data.get('thumbnail', ''),
            categories=video_data.get('categories', [])
        )
    
    def on_download_progress(self, progress_data: Dict, video_info: Dict, progress: DownloadProgress):
        """Handle download progress updates."""
        # Get video index for playlists
        if 'info_dict' in progress_data and 'playlist_autonumber' in progress_data['info_dict']:
            video_index = progress_data['info_dict']['playlist_autonumber'] - 1
        else:
            video_index = 0
        
        if progress_data['status'] == 'downloading':
            self.handle_downloading_status(progress_data, video_info, video_index, progress)
        elif progress_data['status'] == 'finished':
            self.handle_finished_status(progress_data, video_info, video_index, progress)
    
    def handle_downloading_status(self, progress_data: Dict, video_info: Dict, video_index: int, progress: DownloadProgress):
        """Handle downloading status updates."""
        # Update video information if song changed
        if progress.current_song != progress.previous_song:
            config = self.view.get_download_config()
            if config.is_playlist:
                self.update_playlist_display(video_info, video_index)
            else:
                self.update_single_video_display(video_info)
            
            progress.update_current_song(video_index)
        
        # Update progress percentage
        try:
            progress_str = progress_data.get('_percent_str', '0.0%')
            progress_str = progress_str.replace("\x1b[0;94m ", "").replace("\x1b[0m", "")
            percentage = float(progress_str.replace('%', ''))
            self.view.update_video_progress(percentage)
        except (ValueError, KeyError):
            self.view.update_video_progress(0.0)
    
    def handle_finished_status(self, progress_data: Dict, video_info: Dict, video_index: int, progress: DownloadProgress):
        """Handle finished status updates."""
        # Update to processing mode
        self.view.update_video_progress(100.0, "processing")
        
        # Update song name for finished video
        config = self.view.get_download_config()
        if config.is_playlist:
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
    
    def on_download_complete(self):
        """Handle download completion."""
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
