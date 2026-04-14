"""
Widget creation mixin for the main application view.

Contains all create_* methods and related show/hide helpers for
URL input, path input, format selection, playlist options,
normalize options, enrich metadata, convert button, and disclaimer.
"""
import tkinter as tk
import tkinter.ttk as ttk

from config import COLORS, DEFAULT_BITRATES, DEFAULT_QUALITIES
from utils import settings_manager


class WidgetsMixin:
    """Mixin that provides widget creation methods for MainApplicationView."""

    def setup_widgets(self):
        """Create and layout all GUI widgets."""
        self.create_url_input()
        self.create_path_input()
        self.create_format_selection()
        self.create_playlist_selection()
        self.create_normalize_selection()
        self.create_enrich_selection()
        self.create_prevent_sleep_selection()
        self.create_convert_button()
        self.create_disclaimer()

        # Adjust initial window size
        self.adjust_window_size()

    # ------------------------------------------------------------------
    # URL input
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Path input
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Format selection
    # ------------------------------------------------------------------

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

        # Opus radio button
        self.opus_radio = ttk.Radiobutton(
            self.frame1,
            text="Opus",
            command=self._on_opus_selected,
            variable=self.format_var,
            value=3,
            cursor="hand2"
        )
        self.opus_radio.grid(row=0, column=5)

        # Create the appropriate menu based on saved format
        if self.format_var.get() == 2:  # MP4
            self.quality_menu = ttk.OptionMenu(
                self.frame1,
                self.quality_var,
                self.quality_var.get(),
                *DEFAULT_QUALITIES,
                command=self._on_quality_changed
            )
        else:  # MP3 or Opus (audio formats use bitrate)
            self.quality_menu = ttk.OptionMenu(
                self.frame1,
                self.bitrate_var,
                self.bitrate_var.get(),
                *DEFAULT_BITRATES,
                command=self._on_bitrate_changed
            )
        self.quality_menu.grid(row=0, column=6)

    # ------------------------------------------------------------------
    # Playlist selection
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Quality / bitrate menu switching
    # ------------------------------------------------------------------

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
        self.quality_menu.grid(row=0, column=6)

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
        self.quality_menu.grid(row=0, column=6)

    # ------------------------------------------------------------------
    # Normalize selection
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Enrich metadata selection
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Prevent sleep selection
    # ------------------------------------------------------------------

    def create_prevent_sleep_selection(self):
        """Create checkbox to prevent system sleep during downloads."""
        self.frame_prevent_sleep = tk.LabelFrame(self.root, bg=COLORS['background'], border=0)
        self.frame_prevent_sleep.grid(sticky=tk.W, row=6, column=0)

        self.prevent_sleep_check = ttk.Checkbutton(
            self.frame_prevent_sleep,
            text="  Prevent sleep during download",
            variable=self.prevent_sleep_var,
            command=self._on_prevent_sleep_toggled,
            cursor="hand2"
        )
        self.prevent_sleep_check.grid(sticky=tk.W, row=0, column=0, padx=5, pady=5)

    # ------------------------------------------------------------------
    # Convert button
    # ------------------------------------------------------------------

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
        self.convert_button.grid(row=7, column=0, pady=2)

    # ------------------------------------------------------------------
    # Disclaimer
    # ------------------------------------------------------------------

    def create_disclaimer(self):
        """Create the disclaimer text."""
        self.frame3 = tk.LabelFrame(self.root, bg=COLORS['background'], border=0)
        self.frame3.grid(sticky=tk.W, row=9, column=0)

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
