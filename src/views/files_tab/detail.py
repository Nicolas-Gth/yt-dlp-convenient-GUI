import os
import warnings

from PySide6.QtWidgets import QTableWidgetItem
from PySide6.QtCore import Qt, QTimer

from utils.i18n_utils import t

from .metadata import _load_audio, _extract_artwork, _extract_all_metadata, _extract_lyrics_text, _tag_label
from .constants import _FIELD_KEYS, _FIELD_LABELS


class FilesDetailMixin:
    """Mixin that populates the right-side detail panel."""

    def _clear_meta_panel(self):
        """Remove all rows and cell widgets from the metadata table."""
        for r in range(self._files_meta.rowCount()):
            if self._files_meta.cellWidget(r, 1):
                self._files_meta.removeCellWidget(r, 1)
        self._files_meta.setRowCount(0)

    def _show_empty_detail(self):
        if self._current_detail_filepath:
            return  # file has been selected since the timer was set
        self._files_meta.setRowCount(1)
        self._files_meta.setRowHeight(0, max(self._files_meta.viewport().height(), 60))
        item = QTableWidgetItem(t("files.no_selection"))
        item.setFlags(Qt.ItemIsEnabled)
        item.setTextAlignment(Qt.AlignCenter)
        self._files_meta.setItem(0, 0, item)
        self._files_meta.setSpan(0, 0, 1, 2)

    def _show_file_detail(self, filepath):
        """Populate the right panel with artwork and metadata."""
        if filepath is None or not os.path.isfile(filepath):
            self._clear_meta_panel()
            self._files_artwork.setArtwork(None)
            self._artwork_wrapper.hide()
            self._current_detail_filepath = None
            self._play_btn.setEnabled(False)
            self._seek_slider.setEnabled(False)
            self._seek_slider.setValue(0)
            self._elapsed_label.setText("0:00")
            self._total_label.setText("0:00")
            self._edit_btn_bar.hide()
            self._lyrics_label.hide()
            self._lyrics_edit.hide()
            QTimer.singleShot(0, self._show_empty_detail)
            return

        self._artwork_wrapper.show()

        if self._current_detail_filepath != filepath:
            self._media_player.stop()
            self._seek_slider.setValue(0)
        self._current_detail_filepath = filepath
        self._play_btn.setEnabled(True)
        self._seek_slider.setEnabled(True)

        audio = _load_audio(filepath)
        if audio is None:
            self._clear_meta_panel()
            self._files_artwork.setArtwork(None)
            return

        # Artwork
        pix = _extract_artwork(audio)
        self._files_artwork.setArtwork(pix if pix and not pix.isNull() else None)

        # Metadata table — clear old cell widgets first
        self._clear_meta_panel()
        self._modified_rows.clear()
        self._edited = False
        self._edit_btn_bar.hide()
        self._files_meta.blockSignals(True)

        # Extract values for always-shown fields
        meta_dict = {}
        for k, v in _extract_all_metadata(audio):
            meta_dict[k] = v

        fixed = []
        for field_name in ('title', 'artist', 'album', 'year', 'tracknumber', 'genre'):
            val = ''
            raw_key = ''
            for candidate in _FIELD_KEYS[field_name]:
                if candidate in meta_dict and meta_dict[candidate]:
                    val = meta_dict[candidate]
                    raw_key = candidate
                    break
            fixed.append((field_name, raw_key, val))
            # Remove from meta_dict so they don't appear twice
            for candidate in _FIELD_KEYS[field_name]:
                meta_dict.pop(candidate, None)

        # Remaining tags (sorted alphabetically)
        remaining = sorted(meta_dict.items(), key=lambda r: r[0].lower())

        num_rows = 1 + len(fixed) + len(remaining)  # filename + fixed + remaining
        self._files_meta.setRowCount(num_rows)

        row = 0
        # Filename
        self._files_meta.setRowHeight(row, 22)
        ki = QTableWidgetItem(t("tag.filename"))
        ki.setFlags(Qt.NoItemFlags); f = ki.font(); f.setBold(True); ki.setFont(f)
        self._files_meta.setItem(row, 0, ki)
        vi = QTableWidgetItem(os.path.basename(filepath))
        vi.setFlags(Qt.ItemIsEnabled | Qt.ItemIsEditable)
        vi.setData(Qt.UserRole, '_filename_')
        self._files_meta.setItem(row, 1, vi)
        row += 1

        # Fixed fields
        for field_name, raw_key, val in fixed:
            self._files_meta.setRowHeight(row, 22)
            ki = QTableWidgetItem(t(_FIELD_LABELS[field_name]))
            ki.setFlags(Qt.NoItemFlags); f = ki.font(); f.setBold(True); ki.setFont(f)
            self._files_meta.setItem(row, 0, ki)
            vi = QTableWidgetItem(val)
            vi.setFlags(Qt.ItemIsEnabled | Qt.ItemIsEditable)
            vi.setData(Qt.UserRole, field_name)  # store field name, not tag key
            self._files_meta.setItem(row, 1, vi)
            row += 1

        # Remaining tags
        for key, val in remaining:
            self._files_meta.setRowHeight(row, 22)
            ki = QTableWidgetItem(_tag_label(key))
            ki.setFlags(Qt.NoItemFlags); f = ki.font(); f.setBold(True); ki.setFont(f)
            ki.setData(Qt.UserRole, key)
            self._files_meta.setItem(row, 0, ki)
            vi = QTableWidgetItem(val)
            vi.setFlags(Qt.ItemIsEnabled | Qt.ItemIsEditable)
            vi.setData(Qt.UserRole, key)
            self._files_meta.setItem(row, 1, vi)
            row += 1

        # Lyrics — separate widget below the table
        lyrics_text = _extract_lyrics_text(audio)
        self._lyrics_edit.blockSignals(True)
        self._lyrics_edit.setPlainText(lyrics_text or '')
        self._lyrics_edit.blockSignals(False)
        self._lyrics_edit.setVisible(True)
        self._lyrics_label.setVisible(True)

        self._files_meta.blockSignals(False)
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', RuntimeWarning)
            try:
                self._files_meta.itemChanged.disconnect(self._on_meta_item_changed)
            except (TypeError, RuntimeError):
                pass
        self._files_meta.itemChanged.connect(self._on_meta_item_changed)
