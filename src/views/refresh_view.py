"""
Refresh mixin — palette & translation updates for dynamically-created widgets.
"""
from PySide6.QtCore import Qt

from utils.i18n_utils import t


class RefreshMixin:
    """Mixin that handles theme palette and language refresh for tables."""

    def refresh_table_theme(self):
        """Force table widgets to pick up the new palette colours."""
        for attr in ('info_table', '_normalize_table', '_skipped_table', '_files_table', '_files_meta', '_play_btn', '_lyrics_edit', '_elapsed_label', '_total_label', '_edit_reset_btn', '_edit_save_btn', '_edit_btn_bar'):
            widget = getattr(self, attr, None)
            if widget is not None:
                sheet = widget.styleSheet()
                widget.setStyleSheet("")
                widget.setStyleSheet(sheet)
                widget.update()
        # Refresh play/pause icon for current theme
        if hasattr(self, '_play_btn') and self._play_btn is not None:
            if hasattr(self, '_media_player') and self._media_player is not None:
                from PySide6.QtMultimedia import QMediaPlayer
                is_playing = self._media_player.playbackState() == QMediaPlayer.PlayingState
                self._update_play_icon(is_playing)

    def refresh_table_translation(self):
        """Update table headers and cell content after a language change."""
        # ── info_table : row headers (column 0) ──
        if hasattr(self, 'info_table') and self.info_table is not None:
            if hasattr(self, '_info_row_playlist') and self._info_row_playlist >= 0:
                self.info_table.item(self._info_row_playlist, 0).setText(
                    t("progress.info.playlist"))
            for row, key in [
                (getattr(self, '_info_row_title', 1), "progress.info.title"),
                (getattr(self, '_info_row_author', 2), "progress.info.author"),
                (getattr(self, '_info_row_duration', 3), "progress.info.duration"),
            ]:
                item = self.info_table.item(row, 0)
                if item:
                    item.setText(t(key))

        # ── _normalize_table ──
        if hasattr(self, '_normalize_table') and self._normalize_table is not None:
            self._normalize_table.setHorizontalHeaderLabels([
                t("progress.table.number"),
                t("progress.table.artist"),
                t("progress.table.title"),
                t("progress.table.metadatas"),
                t("progress.table.lyrics"),
                t("progress.table.norm"),
            ])
            # Cell content — columns 3 (metadatas), 4 (lyrics), 5 (norm) use t()
            for r in range(self._normalize_table.rowCount()):
                for c in (3, 4, 5):
                    item = self._normalize_table.item(r, c)
                    key = item.data(Qt.UserRole) if item else None
                    if key:
                        item.setText(t(key))

        # ── _skipped_table ──
        if hasattr(self, '_skipped_table') and self._skipped_table is not None:
            self._skipped_table.setHorizontalHeaderLabels([
                "#",
                t("progress.table.artist"),
                t("progress.table.title"),
                t("progress.table.reason"),
            ])
            # Cell content — reason column (3) uses t()
            for r in range(self._skipped_table.rowCount()):
                item = self._skipped_table.item(r, 3)
                key = item.data(Qt.UserRole) if item else None
                if key:
                    item.setText(t(key))

        # ── Group-box titles ──
        if hasattr(self, '_skipped_group') and self._skipped_group is not None:
            self._skipped_group.setTitle(t("progress.skipped_header"))
        if hasattr(self, 'normalize_outer_frame') and self.normalize_outer_frame is not None:
            key = "progress.downloaded_element" \
                if getattr(self, '_info_item_count', 0) == 1 \
                else "progress.downloaded_elements"
            self.normalize_outer_frame.setTitle(t(key))

        # ── Stop / New-download button ──
        if hasattr(self, 'stop_button') and self.stop_button is not None:
            self.stop_button.setText(" " + t("button.stop"))
        if hasattr(self, 'convert_button') and self.convert_button is not None:
            if getattr(self, '_new_download_mode', False):
                self.convert_button.setText(" " + t("button.new_download"))
            elif not self.convert_button.isHidden():
                self.convert_button.setText(" " + t("button.download"))

        # Files tab
        if hasattr(self, 'retranslate_files_tab'):
            self.retranslate_files_tab()
