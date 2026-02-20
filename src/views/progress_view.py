"""
Progress display mixin for the main application view.

Contains all progress-related UI: download progress bars, ETA,
thumbnails, normalize feedback, skipped entries, and fetching progress.
"""
import tkinter as tk
import tkinter.ttk as ttk
from PIL import ImageTk

from config import COLORS
from utils import load_thumbnail
from models import VideoInfo


class ProgressMixin:
    """Mixin that provides progress display methods for MainApplicationView."""

    # ------------------------------------------------------------------
    # Download progress widgets
    # ------------------------------------------------------------------

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
        self.stop_button.grid(row=7, column=0, pady=(8, 2))

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
            length=300,
            mode='determinate'
        )
        self.video_progress.grid(sticky=tk.W, row=2, column=0, pady=0, padx=120)

        self.video_progress_percent = ttk.Label(
            self.progress_frame,
            text=" 0.0%",
            anchor="w",
            justify="left"
        )
        self.video_progress_percent.grid(sticky=tk.W, row=2, column=0, pady=10, padx=(422, 0))

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
                length=300,
                mode='determinate'
            )
            self.total_progress.grid(sticky=tk.W, row=3, column=0, pady=0, padx=120)

            self.total_progress_percent = ttk.Label(
                self.progress_frame,
                text=" 0.0%",
                anchor="w",
                justify="left"
            )
            self.total_progress_percent.grid(sticky=tk.W, row=3, column=0, pady=10, padx=(422, 0))

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

    # ------------------------------------------------------------------
    # Download-again button
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # ETA management
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Progress updates
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Skipped entries panel
    # ------------------------------------------------------------------

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
            suffix = '  [Age-restricted]' if entry.get('age_restricted') else ''
            if channel:
                lines.append(f"{i}. {channel} - {title}{suffix}")
            else:
                lines.append(f"{i}. {title}{suffix}")

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

    def show_age_restricted_entries(self, entries: list):
        """Show age-restricted entries in the skipped unavailable elements panel.

        If the skipped panel already exists, appends to it. Otherwise creates it.
        Format: \"channel - title  [Age-restricted]\"
        """
        if not entries:
            return

        # Build entries in the same format as hidden_entries for show_skipped_entries
        formatted = []
        for entry in entries:
            title = entry.get('title', 'Unknown')
            channel = entry.get('channel', '')
            if channel:
                formatted.append({'title': title, 'channel': channel, 'age_restricted': True})
            else:
                formatted.append({'title': title, 'channel': '', 'age_restricted': True})

        if hasattr(self, '_skipped_frame') and hasattr(self, '_skipped_text'):
            # Append to existing skipped panel
            self._skipped_text.configure(state='normal')
            current_lines = int(self._skipped_text.index('end-1c').split('.')[0])
            for entry in formatted:
                title = entry['title']
                channel = entry['channel']
                if channel:
                    line = f"{current_lines}. {channel} - {title}  [Age-restricted]"
                else:
                    line = f"{current_lines}. {title}  [Age-restricted]"
                self._skipped_text.insert('end', f"\n{line}")
                current_lines += 1
            new_height = int(self._skipped_text.index('end-1c').split('.')[0])
            self._skipped_text.configure(height=new_height)
            self._skipped_text.configure(state='disabled')
            self.adjust_window_size()
        else:
            # Create the skipped panel with age-restricted entries
            self.show_skipped_entries(formatted)

    # ------------------------------------------------------------------
    # Normalize feedback (per-track summary)
    # ------------------------------------------------------------------

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

        # Only resize window when the visible area is still growing
        if count <= MAX_VISIBLE:
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

    # ------------------------------------------------------------------
    # Fetching progress (pre-download info retrieval)
    # ------------------------------------------------------------------

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
