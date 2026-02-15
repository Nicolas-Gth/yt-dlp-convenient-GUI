"""
Main application view and GUI components.
"""
import tkinter as tk
from tkinter import filedialog, StringVar, IntVar, DoubleVar, BooleanVar
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
    DEFAULT_QUALITIES, DEFAULT_BITRATE, DEFAULT_QUALITY, ICON_PATH,
    DEFAULT_NORMALIZE_TARGET, PLATFORM_SCALE
)
from utils import get_platform_fonts, load_thumbnail, load_icon, settings_manager
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
        self.on_stop_callback = None
    
    def setup_window(self):
        """Initialize the main window."""
        self.root = ThemedTk(theme="equilux")
        self.root.title(APP_TITLE)
        self.root.configure(bg=COLORS['background'])
        self.root.resizable(False, False)
        
        # Allow column 0 to expand so centered widgets work
        self.root.columnconfigure(0, weight=1)
        
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
        
        self.style.configure('TCheckbutton',
                           font=self.fonts['default'],
                           background=COLORS['background'],
                           foreground=COLORS['text_primary'])
        
        self.style.configure('TMenubutton',
                           background=COLORS['background'],
                           foreground=COLORS['text_primary'])
        
        self.style.configure('TSpinbox',
                           background=COLORS['background'],
                           fieldbackground=COLORS['background'],
                           foreground=COLORS['text_primary'])
        
        self.style.configure('TFrame', 
                           background=COLORS['background'])
        
        self.style.configure('TLabelframe', 
                           background=COLORS['background'])
        
        # Configure scrollbar
        self.style.configure('Vertical.TScrollbar',
                           background=COLORS['background'],
                           troughcolor=COLORS['background'],
                           bordercolor=COLORS['background'],
                           arrowcolor=COLORS['text_primary'])
        
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
        
        # Normalize volume variables
        self.normalize_var = BooleanVar(value=preferences.get("normalize_volume", False))
        self.normalize_target_var = DoubleVar(value=preferences.get("normalize_target", DEFAULT_NORMALIZE_TARGET))
        
        # Enrich metadata variable
        self.enrich_var = BooleanVar(value=preferences.get("enrich_metadata", False))
    
    def setup_widgets(self):
        """Create and layout all GUI widgets."""
        self.create_url_input()
        self.create_path_input()
        self.create_format_selection()
        self.create_playlist_selection()
        self.create_normalize_selection()
        self.create_enrich_selection()
        self.create_convert_button()
        self.create_disclaimer()
        
        # Adjust initial window size
        self.adjust_window_size()
    
    def create_url_input(self):
        """Create URL input field with clear button."""
        self.url_frame = tk.Frame(self.root, bg=COLORS['background'])
        self.url_frame.grid(sticky=tk.W, row=0, column=0, pady=10, padx=5)

        self.url_entry = ttk.Entry(self.url_frame, width=71, textvariable=self.url_var)
        self.url_entry.insert(0, 'Enter a video URL')
        self.url_entry.bind("<FocusIn>", self._on_url_focus_in)
        self.url_entry.bind("<FocusOut>", self._on_url_focus_out)
        self.url_entry.pack(side=tk.LEFT)

        self.url_clear_btn = tk.Button(
            self.url_frame, text="✕", font=("Arial", 10, "bold"),
            bg=COLORS['background'], fg=COLORS['text_primary'],
            activebackground=COLORS['background'], activeforeground="red",
            bd=0, padx=4, cursor="hand2",
            highlightthickness=0, highlightbackground=COLORS['background'],
            relief="flat",
            command=self._clear_url_input
        )
        self.url_clear_btn.pack(side=tk.LEFT, padx=(4, 0))
        self.url_clear_btn.bind("<Enter>", lambda e: self._show_tooltip(e, "Clear"))
        self.url_clear_btn.bind("<Leave>", lambda e: self._hide_tooltip())
    
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
    
    def create_normalize_selection(self):
        """Create volume normalization checkbox and target input."""
        self.frame_normalize = tk.LabelFrame(self.root, bg=COLORS['background'], border=0)
        self.frame_normalize.grid(sticky=tk.W, row=4, column=0)
        
        # Normalize checkbox
        self.normalize_check = ttk.Checkbutton(
            self.frame_normalize,
            text="  Normalize volume",
            variable=self.normalize_var,
            command=self._on_normalize_toggled,
            cursor="hand2"
        )
        self.normalize_check.grid(sticky=tk.W, row=0, column=0, padx=5, pady=5)
        
        # Show target input if previously enabled
        if self.normalize_var.get():
            self.show_normalize_input()
    
    def show_normalize_input(self):
        """Show the normalize target LUFS input."""
        if hasattr(self, 'normalize_target_label'):
            return  # Already shown
        
        self.normalize_target_label = ttk.Label(self.frame_normalize, text="  Target (LUFS) :")
        self.normalize_target_label.grid(row=0, column=1, padx=2)
        
        self.normalize_target_entry = ttk.Entry(self.frame_normalize, width=6)
        self.normalize_target_entry.insert(0, str(self.normalize_target_var.get()))
        self.normalize_target_entry.grid(row=0, column=2, padx=2)
        
        self.normalize_hint_label = ttk.Label(
            self.frame_normalize,
            text="(-14 recommended)",
            font=("Arial", 7, "italic")
        )
        self.normalize_hint_label.grid(row=0, column=3, padx=2)
    
    def hide_normalize_input(self):
        """Hide the normalize target LUFS input."""
        if hasattr(self, 'normalize_target_label'):
            self.normalize_target_label.destroy()
            self.normalize_target_entry.destroy()
            self.normalize_hint_label.destroy()
            del self.normalize_target_label
            del self.normalize_target_entry
            del self.normalize_hint_label
    
    def _on_normalize_toggled(self):
        """Handle normalize checkbox toggle."""
        if self.normalize_var.get():
            self.show_normalize_input()
        else:
            self.hide_normalize_input()
        
        # Save preference
        target = self._get_normalize_target()
        settings_manager.save_format_preferences(
            format_var=self.format_var.get(),
            bitrate=self.bitrate_var.get(),
            quality=self.quality_var.get(),
            playlist_mode=(self.playlist_var.get() == 0),
            normalize_volume=self.normalize_var.get(),
            normalize_target=target,
            enrich_metadata=self.enrich_var.get()
        )
    
    def _get_normalize_target(self) -> float:
        """Get the normalize target value from the entry, with validation."""
        if hasattr(self, 'normalize_target_entry'):
            try:
                return float(self.normalize_target_entry.get())
            except ValueError:
                return DEFAULT_NORMALIZE_TARGET
        return self.normalize_target_var.get()

    def create_enrich_selection(self):
        """Create metadata enrichment checkbox (HD cover + lyrics via MusicBrainz/LRCLIB)."""
        self.frame_enrich = tk.LabelFrame(self.root, bg=COLORS['background'], border=0)
        self.frame_enrich.grid(sticky=tk.W, row=5, column=0)
        
        self.enrich_check = ttk.Checkbutton(
            self.frame_enrich,
            text="  Enrich metadata (HD album cover + lyrics)",
            variable=self.enrich_var,
            command=self._on_enrich_toggled,
            cursor="hand2"
        )
        self.enrich_check.grid(sticky=tk.W, row=0, column=0, padx=5, pady=5)
        
        # Info label
        self.enrich_hint = ttk.Label(
            self.frame_enrich,
            text="via MusicBrainz, iTunes, LRCLIB, Genius",
            font=("Arial", 7, "italic")
        )
        self.enrich_hint.grid(row=0, column=1, padx=2)
    
    def _on_enrich_toggled(self):
        """Handle enrich metadata checkbox toggle."""
        target = self._get_normalize_target()
        settings_manager.save_format_preferences(
            format_var=self.format_var.get(),
            bitrate=self.bitrate_var.get(),
            quality=self.quality_var.get(),
            playlist_mode=(self.playlist_var.get() == 0),
            normalize_volume=self.normalize_var.get(),
            normalize_target=target,
            enrich_metadata=self.enrich_var.get()
        )

    def create_convert_button(self):
        """Create the main convert button."""
        self.convert_button = tk.Button(
            self.root, 
            text="Click here to launch download",
            font=("Bahnschrift", 12), 
            command=self._on_convert_click,
            border=0, 
            highlightthickness=0,
            fg=COLORS['text_primary'], 
            bg=COLORS['button_normal'], 
            pady=5, 
            padx=10,
            activebackground=COLORS['button_active'],
            activeforeground=COLORS['text_secondary'], 
            cursor="hand2"
        )
        self.convert_button.grid(row=6, column=0, pady=2)
    
    def create_disclaimer(self):
        """Create the disclaimer text."""
        self.frame3 = tk.LabelFrame(self.root, bg=COLORS['background'], border=0)
        self.frame3.grid(sticky=tk.W, row=8, column=0)
        
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
        
        self.playlist_start_var = tk.StringVar(value='1')
        self.playlist_start_entry = ttk.Spinbox(
            self.frame2, width=5, from_=1, to=9999, increment=1,
            textvariable=self.playlist_start_var,
            validate='key',
            validatecommand=(self.root.register(lambda v: v == '' or v.isdigit()), '%P')
        )
        self.playlist_start_entry.grid(row=0, column=5)
        
        self.playlist_to_label = ttk.Label(self.frame2, text=" to ")
        self.playlist_to_label.grid(row=0, column=6)
        
        self.playlist_end_var = tk.StringVar(value='999')
        self.playlist_end_entry = ttk.Spinbox(
            self.frame2, width=5, from_=1, to=9999, increment=1,
            textvariable=self.playlist_end_var,
            validate='key',
            validatecommand=(self.root.register(lambda v: v == '' or v.isdigit()), '%P')
        )
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
            if hasattr(self, 'playlist_start_var'):
                del self.playlist_start_var
            if hasattr(self, 'playlist_end_var'):
                del self.playlist_end_var
    
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
    
    def disable_interactive_widgets(self):
        """Disable all interactive widgets during download.
        
        For checkboxes and radiobuttons, we intercept click events
        instead of using 'disabled' state, because the equilux theme hides
        the checked indicator on disabled checkbuttons/radiobuttons.
        """
        self._widgets_locked = True
        
        # Truly disable entries, buttons, menus
        for attr in ('url_entry', 'path_entry', 'browse_button', 'quality_menu'):
            if hasattr(self, attr):
                try:
                    getattr(self, attr).configure(state='disabled')
                except Exception:
                    pass
        
        # For check/radio buttons: block interaction by intercepting clicks
        self._lock_bind_ids = {}
        lock_targets = [
            'mp3_radio', 'mp4_radio',
            'no_playlist_radio', 'yes_playlist_radio',
            'normalize_check', 'enrich_check',
        ]
        for attr in lock_targets:
            if hasattr(self, attr):
                w = getattr(self, attr)
                try:
                    bid = w.bind('<Button-1>', lambda e: 'break')
                    self._lock_bind_ids[attr] = bid
                    w.configure(cursor='arrow')
                except Exception:
                    pass
        
        # Disable playlist spinboxes if visible
        if hasattr(self, 'playlist_start_entry'):
            try:
                self.playlist_start_entry.configure(state='disabled')
                self.playlist_end_entry.configure(state='disabled')
            except Exception:
                pass
        # Disable normalize target entry if visible
        if hasattr(self, 'normalize_target_entry'):
            try:
                self.normalize_target_entry.configure(state='disabled')
            except Exception:
                pass

    def enable_interactive_widgets(self):
        """Re-enable all interactive widgets after download."""
        self._widgets_locked = False
        
        for attr in ('url_entry', 'path_entry', 'browse_button', 'quality_menu'):
            if hasattr(self, attr):
                try:
                    getattr(self, attr).configure(state='normal')
                except Exception:
                    pass
        
        # Remove click-blocking binds from check/radio buttons
        if hasattr(self, '_lock_bind_ids'):
            for attr, bid in self._lock_bind_ids.items():
                if hasattr(self, attr):
                    try:
                        getattr(self, attr).unbind('<Button-1>', bid)
                        getattr(self, attr).configure(cursor='hand2')
                    except Exception:
                        pass
            del self._lock_bind_ids
        
        if hasattr(self, 'playlist_start_entry'):
            try:
                self.playlist_start_entry.configure(state='normal')
                self.playlist_end_entry.configure(state='normal')
            except Exception:
                pass
        if hasattr(self, 'normalize_target_entry'):
            try:
                self.normalize_target_entry.configure(state='normal')
            except Exception:
                pass

    def show_progress_widgets(self, is_playlist: bool = False):
        """Show download progress widgets."""
        self.disable_interactive_widgets()
        self.convert_button.destroy()
        
        # Create progress frame where convert button was
        self.progress_frame = tk.LabelFrame(self.root, bg=COLORS['background'], border=0)
        self.progress_frame.grid(sticky=tk.W+tk.E, row=6, column=0)
        self.progress_frame.columnconfigure(0, weight=1)
        
        # Create stop button below progress frame, just above disclaimer
        self.stop_button = tk.Button(
            self.root,
            text="Stop download",
            font=("Bahnschrift", 12),
            command=self._on_stop_click,
            border=0,
            highlightthickness=0,
            fg=COLORS['text_primary'],
            bg="#a63333",
            pady=5,
            padx=10,
            activebackground="#c94444",
            activeforeground=COLORS['text_secondary'],
            cursor="hand2"
        )
        self.stop_button.grid(row=7, column=0, pady=2)
        
        # Song name label
        self.song_label = ttk.Label(self.progress_frame, text="", anchor="w", justify="left",
                                    font=("Arial", 9, "bold"))
        self.song_label.grid(sticky=tk.W, row=0, column=0, pady=(10, 0), padx=7)
        
        # Thumbnail placeholder
        self.thumbnail_label = ttk.Label(self.progress_frame)
        self.thumbnail_label.grid(sticky=tk.W, row=1, column=0, pady=5, padx=7)
        
        # Video info label
        self.info_label = ttk.Label(self.progress_frame, text="", anchor="w", justify="left")
        self.info_label.grid(sticky=tk.W, row=1, column=0, pady=5, padx=74)
        
        # Element progress
        self.progress_label = ttk.Label(self.progress_frame, text="Element progress :", anchor="w", justify="left")
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
            
            # ETA label (below total progress)
            self.eta_label = ttk.Label(
                self.progress_frame, text="", anchor="w", justify="left"
            )
            self.eta_label.grid(sticky=tk.W, row=4, column=0, pady=(0, 5), padx=7)
            self._eta_callback = None
            self._eta_timer_id = None
            self._start_eta_timer()
            
            # Adjust window size for playlist
            self.adjust_window_size()
        else:
            # Adjust window size for single video
            self.adjust_window_size()
    
    def hide_progress_widgets(self):
        """Hide progress widgets and restore convert button."""
        # Remove stop button
        if hasattr(self, 'stop_button') and self.stop_button.winfo_exists():
            self.stop_button.destroy()
            del self.stop_button
        
        # Stop ETA timer
        self._stop_eta_timer()
        
        if hasattr(self, '_skipped_frame'):
            self._skipped_frame.destroy()
            del self._skipped_frame
        
        if hasattr(self, 'progress_frame'):
            for widget in self.progress_frame.winfo_children():
                widget.destroy()
            self.progress_frame.grid_forget()
            del self.progress_frame
        
        # Clean up normalize scrollable frame if it exists
        if hasattr(self, 'normalize_outer_frame'):
            self.normalize_outer_frame.destroy()
            del self.normalize_outer_frame
            if hasattr(self, '_normalize_labels'):
                del self._normalize_labels
            if hasattr(self, '_normalize_canvas'):
                del self._normalize_canvas
            if hasattr(self, '_normalize_inner_frame'):
                del self._normalize_inner_frame
            if hasattr(self, '_scroll_area'):
                del self._scroll_area
            if hasattr(self, '_info_item_count'):
                del self._info_item_count
        
        # Recreate convert button
        self.create_convert_button()
        self.enable_interactive_widgets()
        self.adjust_window_size()  # Reset to base size
    
    def _on_stop_click(self):
        """Handle stop button click."""
        if hasattr(self, 'stop_button') and self.stop_button.winfo_exists():
            self.stop_button.configure(state='disabled', text="Stopping...", bg="#666666", cursor="arrow")
        if self.on_stop_callback:
            self.on_stop_callback()

    def show_download_again_button(self):
        """Transform the stop button into a 'Download again' button."""
        # Hide element/total progress bars
        for attr in ('progress_label', 'video_progress', 'video_progress_percent',
                      'total_progress_label', 'total_progress', 'total_progress_percent',
                      'eta_label'):
            widget = getattr(self, attr, None)
            if widget is not None:
                try:
                    widget.grid_remove()
                except Exception:
                    pass
        # Clear last element info (thumbnail, title details)
        for attr in ('thumbnail_label', 'info_label'):
            widget = getattr(self, attr, None)
            if widget is not None:
                try:
                    widget.grid_remove()
                except Exception:
                    pass
        if hasattr(self, 'stop_button') and self.stop_button.winfo_exists():
            self.stop_button.configure(
                state='normal',
                text="Download again",
                bg=COLORS['button_normal'],
                activebackground=COLORS['button_active'],
                cursor="hand2",
                command=self._on_download_again_click
            )
        # Resize window to fit remaining content
        self.adjust_window_size()

    def _on_download_again_click(self):
        """Handle 'Download again' button click — return to start screen."""
        self.hide_progress_widgets()
    
    def set_eta_callback(self, callback):
        """Set the callback used to compute the ETA string."""
        self._eta_callback = callback
    
    def _start_eta_timer(self):
        """Refresh the ETA label every second."""
        if hasattr(self, 'eta_label') and self.eta_label.winfo_exists():
            if callable(getattr(self, '_eta_callback', None)):
                eta_text = self._eta_callback()
                self.eta_label.configure(text=eta_text)
            self._eta_timer_id = self.root.after(1000, self._start_eta_timer)
    
    def _stop_eta_timer(self):
        """Stop the ETA refresh timer."""
        if hasattr(self, '_eta_timer_id') and self._eta_timer_id is not None:
            self.root.after_cancel(self._eta_timer_id)
            self._eta_timer_id = None
    
    def update_eta(self, eta_text: str):
        """Update the estimated remaining time label."""
        if hasattr(self, 'eta_label'):
            self.eta_label.configure(text=eta_text)
    
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
            thumbnail = load_thumbnail(video_info.thumbnail, (100, 60), video_info.is_music)
            if thumbnail:
                photo = ImageTk.PhotoImage(thumbnail)
                self.thumbnail_label.configure(image=photo)
                self.thumbnail_label.image = photo  # Keep a reference
                
                # Adjust info label position based on actual thumbnail size
                # If the thumbnail ended up square, it was cropped (music/black bars)
                is_square = abs(thumbnail.size[0] - thumbnail.size[1]) < 5
                padx = 74 if is_square else 114
                self.info_label.grid_configure(padx=padx)
        
        # Resize window to fit updated content
        self.adjust_window_size()
    
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
    
    def show_skipped_entries(self, hidden_entries: list):
        """Show a panel listing entries that YouTube hides but the API returned.

        Displayed above the 'Downloaded elements' section so the user can
        see which videos were skipped due to numbering offset.
        """
        if not hasattr(self, 'progress_frame') or not hidden_entries:
            return

        # Determine the row — place it after the last progress widget row
        next_row = len(self.progress_frame.grid_slaves()) + 5

        self._skipped_frame = tk.Frame(
            self.progress_frame, bg=COLORS['background']
        )
        self._skipped_frame.grid(
            sticky=tk.W + tk.E, row=next_row, column=0, padx=5, pady=2
        )

        # Header
        header = ttk.Label(
            self._skipped_frame,
            text="Skipped unavailable elements",
            font=("Arial", 9, "bold"),
            anchor="w",
            justify="left",
        )
        header.pack(anchor='w', padx=2, pady=(2, 0))

        sep = ttk.Separator(self._skipped_frame, orient='horizontal')
        sep.pack(fill='x', padx=2, pady=(1, 3))

        # Build text content
        lines = []
        for i, entry in enumerate(hidden_entries, start=1):
            title = entry.get('title', 'Unknown')
            channel = entry.get('channel', '')
            if channel:
                lines.append(f"{i}. {channel} - {title}")
            else:
                lines.append(f"{i}. {title}")
        
        # Selectable readonly text widget
        text_content = "\n".join(lines)
        num_lines = len(lines)
        self._skipped_text = tk.Text(
            self._skipped_frame,
            font=("Arial", 8),
            bg=COLORS['background'],
            fg=COLORS['text_primary'],
            relief='flat',
            borderwidth=0,
            highlightthickness=0,
            wrap='none',
            height=num_lines,
            cursor='arrow',
        )
        self._skipped_text.insert('1.0', text_content)
        self._skipped_text.configure(state='disabled')
        self._skipped_text.pack(anchor='w', padx=2, pady=1)

        self.adjust_window_size()

    def show_normalize_feedback(self, info: dict):
        """Show per-track summary feedback below the progress widgets.
        
        Each track gets one line combining: name, metadata, lyrics, volume.
        Displays up to 5 items directly. After 5, a scrollbar appears
        and the block stays at a fixed height.
        """
        if not hasattr(self, 'progress_frame'):
            return
        
        # Track item count for numbering
        if not hasattr(self, '_info_item_count'):
            self._info_item_count = 0
        self._info_item_count += 1
        num = self._info_item_count
        
        display_name = info.get('display_name', info.get('title', 'Unknown'))
        
        # Build parts list
        parts = []
        
        # Metadata status
        if info.get('metadata_found'):
            parts.append("Metadatas")
        elif info.get('type') == 'track_summary':
            parts.append("No metadatas")
        
        # Lyrics status
        if info.get('lyrics_found'):
            parts.append("Lyrics")
        elif info.get('type') == 'track_summary':
            parts.append("No lyrics")
        
        # Volume status
        volume = info.get('volume')
        if volume:
            measured = volume['measured']
            target = volume['target']
            diff = measured - target
            if diff > 0:
                parts.append(f"-{abs(diff):.1f} dB")
            else:
                parts.append(f"+{abs(diff):.1f} dB")
        
        separator = "  |  "
        feedback = f"{num}. {display_name}{separator}{separator.join(parts)}" if parts else f"{num}. {display_name}"
        
        MAX_VISIBLE = 5
        ITEM_HEIGHT = 22  # approximate height per label in pixels
        
        # Initialize the scrollable container on first call
        if not hasattr(self, '_normalize_labels'):
            self._normalize_labels = []
            
            # Determine the row for the normalize block (after progress widgets)
            next_row = len(self.progress_frame.grid_slaves()) + 5
            
            # Outer frame holds header + canvas + scrollbar
            self.normalize_outer_frame = tk.Frame(
                self.progress_frame, bg=COLORS['background']
            )
            self.normalize_outer_frame.grid(
                sticky=tk.W+tk.E, row=next_row, column=0, padx=5, pady=(2, 8)
            )
            
            # Header (fixed, does NOT scroll)
            header_lbl = ttk.Label(
                self.normalize_outer_frame,
                text="Downloaded elements",
                font=("Arial", 9, "bold"),
                anchor="w",
                justify="left"
            )
            header_lbl.pack(anchor='w', padx=2, pady=(2, 0))
            sep = ttk.Separator(self.normalize_outer_frame, orient='horizontal')
            sep.pack(fill='x', padx=2, pady=(1, 3))
            
            # Scrollable area frame (holds canvas + scrollbar side by side)
            self._scroll_area = tk.Frame(
                self.normalize_outer_frame, bg=COLORS['background']
            )
            self._scroll_area.pack(fill=tk.BOTH, expand=True)
            
            # Canvas for scrolling
            self._normalize_canvas = tk.Canvas(
                self._scroll_area,
                bg=COLORS['background'],
                highlightthickness=0,
                borderwidth=0
            )
            self._normalize_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            
            # Inner frame inside the canvas
            self._normalize_inner_frame = tk.Frame(
                self._normalize_canvas, bg=COLORS['background']
            )
            self._normalize_canvas_window = self._normalize_canvas.create_window(
                (0, 0), window=self._normalize_inner_frame, anchor='nw'
            )
            
            # Make inner frame stretch to canvas width
            self._normalize_canvas.bind('<Configure>', self._on_normalize_canvas_configure)
            
            # Scrollbar (hidden initially)
            self._normalize_scrollbar = ttk.Scrollbar(
                self._scroll_area,
                orient=tk.VERTICAL,
                command=self._normalize_canvas.yview
            )
            self._normalize_canvas.configure(yscrollcommand=self._normalize_scrollbar.set)
            
            # Bind resize
            self._normalize_inner_frame.bind('<Configure>', self._on_normalize_frame_configure)
            
            # Bind mousewheel for scrolling
            self._normalize_canvas.bind('<Enter>', self._bind_normalize_mousewheel)
            self._normalize_canvas.bind('<Leave>', self._unbind_normalize_mousewheel)
            
            # Selectable readonly text widget instead of labels
            self._normalize_text = tk.Text(
                self._normalize_inner_frame,
                font=("Arial", 8),
                bg=COLORS['background'],
                fg=COLORS['text_primary'],
                relief='flat',
                borderwidth=0,
                highlightthickness=0,
                wrap='none',
                height=1,
                cursor='arrow',
            )
            self._normalize_text.pack(anchor='w', padx=2, pady=1, fill='x')
            self._normalize_text.configure(state='disabled')
        
        # Append the new line to the text widget
        self._normalize_text.configure(state='normal')
        if len(self._normalize_labels) > 0:
            self._normalize_text.insert('end', f"\n{feedback}")
        else:
            self._normalize_text.insert('end', feedback)
        self._normalize_text.configure(state='disabled')
        self._normalize_labels.append(feedback)
        
        count = len(self._normalize_labels)
        
        # Update text widget height to match line count
        self._normalize_text.configure(state='normal')
        self._normalize_text.configure(height=count)
        self._normalize_text.configure(state='disabled')
        
        if count <= MAX_VISIBLE:
            # Grow canvas height to fit
            new_height = count * ITEM_HEIGHT
            self._normalize_canvas.configure(height=new_height)
        else:
            # Lock height at MAX_VISIBLE items and show scrollbar
            self._normalize_canvas.configure(height=MAX_VISIBLE * ITEM_HEIGHT)
            self._normalize_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Update scroll region and scroll to bottom
        self._normalize_canvas.update_idletasks()
        self._normalize_canvas.configure(scrollregion=self._normalize_canvas.bbox('all'))
        self._normalize_canvas.yview_moveto(1.0)
        
        # Refresh window size
        self.adjust_window_size()
    
    def _on_normalize_canvas_configure(self, event):
        """Stretch inner frame to match canvas width."""
        if hasattr(self, '_normalize_canvas_window'):
            self._normalize_canvas.itemconfigure(self._normalize_canvas_window, width=event.width)
    
    def _on_normalize_frame_configure(self, event):
        """Update scroll region when inner frame changes size."""
        if hasattr(self, '_normalize_canvas'):
            self._normalize_canvas.configure(scrollregion=self._normalize_canvas.bbox('all'))
    
    def _bind_normalize_mousewheel(self, event):
        """Bind mousewheel to normalize canvas."""
        if hasattr(self, '_normalize_canvas'):
            self._normalize_canvas.bind_all('<Button-4>', self._on_normalize_mousewheel_up)
            self._normalize_canvas.bind_all('<Button-5>', self._on_normalize_mousewheel_down)
    
    def _unbind_normalize_mousewheel(self, event):
        """Unbind mousewheel from normalize canvas."""
        if hasattr(self, '_normalize_canvas'):
            self._normalize_canvas.unbind_all('<Button-4>')
            self._normalize_canvas.unbind_all('<Button-5>')
    
    def _on_normalize_mousewheel_up(self, event):
        """Scroll up."""
        if hasattr(self, '_normalize_canvas'):
            self._normalize_canvas.yview_scroll(-1, 'units')
    
    def _on_normalize_mousewheel_down(self, event):
        """Scroll down."""
        if hasattr(self, '_normalize_canvas'):
            self._normalize_canvas.yview_scroll(1, 'units')
    
    def adjust_window_size(self, extra_height: int = 0):
        """Adjust window size to fit content automatically."""
        self.root.update_idletasks()
        req_width = self.root.winfo_reqwidth()
        req_height = self.root.winfo_reqheight() + extra_height
        # Clamp width between minimum and maximum
        width = max(req_width, PLATFORM_SCALE['width_base'])
        width = min(width, 560)  # Never wider than 560px
        # Reset geometry to allow shrinking, then set final size
        self.root.geometry("")
        self.root.update_idletasks()
        req_height = self.root.winfo_reqheight() + extra_height
        self.root.geometry(f"{width}x{req_height}")
    
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
        config.normalize_volume = self.normalize_var.get()
        config.normalize_target = self._get_normalize_target()
        config.enrich_metadata = self.enrich_var.get()
        
        # Save the output directory as the last used directory
        if config.output_directory and config.output_directory != 'Choose a path for your file':
            settings_manager.set_last_download_directory(config.output_directory)
        
        # Save all format preferences
        settings_manager.save_format_preferences(
            format_var=self.format_var.get(),
            bitrate=self.bitrate_var.get(),
            quality=self.quality_var.get(),
            playlist_mode=config.is_playlist,
            normalize_volume=config.normalize_volume,
            normalize_target=config.normalize_target,
            enrich_metadata=config.enrich_metadata
        )
        
        if config.file_format == "mp3":
            raw_bitrate = self.bitrate_var.get()
            config.bitrate = "best" if raw_bitrate == "Best" else raw_bitrate.split("Kbps")[0]
        else:
            raw_quality = self.quality_var.get()
            config.quality = "best" if raw_quality == "Best" else raw_quality.split("p")[0]
        
        if config.is_playlist and hasattr(self, 'playlist_start_entry'):
            try:
                start_val = self.playlist_start_entry.get().strip()
                end_val = self.playlist_end_entry.get().strip()
                config.playlist_start = int(start_val) if start_val else 1
                config.playlist_end = int(end_val) if end_val else 9999
                if config.playlist_end < config.playlist_start:
                    import tkinter.messagebox as messagebox
                    messagebox.showwarning(
                        "Invalid range",
                        f"The end value ({config.playlist_end}) cannot be less than the start value ({config.playlist_start})."
                    )
                    return None
            except ValueError:
                config.playlist_start = 1
                config.playlist_end = 9999
        
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
        """Show fetching progress bar (determinate for playlists, indeterminate for single videos)."""
        # Disable all interactive widgets
        self.disable_interactive_widgets()
        
        # Hide the convert button completely
        if hasattr(self, 'convert_button') and self.convert_button.winfo_exists():
            self.convert_button.grid_remove()
        
        # Create a progress frame where the button was
        self.fetching_frame = tk.LabelFrame(self.root, bg=COLORS['background'], border=0)
        self.fetching_frame.grid(sticky=tk.W, row=6, column=0, pady=2, padx=110)
        
        # Progress label
        self.fetching_label = ttk.Label(
            self.fetching_frame, 
            text="Retrieving information..." if not is_playlist else "Retrieving playlist information...",
            anchor="center", 
            justify="center"
        )
        self.fetching_label.grid(row=0, column=0, pady=5)
        
        # Progress bar: determinate for playlists, indeterminate for single videos
        if is_playlist:
            self.fetching_progress = ttk.Progressbar(
                self.fetching_frame, 
                orient=tk.HORIZONTAL, 
                length=300, 
                mode='determinate',
                maximum=100
            )
            self.fetching_progress.grid(row=1, column=0, pady=5)
        else:
            self.fetching_progress = ttk.Progressbar(
                self.fetching_frame, 
                orient=tk.HORIZONTAL, 
                length=300, 
                mode='indeterminate'
            )
            self.fetching_progress.grid(row=1, column=0, pady=5)
            self.fetching_progress.start(10)
    
    def update_fetching_progress(self, current: int, total: int = None):
        """Update the fetching progress bar and label for playlist extraction."""
        if not hasattr(self, 'fetching_label') or not hasattr(self, 'fetching_progress'):
            return
        
        if total and total > 0:
            percentage = (current / total) * 100
            self.fetching_progress['value'] = percentage
            self.fetching_label.configure(
                text=f"Retrieving playlist information... ({current}/{total})"
            )
        else:
            # Total unknown — show count only and pulse the bar
            self.fetching_label.configure(
                text=f"Retrieving playlist information... ({current} titles found)"
            )
            # Advance bar in small steps to show activity
            self.fetching_progress['value'] = min(current % 100, 95)
    
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
        
        # Re-enable all interactive widgets
        self.enable_interactive_widgets()
        
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

    def _clear_url_input(self):
        """Clear the URL input field and restore placeholder."""
        self.url_entry.delete('0', 'end')
        self.url_entry.insert(0, 'Enter a video URL')
        self.root.focus_set()

    def _show_tooltip(self, event, text: str):
        """Show a small tooltip near the widget on hover."""
        self._hide_tooltip()
        x = event.widget.winfo_rootx() + event.widget.winfo_width() // 2
        y = event.widget.winfo_rooty() + event.widget.winfo_height() + 4
        self._tooltip = tk.Toplevel(self.root)
        self._tooltip.wm_overrideredirect(True)
        self._tooltip.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            self._tooltip, text=text,
            bg="#222222", fg="white",
            font=("Arial", 9), padx=6, pady=2,
            relief="solid", borderwidth=1
        )
        label.pack()

    def _hide_tooltip(self):
        """Destroy the current tooltip if any."""
        tw = getattr(self, '_tooltip', None)
        if tw:
            tw.destroy()
            self._tooltip = None
    
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
            playlist_mode=(self.playlist_var.get() == 0),
            normalize_volume=self.normalize_var.get(),
            normalize_target=self._get_normalize_target(),
            enrich_metadata=self.enrich_var.get()
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
            playlist_mode=(self.playlist_var.get() == 0),
            normalize_volume=self.normalize_var.get(),
            normalize_target=self._get_normalize_target(),
            enrich_metadata=self.enrich_var.get()
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
            playlist_mode=True,
            normalize_volume=self.normalize_var.get(),
            normalize_target=self._get_normalize_target(),
            enrich_metadata=self.enrich_var.get()
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
            playlist_mode=False,
            normalize_volume=self.normalize_var.get(),
            normalize_target=self._get_normalize_target(),
            enrich_metadata=self.enrich_var.get()
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
            playlist_mode=(self.playlist_var.get() == 0),
            normalize_volume=self.normalize_var.get(),
            normalize_target=self._get_normalize_target(),
            enrich_metadata=self.enrich_var.get()
        )
    
    def _on_quality_changed(self, selected_value):
        """Handle quality selection change."""
        # Save the quality preference immediately
        settings_manager.save_format_preferences(
            format_var=self.format_var.get(),
            bitrate=self.bitrate_var.get(),
            quality=selected_value,
            playlist_mode=(self.playlist_var.get() == 0),
            normalize_volume=self.normalize_var.get(),
            normalize_target=self._get_normalize_target(),
            enrich_metadata=self.enrich_var.get()
        )
    
    def run(self):
        """Start the main event loop."""
        self.root.mainloop()
