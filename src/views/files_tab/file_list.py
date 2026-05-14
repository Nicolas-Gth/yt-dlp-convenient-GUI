import os

from PySide6.QtWidgets import QTableWidgetItem, QHeaderView, QAbstractItemView, QFrame, QGroupBox
from PySide6.QtCore import Qt

from utils.i18n_utils import t

from .metadata import _extract_title_artist, _check_lyrics


class FilesListMixin:
    """Mixin that provides file-list scanning and selection."""

    def _on_tab_changed(self, index):
        """Refresh file list when the files tab is selected."""
        if self.tabs.widget(index) is self._files_tab:
            saved = self._current_detail_filepath
            self.refresh_files_list()
            if saved and os.path.isfile(saved):
                self._current_detail_filepath = saved
                self._show_file_detail(saved)
                self._select_file_in_table(saved)

    def refresh_files_list(self):
        """Scan the output directory recursively and populate the file table."""
        directory = self.path_entry.text().strip()
        if not directory or not os.path.isdir(directory):
            self._files_table.setRowCount(0)
            self._show_file_detail(None)
            return

        extensions = ('.mp3', '.mp4', '.opus')
        files = []
        for root, _dirs, filenames in os.walk(directory):
            for fname in filenames:
                if os.path.splitext(fname)[1].lower() in extensions:
                    full = os.path.join(root, fname)
                    rel = os.path.relpath(full, directory)
                    files.append((full, rel))

        files.sort(key=lambda x: x[1].lower())

        self._files_table.setSortingEnabled(False)
        self._files_table.setRowCount(0)
        self._files_table.setRowCount(len(files))
        ROW_HEIGHT = 24

        for idx, (filepath, relpath) in enumerate(files):
            self._files_table.setRowHeight(idx, ROW_HEIGHT)

            name_item = QTableWidgetItem(relpath)
            name_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            name_item.setData(Qt.UserRole, filepath)
            self._files_table.setItem(idx, 0, name_item)

            artist, title = _extract_title_artist(filepath)

            title_item = QTableWidgetItem(title)
            title_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self._files_table.setItem(idx, 1, title_item)

            artist_item = QTableWidgetItem(artist)
            artist_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self._files_table.setItem(idx, 2, artist_item)

            lyrics, lyr_type = _check_lyrics(filepath)
            lyrics_item = QTableWidgetItem(lyrics)
            lyrics_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            lyrics_item.setData(Qt.UserRole, lyr_type)
            self._files_table.setItem(idx, 3, lyrics_item)

        self._files_table.horizontalHeader().resizeSections(QHeaderView.ResizeToContents)
        self._files_table.setSortingEnabled(True)
        self._show_file_detail(None)

    def _on_file_selected(self):
        """Show detail for the first selected file."""
        rows = set(idx.row() for idx in self._files_table.selectedIndexes())
        if not rows:
            self._show_file_detail(None)
            return
        row = min(rows)
        name_item = self._files_table.item(row, 0)
        filepath = name_item.data(Qt.UserRole)
        if not filepath or not os.path.isfile(filepath):
            self._show_file_detail(None)
            return
        self._show_file_detail(filepath)

    def _select_file_in_table(self, filepath):
        """Select the row matching *filepath* in the files table."""
        for r in range(self._files_table.rowCount()):
            item = self._files_table.item(r, 0)
            if item and item.data(Qt.UserRole) == filepath:
                self._files_table.selectRow(r)
                self._files_table.scrollToItem(item)
                return
