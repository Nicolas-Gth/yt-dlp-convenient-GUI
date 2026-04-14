"""
Event handlers mixin for the main application view.

Contains all user interaction callbacks, input validation, tooltips,
widget state toggling (disable/enable during downloads), and
preference-saving logic.
"""
import tkinter as tk
from tkinter import filedialog
import subprocess
import shutil
import os

from config import DEFAULT_NORMALIZE_TARGET
from utils import settings_manager


class EventHandlersMixin:
    """Mixin that provides event handler methods for MainApplicationView."""

    # ------------------------------------------------------------------
    # Widget state toggling (lock / unlock during download)
    # ------------------------------------------------------------------

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
            'mp3_radio', 'mp4_radio', 'opus_radio',
            'no_playlist_radio', 'yes_playlist_radio',
            'normalize_check', 'enrich_check',
            'prevent_sleep_check',
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

    # ------------------------------------------------------------------
    # Stop / download-again
    # ------------------------------------------------------------------

    def _on_stop_click(self):
        """Handle stop button click."""
        if hasattr(self, 'stop_button') and self.stop_button.winfo_exists():
            self.stop_button.configure(state='disabled', text="Stopping...", bg="#666666", cursor="arrow")
        if self.on_stop_callback:
            self.on_stop_callback()

    def _on_download_again_click(self):
        """Handle 'New download' button click — return to start screen."""
        self.hide_progress_widgets()

    # ------------------------------------------------------------------
    # Browse / file dialog
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Focus handlers (placeholders)
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Tooltips
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate_download_path(self) -> bool:
        """Validate that a download path has been selected."""
        path = self.folder_path.get()
        return path and path != 'Choose a path for your file' and path.strip() != ""

    def _show_path_tooltip(self):
        """Show tooltip indicating that a download path must be selected."""
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
        """Show yt-dlp error in a standard popup dialog."""
        import tkinter.messagebox as messagebox
        clean_message = error_message.replace("ERROR: ", "").strip()
        messagebox.showerror("Download Error", clean_message)

    # ------------------------------------------------------------------
    # Convert button handler
    # ------------------------------------------------------------------

    def _on_convert_click(self):
        if self.on_convert_callback:
            self.on_convert_callback()

    # ------------------------------------------------------------------
    # Format / playlist / option change handlers
    # ------------------------------------------------------------------

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
            enrich_metadata=self.enrich_var.get(),
            prevent_sleep=self.prevent_sleep_var.get()
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
            enrich_metadata=self.enrich_var.get(),
            prevent_sleep=self.prevent_sleep_var.get()
        )
        if self.on_format_change_callback:
            self.on_format_change_callback("mp4")

    def _on_opus_selected(self):
        self.bitrate_var.set("Max 128Kbps")
        self.switch_to_bitrate_menu()
        # Save the format preference immediately
        settings_manager.save_format_preferences(
            format_var=3,
            bitrate=self.bitrate_var.get(),
            quality=self.quality_var.get(),
            playlist_mode=(self.playlist_var.get() == 0),
            normalize_volume=self.normalize_var.get(),
            normalize_target=self._get_normalize_target(),
            enrich_metadata=self.enrich_var.get(),
            prevent_sleep=self.prevent_sleep_var.get()
        )
        if self.on_format_change_callback:
            self.on_format_change_callback("opus")

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
            enrich_metadata=self.enrich_var.get(),
            prevent_sleep=self.prevent_sleep_var.get()
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
            enrich_metadata=self.enrich_var.get(),
            prevent_sleep=self.prevent_sleep_var.get()
        )
        if self.on_playlist_change_callback:
            self.on_playlist_change_callback(False)

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
            enrich_metadata=self.enrich_var.get(),
            prevent_sleep=self.prevent_sleep_var.get()
        )

    def _get_normalize_target(self) -> float:
        """Get the normalize target value from the entry, with validation."""
        if hasattr(self, 'normalize_target_entry'):
            try:
                return float(self.normalize_target_entry.get())
            except ValueError:
                return DEFAULT_NORMALIZE_TARGET
        return self.normalize_target_var.get()

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
            enrich_metadata=self.enrich_var.get(),
            prevent_sleep=self.prevent_sleep_var.get()
        )

    def _on_prevent_sleep_toggled(self):
        """Handle prevent sleep checkbox toggle."""
        target = self._get_normalize_target()
        settings_manager.save_format_preferences(
            format_var=self.format_var.get(),
            bitrate=self.bitrate_var.get(),
            quality=self.quality_var.get(),
            playlist_mode=(self.playlist_var.get() == 0),
            normalize_volume=self.normalize_var.get(),
            normalize_target=target,
            enrich_metadata=self.enrich_var.get(),
            prevent_sleep=self.prevent_sleep_var.get()
        )

    def _on_bitrate_changed(self, selected_value):
        """Handle bitrate selection change."""
        settings_manager.save_format_preferences(
            format_var=self.format_var.get(),
            bitrate=selected_value,
            quality=self.quality_var.get(),
            playlist_mode=(self.playlist_var.get() == 0),
            normalize_volume=self.normalize_var.get(),
            normalize_target=self._get_normalize_target(),
            enrich_metadata=self.enrich_var.get(),
            prevent_sleep=self.prevent_sleep_var.get()
        )

    def _on_quality_changed(self, selected_value):
        """Handle quality selection change."""
        settings_manager.save_format_preferences(
            format_var=self.format_var.get(),
            bitrate=self.bitrate_var.get(),
            quality=selected_value,
            playlist_mode=(self.playlist_var.get() == 0),
            normalize_volume=self.normalize_var.get(),
            normalize_target=self._get_normalize_target(),
            enrich_metadata=self.enrich_var.get(),
            prevent_sleep=self.prevent_sleep_var.get()
        )
