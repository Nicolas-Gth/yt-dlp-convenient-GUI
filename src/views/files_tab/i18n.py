from PySide6.QtCore import Qt

from utils.i18n_utils import t

from .metadata import _tag_label


class FilesI18nMixin:
    """Mixin that retranslates the files tab."""

    def retranslate_files_tab(self):
        """Update tab and table header labels after a language change."""
        idx = self.tabs.indexOf(self._files_tab)
        if idx >= 0:
            self.tabs.setTabText(idx, t("tabs.files"))
        if hasattr(self, '_files_table') and self._files_table is not None:
            self._files_table.setHorizontalHeaderLabels([
                t("files.filename"),
                t("files.title"),
                t("files.artist"),
                t("files.lyrics"),
            ])
            for r in range(self._files_table.rowCount()):
                item = self._files_table.item(r, 3)
                if item:
                    lyr_type = item.data(Qt.UserRole)
                    if lyr_type == 'lrc':
                        item.setText('LRC')
                    elif lyr_type == 'txt':
                        item.setText('Txt')
                    else:
                        item.setText(t("table.none"))
                    item.setText(t("table.none"))
        if hasattr(self, '_files_group') and self._files_group is not None:
            self._files_group.setTitle(t("files.group_title"))
        if hasattr(self, '_detail_group') and self._detail_group is not None:
            self._detail_group.setTitle(t("metadata.group_title"))
        if hasattr(self, '_edit_reset_btn') and self._edit_reset_btn is not None:
            self._edit_reset_btn.setText(t("button.reset"))
            self._edit_save_btn.setText(t("button.save"))
        if hasattr(self, '_lyrics_label') and self._lyrics_label is not None:
            self._lyrics_label.setText(t("files.lyrics"))
            self._lyrics_edit.setPlaceholderText(t("files.no_lyrics"))
        # Retranslate metadata keys (skip row 0 = filename)
        if hasattr(self, '_files_meta') and self._files_meta is not None:
            if self._files_meta.rowCount() > 0:
                self._files_meta.item(0, 0).setText(t("tag.filename"))
            for r in range(1, self._files_meta.rowCount()):
                item = self._files_meta.item(r, 0)
                if item:
                    raw_key = item.data(Qt.UserRole)
                    if raw_key:
                        item.setText(_tag_label(raw_key))
