"""
Settings manager for persistent application configuration.
"""
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional


class SettingsManager:
    """Manages persistent application settings."""
    
    def __init__(self):
        """Initialize settings manager with appropriate config directory."""
        self.config_dir = self._get_config_directory()
        self.config_file = self.config_dir / "yt-dlp-gui-config.json"
        self._ensure_config_directory()
        self._default_settings = {
            "last_download_directory": "",
            "window_geometry": "",
            "last_format": "mp3",  # "mp3" or "mp4"
            "last_bitrate": "192Kbps",
            "last_quality": "720p",
            "last_playlist_mode": False,  # True for playlist, False for single video
            "last_format_var": 1  # 1 for MP3, 2 for MP4
        }
        
    def _get_config_directory(self) -> Path:
        """Get the project directory for configuration storage."""
        # Get the project root directory (go up from src/utils/)
        current_file = Path(__file__)
        project_root = current_file.parent.parent.parent  # Go up 3 levels: utils -> src -> project_root
        return project_root
    
    def _ensure_config_directory(self):
        """Ensure config directory exists (project root should already exist)."""
        try:
            # The project root should already exist, but we can check
            if not self.config_dir.exists():
                print(f"Warning: Project directory {self.config_dir} does not exist")
        except Exception as e:
            print(f"Warning: Could not verify config directory {self.config_dir}: {e}")
    
    def load_settings(self) -> Dict[str, Any]:
        """Load settings from config file."""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                # Merge with defaults to ensure all keys exist
                merged_settings = self._default_settings.copy()
                merged_settings.update(settings)
                return merged_settings
            else:
                return self._default_settings.copy()
        except Exception as e:
            print(f"Warning: Could not load settings from {self.config_file}: {e}")
            return self._default_settings.copy()
    
    def save_settings(self, settings: Dict[str, Any]):
        """Save settings to config file."""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Warning: Could not save settings to {self.config_file}: {e}")
    
    def get_last_download_directory(self) -> str:
        """Get the last used download directory."""
        settings = self.load_settings()
        last_dir = settings.get("last_download_directory", "")
        
        # Verify the directory still exists if it was previously set
        if last_dir and os.path.exists(last_dir) and os.path.isdir(last_dir):
            return last_dir
        
        # Return empty string if no valid directory was previously saved
        return ""
    
    def set_last_download_directory(self, directory: str):
        """Save the last used download directory."""
        if not directory or not os.path.exists(directory):
            return
        
        settings = self.load_settings()
        settings["last_download_directory"] = directory
        self.save_settings(settings)
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a specific setting value."""
        settings = self.load_settings()
        return settings.get(key, default)
    
    def set_setting(self, key: str, value: Any):
        """Set a specific setting value."""
        settings = self.load_settings()
        settings[key] = value
        self.save_settings(settings)
    
    def get_last_format_preferences(self) -> Dict[str, Any]:
        """Get the last used format preferences."""
        settings = self.load_settings()
        return {
            "format_var": settings.get("last_format_var", 1),
            "bitrate": settings.get("last_bitrate", "192Kbps"),
            "quality": settings.get("last_quality", "720p"),
            "playlist_mode": settings.get("last_playlist_mode", False)
        }
    
    def save_format_preferences(self, format_var: int, bitrate: str, quality: str, playlist_mode: bool):
        """Save format preferences."""
        settings = self.load_settings()
        settings["last_format_var"] = format_var
        settings["last_bitrate"] = bitrate
        settings["last_quality"] = quality
        settings["last_playlist_mode"] = playlist_mode
        self.save_settings(settings)


# Global settings manager instance
settings_manager = SettingsManager()
