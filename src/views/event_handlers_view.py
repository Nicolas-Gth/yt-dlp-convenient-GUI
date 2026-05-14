"""
Event handlers mixin for the main application view.

Contains all user interaction callbacks, input validation, tooltips,
widget state toggling (disable/enable during downloads), and
preference-saving logic.
"""
from PySide6.QtWidgets import QFileDialog, QMessageBox
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon

from config import DEFAULT_NORMALIZE_TARGET
from utils import settings_manager
from utils.i18n_utils import t


class EventHandlersMixin:
    """Mixin that provides event handler methods for MainApplicationView."""

    # ------------------------------------------------------------------
    # Widget state toggling (lock / unlock during download)
    # ------------------------------------------------------------------

    def disable_interactive_widgets(self):
        """Disable all interactive widgets during download."""
        self._widgets_locked = True
        for w in (self.url_entry, self.path_entry, self.quality_menu):
            w.setEnabled(False)
        for w in (self.mp3_radio, self.mp4_radio, self.opus_radio,
                  self.no_playlist_radio, self.yes_playlist_radio,
                  self.normalize_check, self.enrich_check, self.prevent_sleep_check):
            w.setEnabled(False)
        if hasattr(self, 'playlist_start_entry') and self.playlist_start_entry.isVisible():
            self.playlist_start_entry.setEnabled(False)
            self.playlist_end_entry.setEnabled(False)
        if hasattr(self, 'normalize_target_entry') and self.normalize_target_entry.isVisible():
            self.normalize_target_entry.setEnabled(False)
        if hasattr(self, 'template_entry'):
            self.template_entry.setEnabled(False)
        if hasattr(self, 'template_presets'):
            self.template_presets.setEnabled(False)

    def enable_interactive_widgets(self):
        """Re-enable all interactive widgets after download."""
        self._widgets_locked = False
        for w in (self.url_entry, self.path_entry, self.quality_menu):
            w.setEnabled(True)
        for w in (self.mp3_radio, self.mp4_radio, self.opus_radio,
                  self.no_playlist_radio, self.yes_playlist_radio,
                  self.normalize_check, self.enrich_check, self.prevent_sleep_check):
            w.setEnabled(True)
        if hasattr(self, 'playlist_start_entry') and self.playlist_start_entry.isVisible():
            self.playlist_start_entry.setEnabled(True)
            self.playlist_end_entry.setEnabled(True)
        if hasattr(self, 'normalize_target_entry') and self.normalize_target_entry.isVisible():
            self.normalize_target_entry.setEnabled(True)
        if hasattr(self, 'template_entry'):
            self.template_entry.setEnabled(True)
        if hasattr(self, 'template_presets'):
            self.template_presets.setEnabled(True)

    # ------------------------------------------------------------------
    # Stop / download-again
    # ------------------------------------------------------------------

    def _on_stop_click(self):
        """Handle stop button click."""
        if hasattr(self, 'stop_button'):
            self.stop_button.setEnabled(False)
            self.stop_button.setText(t("button.stopping"))
            self.stop_button.setIcon(QIcon())
            self.stop_button.setStyleSheet("""
                QPushButton { background-color: #666666; color: white; border: none;
                border-radius: 4px; padding: 8px 16px; }
            """)
        if self.on_stop_callback:
            self.on_stop_callback()

    def _on_download_again_click(self):
        """Handle 'New download' button click — return to start screen."""
        self.hide_progress_widgets()

    # ------------------------------------------------------------------
    # Browse / file dialog
    # ------------------------------------------------------------------

    def _on_browse_click(self):
        """Handle browse button click using Qt file dialog (translated)."""
        dlg = QFileDialog(self, t("path.dialog_title"), self.path_entry.text() or "")
        dlg.setFileMode(QFileDialog.FileMode.Directory)
        dlg.setOption(QFileDialog.Option.DontUseNativeDialog)
        dlg.setOption(QFileDialog.Option.ShowDirsOnly)
        # Override labels that Qt's built-in translations miss
        dlg.setLabelText(QFileDialog.DialogLabel.LookIn, t("dialog.look_in"))
        dlg.setLabelText(QFileDialog.DialogLabel.FileType, t("dialog.files_of_type"))
        if dlg.exec() == QFileDialog.DialogCode.Accepted:
            files = dlg.selectedFiles()
            if files:
                directory = files[0]
                self.path_entry.setText(directory)
                settings_manager.set_last_download_directory(directory)

        if self.on_browse_callback:
            self.on_browse_callback()

    # ------------------------------------------------------------------
    # Clear URL
    # ------------------------------------------------------------------

    def _clear_url_input(self):
        """Clear the URL input field."""
        self.url_entry.clear()
        self.url_entry.clearFocus()

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate_download_path(self) -> bool:
        """Validate that a download path has been selected."""
        path = self.path_entry.text().strip()
        return bool(path) and path != "Choose a path for your file"

    def _show_path_tooltip(self):
        """Show dialog indicating that a download path must be selected."""
        QMessageBox.warning(
            self,
            t("validation.path_required_title"),
            t("validation.path_required_msg")
        )

    def _validate_url(self) -> tuple:
        """Validate the URL and return (is_valid, error_message)."""
        url = self.url_entry.text().strip()
        if not url:
            return False, t("validation.url_empty")
        if not (url.startswith('http://') or url.startswith('https://')):
            return False, t("validation.url_invalid")
        return True, ""

    def _show_url_tooltip(self, error_message: str):
        """Show dialog with URL error message."""
        QMessageBox.warning(self, t("validation.invalid_url_title"), error_message)

    def show_ytdlp_error(self, error_message: str):
        """Show yt-dlp error in a standard popup dialog."""
        clean_message = error_message.replace("ERROR: ", "").strip()
        QMessageBox.critical(self, t("validation.download_error_title"), clean_message)

    # ------------------------------------------------------------------
    # Convert button handler
    # ------------------------------------------------------------------

    def _on_convert_click(self):
        if self.on_convert_callback:
            self.on_convert_callback()

    # ------------------------------------------------------------------
    # Format / playlist / option change handlers
    # ------------------------------------------------------------------

    def _save_preferences(self):
        """Save all format preferences to settings."""
        settings_manager.save_format_preferences(
            format_var=self.format_group.checkedId(),
            bitrate=self._mp3_bitrate_var,
            opus_bitrate=self._opus_bitrate_var,
            quality=self._get_current_quality(),
            playlist_mode=(self.yes_playlist_radio.isChecked()),
            playlist_start=self.playlist_start_entry.value(),
            playlist_end=self.playlist_end_entry.value(),
            normalize_volume=self.normalize_check.isChecked(),
            normalize_target=self._get_normalize_target(),
            enrich_metadata=self.enrich_check.isChecked(),
            prevent_sleep=self.prevent_sleep_check.isChecked(),
            output_template=self.template_entry.text().strip() if hasattr(self, 'template_entry') else ""
        )

    def _get_current_bitrate(self) -> str:
        """Get the current bitrate selection."""
        if self.mp4_radio.isChecked():
            return self._mp3_bitrate_var
        return self.quality_menu.currentData() or (self._opus_bitrate_var if self.opus_radio.isChecked() else self._mp3_bitrate_var)

    def _get_current_quality(self) -> str:
        """Get the current quality selection."""
        if self.mp4_radio.isChecked():
            return self.quality_menu.currentData() or self._quality_var
        return self._quality_var

    def _on_mp3_selected(self):
        self.switch_to_bitrate_menu()
        self._save_preferences()
        if self.on_format_change_callback:
            self.on_format_change_callback("mp3")

    def _on_mp4_selected(self):
        self.switch_to_quality_menu()
        self._save_preferences()
        if self.on_format_change_callback:
            self.on_format_change_callback("mp4")

    def _on_opus_selected(self):
        self.switch_to_bitrate_menu()
        self._save_preferences()
        if self.on_format_change_callback:
            self.on_format_change_callback("opus")

    def _on_playlist_selected(self):
        self.show_playlist_options()
        self._save_preferences()
        if self.on_playlist_change_callback:
            self.on_playlist_change_callback(True)

    def _on_no_playlist_selected(self):
        self.hide_playlist_options()
        self._save_preferences()
        if self.on_playlist_change_callback:
            self.on_playlist_change_callback(False)

    def _on_normalize_toggled(self, checked):
        """Handle normalize checkbox toggle."""
        if checked:
            self.show_normalize_input()
        else:
            self.hide_normalize_input()
        self._save_preferences()

    def _get_normalize_target(self) -> float:
        """Get the normalize target value from the entry, with validation."""
        if hasattr(self, 'normalize_target_entry') and self.normalize_target_entry.isVisible():
            try:
                return float(self.normalize_target_entry.text())
            except ValueError:
                return DEFAULT_NORMALIZE_TARGET
        return self._normalize_target_var

    def _on_enrich_toggled(self, checked):
        """Handle enrich metadata checkbox toggle."""
        self._save_preferences()

    def _on_prevent_sleep_toggled(self, checked):
        """Handle prevent sleep checkbox toggle."""
        self._save_preferences()

    def _on_quality_or_bitrate_changed(self, index):
        """Handle quality/bitrate combo box change."""
        data = self.quality_menu.itemData(index)
        if data is None:
            return
        if self.mp4_radio.isChecked():
            self._quality_var = data
        elif self.opus_radio.isChecked():
            self._opus_bitrate_var = data
        else:
            self._mp3_bitrate_var = data
        self._save_preferences()

    def _on_playlist_range_changed(self):
        """Handle playlist start/end spinbox change."""
        self._save_preferences()

    def _on_template_text_changed(self, text):
        """Handle template text changes: validate, sync dropdown, and save."""
        self._validate_template_visual(text)

        # Sync dropdown selection to typed text
        if hasattr(self, 'template_presets'):
            self.template_presets.blockSignals(True)
            idx = self.template_presets.findData(text)
            if idx >= 0:
                self.template_presets.setCurrentIndex(idx)
            elif text.strip():
                # Custom text: select "Custom" (last item)
                self.template_presets.setCurrentIndex(self.template_presets.count() - 1)
            else:
                self.template_presets.setCurrentIndex(0)
            self.template_presets.blockSignals(False)

        self._save_preferences()

    def _on_template_preset_changed(self, index):
        """Handle template preset dropdown change."""
        if index < 0:
            return
        template_val = self.template_presets.itemData(index)
        if template_val:
            self.template_entry.blockSignals(True)
            self.template_entry.setText(template_val)
            self.template_entry.blockSignals(False)
            self._validate_template_visual(template_val)
        self._save_preferences()
