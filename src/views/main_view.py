"""
Main application view and GUI components.
"""
import tkinter as tk
from tkinter import filedialog, StringVar, IntVar
import tkinter.ttk as ttk
from ttkthemes import ThemedTk
from PIL import ImageTk
import datetime
import subprocess
import shutil
import os
from typing import Optional, Dict, Any

from config import (
    APP_TITLE, DEFAULT_WINDOW_SIZE, COLORS, DEFAULT_BITRATES, 
    DEFAULT_QUALITIES, DEFAULT_BITRATE, DEFAULT_QUALITY, ICON_PATH
)
from utils import get_platform_fonts, calculate_window_size, load_thumbnail, load_icon, settings_manager
from models import DownloadConfig, VideoInfo, PlaylistInfo


class MainApplicationView:
    """Main application window and GUI components."""
    
    def __init__(self):
        self.root = None
        self.setup_window()
        self.setup_fonts()
        self.setup_variables()
        self.setup_widgets()
        self.progress_widgets = {}
        
        # Callbacks (set by controller)
        self.on_browse_callback = None
        self.on_convert_callback = None
        self.on_format_change_callback = None
        self.on_playlist_change_callback = None
    
    def setup_window(self):
        """Initialize the main window."""
        self.root = ThemedTk(theme="equilux")
        self.root.title(APP_TITLE)
        self.root.geometry(f"{DEFAULT_WINDOW_SIZE['width']}x{DEFAULT_WINDOW_SIZE['height']}")
        self.root.configure(bg=COLORS['background'])
        self.root.resizable(False, False)
        
        # Set default background for all tk widgets
        self.root.option_add('*Background', COLORS['background'])
        self.root.option_add('*Foreground', COLORS['text_primary'])
        
        # Set application icon
        load_icon(ICON_PATH, self.root)
    
    def setup_fonts(self):
        """Configure fonts and styles."""
        self.fonts = get_platform_fonts()
        
        # Apply the default font
        self.root.option_add('*Font', self.fonts['default'])
        
        # Configure ttk styles
        self.style = ttk.Style()
        
        # Configure colors for all ttk widgets to match our theme
        self.style.configure('TLabel', 
                           font=self.fonts['default'],
                           background=COLORS['background'],
                           foreground=COLORS['text_primary'])
        
        self.style.configure('TButton', 
                           font=self.fonts['default'],
                           background=COLORS['background'],
                           foreground=COLORS['text_primary'])
        
        self.style.configure('TEntry', 
                           font=self.fonts['default'],
                           background=COLORS['background'],
                           foreground=COLORS['text_primary'])
        
        self.style.configure('TCombobox', 
                           font=self.fonts['default'],
                           background=COLORS['background'],
                           foreground=COLORS['text_primary'])
        
        self.style.configure('TRadiobutton', 
                           font=self.fonts['default'],
                           background=COLORS['background'],
                           foreground=COLORS['text_primary'])
        
        self.style.configure('TFrame', 
                           background=COLORS['background'])
        
        self.style.configure('TLabelframe', 
                           background=COLORS['background'])
        
        # Configure progress bar
        self.style.configure('TProgressbar',
                           background=COLORS['button_normal'],
                           troughcolor=COLORS['background'])
    
    def setup_variables(self):
        """Initialize tkinter variables."""
        self.folder_path = StringVar()
        self.url_var = StringVar()
        self.bitrate_var = StringVar()
        self.quality_var = StringVar()
        self.format_var = IntVar()
        self.playlist_var = IntVar()
        
        # Load saved preferences
        preferences = settings_manager.get_last_format_preferences()
        
        # Set values from preferences
        self.bitrate_var.set(preferences.get("bitrate", DEFAULT_BITRATE))
        self.quality_var.set(preferences.get("quality", DEFAULT_QUALITY))
        self.format_var.set(preferences.get("format_var", 1))  # MP3 by default
        # For playlist_var: 0 = Yes, 1 = No (inverted logic)
        self.playlist_var.set(0 if preferences.get("playlist_mode", False) else 1)
    
    def setup_widgets(self):
        """Create and layout all GUI widgets."""
        self.create_url_input()
        self.create_path_input()
        self.create_format_selection()
        self.create_playlist_selection()
        self.create_convert_button()
        self.create_disclaimer()
        
        # Adjust initial window size
        self.adjust_window_size()
    
    def create_url_input(self):
        """Create URL input field."""
        self.url_entry = ttk.Entry(self.root, width=74, textvariable=self.url_var)
        self.url_entry.insert(0, 'Enter a video URL')
        self.url_entry.bind("<FocusIn>", self._on_url_focus_in)
        self.url_entry.bind("<FocusOut>", self._on_url_focus_out)
        self.url_entry.grid(sticky=tk.W, row=0, column=0, pady=10, padx=5)
    
    def create_path_input(self):
        """Create path input and browse button."""
        self.frame0 = tk.LabelFrame(self.root, bg=COLORS['background'], border=0)
        self.frame0.grid(sticky=tk.W, row=1, column=0)
        
        self.path_entry = ttk.Entry(
            master=self.frame0, 
            textvariable=self.folder_path, 
            width=59
        )
        
        # Load the last used directory or set placeholder
        last_directory = settings_manager.get_last_download_directory()
        if last_directory:
            self.folder_path.set(last_directory)
        else:
            # Always show placeholder when no directory is saved
            self.path_entry.insert(0, 'Choose a path for your file')
            self.path_entry.bind("<FocusIn>", self._on_path_focus_in)
            self.path_entry.bind("<FocusOut>", self._on_path_focus_out)
        
        self.path_entry.grid(row=0, column=0, padx=5, pady=5)
        
        self.browse_button = ttk.Button(
            self.frame0, 
            text="Browse", 
            command=self._on_browse_click,
            cursor="hand2"
        )
        self.browse_button.grid(row=0, column=1)
    
    def create_format_selection(self):
        """Create file format selection widgets."""
        self.frame1 = tk.LabelFrame(self.root, bg=COLORS['background'], border=0)
        self.frame1.grid(sticky=tk.W, row=2, column=0)
        
        # Format label
        format_label = ttk.Label(self.frame1, text="  File output format :    ")
        format_label.grid(sticky=tk.W, row=0, column=0, pady=10)
        
        # MP3 radio button
        self.mp3_radio = ttk.Radiobutton(
            self.frame1, 
            text="Mp3", 
            command=self._on_mp3_selected,
            variable=self.format_var, 
            value=1, 
            cursor="hand2"
        )
        self.mp3_radio.grid(sticky=tk.W, row=0, column=1)
        
        # MP4 radio button
        self.mp4_radio = ttk.Radiobutton(
            self.frame1, 
            text="Mp4", 
            command=self._on_mp4_selected,
            variable=self.format_var, 
            value=2, 
            cursor="hand2"
        )
        self.mp4_radio.grid(row=0, column=3)
        
        # Create the appropriate menu based on saved format
        if self.format_var.get() == 1:  # MP3
            self.quality_menu = ttk.OptionMenu(
                self.frame1, 
                self.bitrate_var, 
                self.bitrate_var.get(), 
                *DEFAULT_BITRATES,
                command=self._on_bitrate_changed
            )
        else:  # MP4
            self.quality_menu = ttk.OptionMenu(
                self.frame1, 
                self.quality_var, 
                self.quality_var.get(), 
                *DEFAULT_QUALITIES,
                command=self._on_quality_changed
            )
        self.quality_menu.grid(row=0, column=4)
    
    def create_playlist_selection(self):
        """Create playlist selection widgets."""
        self.frame2 = tk.LabelFrame(self.root, bg=COLORS['background'], border=0)
        self.frame2.grid(sticky=tk.W, row=3, column=0)
        
        # Playlist label
        playlist_label = ttk.Label(self.frame2, text="  Playlist download :    ")
        playlist_label.grid(sticky=tk.W, row=0, column=0, pady=10)
        
        # No playlist radio button
        self.no_playlist_radio = ttk.Radiobutton(
            self.frame2, 
            text="No", 
            command=self._on_no_playlist_selected,
            variable=self.playlist_var, 
            value=1, 
            cursor="hand2"
        )
        self.no_playlist_radio.grid(row=0, column=1, padx=3)
        
        # Yes playlist radio button
        self.yes_playlist_radio = ttk.Radiobutton(
            self.frame2, 
            text="Yes", 
            command=self._on_playlist_selected,
            variable=self.playlist_var, 
            value=0, 
            cursor="hand2"
        )
        self.yes_playlist_radio.grid(sticky=tk.W, row=0, column=3, padx=5)
        
        # Show playlist options if playlist mode was previously selected
        if self.playlist_var.get() == 0:  # Playlist mode enabled
            self.show_playlist_options()
    
    def create_convert_button(self):
        """Create the main convert button."""
        self.convert_button = tk.Button(
            self.root, 
            text="Click here to launch download",
            font=("Bahnschrift", 12), 
            command=self._on_convert_click,
            border=0, 
            fg=COLORS['text_primary'], 
            bg=COLORS['button_normal'], 
            pady=5, 
            padx=10,
            activebackground=COLORS['button_active'],
            activeforeground=COLORS['text_secondary'], 
            cursor="hand2"
        )
        self.convert_button.grid(sticky=tk.W, row=4, column=0, pady=2, padx=110)
    
    def create_disclaimer(self):
        """Create the disclaimer text."""
        self.frame3 = tk.LabelFrame(self.root, bg=COLORS['background'], border=0)
        self.frame3.grid(sticky=tk.W, row=6, column=0)
        
        disclaimer_text = (
            "Legal Notice: This software is intended for downloading and converting YouTube content that is\n"
            "either copyright-free, licensed under Creative Commons, or for which you have explicit permission.\n"
            "Users are responsible for ensuring compliance with applicable copyright laws and YouTube's ToS.\n"
        )
        
        disclaimer_label = ttk.Label(
            self.frame3, 
            text=disclaimer_text,
            font=("Abadi Extra Light", 8, "italic"), 
            justify=tk.LEFT
        )
        disclaimer_label.grid(sticky=tk.W, row=0, column=0, padx=10, pady=8)
    
    def show_playlist_options(self):
        """Show playlist range selection widgets."""
        if hasattr(self, 'playlist_from_label'):
            return  # Already shown
        
        self.playlist_from_label = ttk.Label(self.frame2, text="                  From video ")
        self.playlist_from_label.grid(row=0, column=4, padx=2)
        
        self.playlist_start_entry = ttk.Entry(self.frame2, width=5)
        self.playlist_start_entry.insert(0, '...')
        self.playlist_start_entry.bind("<FocusIn>", lambda args: self.playlist_start_entry.delete('0', 'end'))
        self.playlist_start_entry.grid(row=0, column=5)
        
        self.playlist_to_label = ttk.Label(self.frame2, text=" to ")
        self.playlist_to_label.grid(row=0, column=6)
        
        self.playlist_end_entry = ttk.Entry(self.frame2, width=5)
        self.playlist_end_entry.insert(0, '...')
        self.playlist_end_entry.bind("<FocusIn>", lambda args: self.playlist_end_entry.delete('0', 'end'))
        self.playlist_end_entry.grid(row=0, column=7)
    
    def hide_playlist_options(self):
        """Hide playlist range selection widgets."""
        if hasattr(self, 'playlist_from_label'):
            self.playlist_from_label.destroy()
            self.playlist_start_entry.destroy()
            self.playlist_to_label.destroy()
            self.playlist_end_entry.destroy()
            
            del self.playlist_from_label
            del self.playlist_start_entry
            del self.playlist_to_label
            del self.playlist_end_entry
    
    def switch_to_quality_menu(self):
        """Switch from bitrate to quality menu (MP4)."""
        self.quality_menu.destroy()
        self.quality_menu = ttk.OptionMenu(
            self.frame1, 
            self.quality_var, 
            self.quality_var.get(), 
            *DEFAULT_QUALITIES,
            command=self._on_quality_changed
        )
        self.quality_menu.grid(row=0, column=4)
    
    def switch_to_bitrate_menu(self):
        """Switch from quality to bitrate menu (MP3)."""
        self.quality_menu.destroy()
        self.quality_menu = ttk.OptionMenu(
            self.frame1, 
            self.bitrate_var, 
            self.bitrate_var.get(), 
            *DEFAULT_BITRATES,
            command=self._on_bitrate_changed
        )
        self.quality_menu.grid(row=0, column=4)
    
    def show_progress_widgets(self, is_playlist: bool = False):
        """Show download progress widgets."""
        self.convert_button.destroy()
        
        # Create progress frame
        self.progress_frame = tk.LabelFrame(self.root, bg=COLORS['background'], border=0)
        self.progress_frame.grid(sticky=tk.W, row=5, column=0)
        
        # Song name label
        self.song_label = ttk.Label(self.progress_frame, text="", anchor="w", justify="left")
        self.song_label.grid(sticky=tk.W, row=0, column=0, pady=10, padx=7)
        
        # Thumbnail placeholder
        self.thumbnail_label = ttk.Label(self.progress_frame)
        self.thumbnail_label.grid(sticky=tk.W, row=1, column=0, pady=5, padx=7)
        
        # Video info label
        self.info_label = ttk.Label(self.progress_frame, text="", anchor="w", justify="left")
        self.info_label.grid(sticky=tk.W, row=1, column=0, pady=5, padx=74)
        
        # Video progress
        self.progress_label = ttk.Label(self.progress_frame, text="Video progress :", anchor="w", justify="left")
        self.progress_label.grid(sticky=tk.W, row=2, column=0, pady=0, padx=7)
        
        self.video_progress = ttk.Progressbar(
            self.progress_frame, 
            orient=tk.HORIZONTAL, 
            length=316, 
            mode='determinate'
        )
        self.video_progress.grid(sticky=tk.W, row=2, column=0, pady=0, padx=106)
        
        self.video_progress_percent = ttk.Label(
            self.progress_frame, 
            text=" 0.0%", 
            anchor="w", 
            justify="left"
        )
        self.video_progress_percent.grid(sticky=tk.W, row=2, column=0, pady=10, padx=424)
        
        # Total progress (for playlists)
        if is_playlist:
            self.total_progress_label = ttk.Label(
                self.progress_frame, 
                text="Total progress :", 
                anchor="w", 
                justify="left"
            )
            self.total_progress_label.grid(sticky=tk.W, row=3, column=0, pady=0, padx=7)
            
            self.total_progress = ttk.Progressbar(
                self.progress_frame, 
                orient=tk.HORIZONTAL, 
                length=316, 
                mode='determinate'
            )
            self.total_progress.grid(sticky=tk.W, row=3, column=0, pady=0, padx=106)
            
            self.total_progress_percent = ttk.Label(
                self.progress_frame, 
                text=" 0.0%", 
                anchor="w", 
                justify="left"
            )
            self.total_progress_percent.grid(sticky=tk.W, row=3, column=0, pady=10, padx=424)
            
            # Adjust window size for playlist
            self.adjust_window_size(extra_height=135)
        else:
            # Adjust window size for single video
            self.adjust_window_size(extra_height=100)
    
    def hide_progress_widgets(self):
        """Hide progress widgets and restore convert button."""
        if hasattr(self, 'progress_frame'):
            for widget in self.progress_frame.winfo_children():
                widget.destroy()
            self.progress_frame.grid_forget()
            del self.progress_frame
        
        # Recreate convert button
        self.create_convert_button()
        self.adjust_window_size()  # Reset to base size
    
    def update_progress_info(self, video_info: VideoInfo, song_name: str, is_playlist: bool = False):
        """Update progress display with video information."""
        if not hasattr(self, 'progress_frame'):
            return
        
        # Update song name
        self.song_label.configure(text=song_name)
        
        # Update video info
        info_text = (
            f"Title : \"{video_info.title}\"\n"
            f"Channel : \"{video_info.uploader}\"\n"
            f"Duration : {video_info.duration_formatted}"
        )
        self.info_label.configure(text=info_text)
        
        # Update thumbnail
        if video_info.thumbnail:
            thumbnail_size = (60, 60) if video_info.is_music else (100, 60)
            thumbnail = load_thumbnail(video_info.thumbnail, thumbnail_size, video_info.is_music)
            if thumbnail:
                photo = ImageTk.PhotoImage(thumbnail)
                self.thumbnail_label.configure(image=photo)
                self.thumbnail_label.image = photo  # Keep a reference
                
                # Adjust info label position based on thumbnail size
                padx = 74 if video_info.is_music else 114
                self.info_label.grid_configure(padx=padx)
    
    def update_video_progress(self, percentage: float, status: str = ""):
        """Update video download progress."""
        if hasattr(self, 'video_progress'):
            if status == "processing":
                self.video_progress['mode'] = 'indeterminate'
                self.video_progress.start(10)
                self.video_progress_percent.configure(text="Processing")
            else:
                if self.video_progress['mode'] != 'determinate':
                    self.video_progress.stop()
                    self.video_progress['mode'] = 'determinate'
                
                self.video_progress['value'] = percentage
                self.video_progress_percent.configure(text=f" {percentage:.1f}%")
    
    def update_total_progress(self, percentage: float):
        """Update total progress for playlists."""
        if hasattr(self, 'total_progress'):
            self.total_progress['value'] = percentage
            if percentage >= 100:
                self.total_progress_percent.configure(text="Done")
            else:
                self.total_progress_percent.configure(text=f" {percentage:.1f}%")
    
    def adjust_window_size(self, extra_height: int = 0):
        """Adjust window size based on content."""
        width, height = calculate_window_size(extra_height=extra_height)
        self.root.geometry(f"{width}x{height}")
    
    def get_download_config(self) -> DownloadConfig:
        """Create DownloadConfig from current UI state."""
        # Validate URL first
        url_valid, url_error = self._validate_url()
        if not url_valid:
            self._show_url_tooltip(url_error)
            return None
        
        # Validate download path
        if not self._validate_download_path():
            self._show_path_tooltip()
            return None
        
        config = DownloadConfig()
        config.url = self.url_var.get().strip()
        config.output_directory = self.folder_path.get()
        config.file_format = "mp3" if self.format_var.get() == 1 else "mp4"
        config.is_playlist = self.playlist_var.get() == 0
        
        # Save the output directory as the last used directory
        if config.output_directory and config.output_directory != 'Choose a path for your file':
            settings_manager.set_last_download_directory(config.output_directory)
        
        # Save all format preferences
        settings_manager.save_format_preferences(
            format_var=self.format_var.get(),
            bitrate=self.bitrate_var.get(),
            quality=self.quality_var.get(),
            playlist_mode=config.is_playlist
        )
        
        if config.file_format == "mp3":
            config.bitrate = self.bitrate_var.get().split("Kbps")[0]
        else:
            config.quality = self.quality_var.get().split("p")[0]
        
        if config.is_playlist and hasattr(self, 'playlist_start_entry'):
            try:
                config.playlist_start = int(self.playlist_start_entry.get())
                config.playlist_end = int(self.playlist_end_entry.get())
            except ValueError:
                config.playlist_start = 1
                config.playlist_end = 1
        
        return config
    
    def set_convert_button_text(self, text: str):
        """Update convert button text."""
        if hasattr(self, 'convert_button') and self.convert_button.winfo_exists():
            self.convert_button.configure(text=text)
    
    def set_convert_button_enabled(self, enabled: bool):
        """Enable or disable the convert button."""
        if hasattr(self, 'convert_button') and self.convert_button.winfo_exists():
            if enabled:
                self.convert_button.configure(
                    state='normal',
                    bg=COLORS['button_normal'],
                    cursor="hand2"
                )
            else:
                self.convert_button.configure(
                    state='disabled',
                    bg=COLORS['background'],
                    cursor="arrow"
                )
    
    def show_fetching_progress(self, is_playlist: bool = False):
        """Show fetching progress with indeterminate progress bar."""
        # Hide the convert button completely
        if hasattr(self, 'convert_button') and self.convert_button.winfo_exists():
            self.convert_button.grid_remove()
        
        # Create a progress frame where the button was
        self.fetching_frame = tk.LabelFrame(self.root, bg=COLORS['background'], border=0)
        self.fetching_frame.grid(sticky=tk.W, row=4, column=0, pady=2, padx=110)
        
        # Progress label
        self.fetching_label = ttk.Label(
            self.fetching_frame, 
            text="Retrieving information..." if not is_playlist else "Retrieving playlist information...",
            anchor="center", 
            justify="center"
        )
        self.fetching_label.grid(row=0, column=0, pady=5)
        
        # Indeterminate progress bar
        self.fetching_progress = ttk.Progressbar(
            self.fetching_frame, 
            orient=tk.HORIZONTAL, 
            length=300, 
            mode='indeterminate'
        )
        self.fetching_progress.grid(row=1, column=0, pady=5)
        self.fetching_progress.start(10)  # Start the animation
    
    def hide_fetching_progress(self):
        """Hide fetching progress widgets and restore convert button."""
        if hasattr(self, 'fetching_frame'):
            # Stop progress bar animation
            if hasattr(self, 'fetching_progress'):
                self.fetching_progress.stop()
            
            # Remove widgets
            for widget in self.fetching_frame.winfo_children():
                widget.destroy()
            self.fetching_frame.grid_forget()
            del self.fetching_frame
        
        # Restore the convert button
        if hasattr(self, 'convert_button') and self.convert_button.winfo_exists():
            self.convert_button.grid()
            self.set_convert_button_enabled(True)
    
    # Event handlers (to be connected to controller)
    def _get_native_directory_dialog(self):
        """Get directory using native KDE file dialog portal."""
        try:
            # Priority 1: Use kdialog with no timeout (let user take their time)
            if shutil.which('kdialog'):
                print("Using kdialog for native KDE file picker...")
                result = subprocess.run([
                    'kdialog', '--getexistingdirectory', 
                    os.path.expanduser('~'), 
                    '--title', 'Select Download Directory'
                ], capture_output=True, text=True)
                
                # If user cancelled (returncode 1), return None instead of falling back
                if result.returncode == 1:
                    print("User cancelled file dialog")
                    return None
                    
                if result.returncode == 0 and result.stdout.strip():
                    selected_dir = result.stdout.strip()
                    print(f"Selected directory via kdialog: {selected_dir}")
                    return selected_dir
            
            # Priority 2: Use zenity as fallback
            if shutil.which('zenity'):
                print("Using zenity as fallback...")
                result = subprocess.run([
                    'zenity', '--file-selection', '--directory',
                    '--title=Select Download Directory'
                ], capture_output=True, text=True)
                
                if result.returncode == 1:
                    print("User cancelled zenity dialog")
                    return None
                    
                if result.returncode == 0 and result.stdout.strip():
                    selected_dir = result.stdout.strip()
                    print(f"Selected directory via zenity: {selected_dir}")
                    return selected_dir
                
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"Native dialog error: {e}")
            
        # Only use tkinter as absolute last resort if user specifically wants it
        print("Falling back to tkinter dialog...")
        return filedialog.askdirectory(title="Select Download Directory")
    
    def _on_browse_click(self):
        print("Browse button clicked!")  # Debug log
        try:
            filename = self._get_native_directory_dialog()
            print(f"Selected directory: {filename}")  # Debug log
            if filename:  # Only set if user didn't cancel
                self.folder_path.set(filename)
                # Save the selected directory for future use
                settings_manager.set_last_download_directory(filename)
                print(f"Path set to: {self.folder_path.get()}")  # Debug log
        except Exception as e:
            print(f"Error in browse click: {e}")  # Debug log
        
        if self.on_browse_callback:
            self.on_browse_callback()
    
    def _on_path_focus_in(self, event):
        """Handle path entry focus in - clear placeholder if needed."""
        if self.folder_path.get() == 'Choose a path for your file':
            self.path_entry.delete('0', 'end')
    
    def _on_path_focus_out(self, event):
        """Handle path entry focus out - restore placeholder if empty."""
        if not self.folder_path.get().strip():
            self.path_entry.delete('0', 'end')
            self.path_entry.insert(0, 'Choose a path for your file')
    
    def _on_url_focus_in(self, event):
        """Handle URL entry focus in - clear placeholder if needed."""
        if self.url_var.get() == 'Enter a video URL':
            self.url_entry.delete('0', 'end')
    
    def _on_url_focus_out(self, event):
        """Handle URL entry focus out - restore placeholder if empty."""
        if not self.url_var.get().strip():
            self.url_entry.delete('0', 'end')
            self.url_entry.insert(0, 'Enter a video URL')
    
    def _validate_download_path(self) -> bool:
        """Validate that a download path has been selected."""
        path = self.folder_path.get()
        return path and path != 'Choose a path for your file' and path.strip() != ""
    
    def _show_path_tooltip(self):
        """Show tooltip indicating that a download path must be selected."""
        # Create a simple tooltip-like message
        import tkinter.messagebox as messagebox
        messagebox.showwarning(
            "Path Required", 
            "Please select a download directory before starting the download.\n\nClick the 'Browse' button to choose a folder."
        )
    
    def _validate_url(self) -> tuple[bool, str]:
        """Validate the URL and return (is_valid, error_message)."""
        url = self.url_var.get().strip()
        
        if not url or url == 'Enter a video URL':
            return False, "Please enter a video URL before starting the download."
        
        # Basic URL validation
        if not (url.startswith('http://') or url.startswith('https://')):
            return False, "Please enter a valid URL starting with http:// or https://"
        
        return True, ""
    
    def _show_url_tooltip(self, error_message: str):
        """Show tooltip with URL error message."""
        import tkinter.messagebox as messagebox
        messagebox.showwarning("Invalid URL", error_message)
    
    def show_ytdlp_error(self, error_message: str):
        """Show yt-dlp error in a tooltip/messagebox."""
        import tkinter.messagebox as messagebox
        # Clean up the error message for better presentation
        clean_message = error_message.replace("ERROR: ", "").strip()
        messagebox.showerror("Download Error", clean_message)
    
    def _on_convert_click(self):
        if self.on_convert_callback:
            self.on_convert_callback()
    
    def _on_mp3_selected(self):
        self.switch_to_bitrate_menu()
        # Save the format preference immediately
        settings_manager.save_format_preferences(
            format_var=1,
            bitrate=self.bitrate_var.get(),
            quality=self.quality_var.get(),
            playlist_mode=(self.playlist_var.get() == 0)
        )
        if self.on_format_change_callback:
            self.on_format_change_callback("mp3")
    
    def _on_mp4_selected(self):
        self.switch_to_quality_menu()
        # Save the format preference immediately
        settings_manager.save_format_preferences(
            format_var=2,
            bitrate=self.bitrate_var.get(),
            quality=self.quality_var.get(),
            playlist_mode=(self.playlist_var.get() == 0)
        )
        if self.on_format_change_callback:
            self.on_format_change_callback("mp4")
    
    def _on_playlist_selected(self):
        self.show_playlist_options()
        # Save the playlist preference immediately
        settings_manager.save_format_preferences(
            format_var=self.format_var.get(),
            bitrate=self.bitrate_var.get(),
            quality=self.quality_var.get(),
            playlist_mode=True
        )
        if self.on_playlist_change_callback:
            self.on_playlist_change_callback(True)
    
    def _on_no_playlist_selected(self):
        self.hide_playlist_options()
        # Save the playlist preference immediately
        settings_manager.save_format_preferences(
            format_var=self.format_var.get(),
            bitrate=self.bitrate_var.get(),
            quality=self.quality_var.get(),
            playlist_mode=False
        )
        if self.on_playlist_change_callback:
            self.on_playlist_change_callback(False)
    
    def _on_bitrate_changed(self, selected_value):
        """Handle bitrate selection change."""
        # Save the bitrate preference immediately
        settings_manager.save_format_preferences(
            format_var=self.format_var.get(),
            bitrate=selected_value,
            quality=self.quality_var.get(),
            playlist_mode=(self.playlist_var.get() == 0)
        )
    
    def _on_quality_changed(self, selected_value):
        """Handle quality selection change."""
        # Save the quality preference immediately
        settings_manager.save_format_preferences(
            format_var=self.format_var.get(),
            bitrate=self.bitrate_var.get(),
            quality=selected_value,
            playlist_mode=(self.playlist_var.get() == 0)
        )
    
    def run(self):
        """Start the main event loop."""
        self.root.mainloop()
