import os

from PySide6.QtWidgets import QTableWidgetItem, QHeaderView, QAbstractItemView, QFrame, QGroupBox
from PySide6.QtCore import Qt

from utils.i18n_utils import t

from .metadata import _extract_title_artist, _check_lyrics
from .scanner import FileScanner


class FilesListMixin:
    """Mixin that provides file-list scanning and selection."""

    def _on_tab_changed(self, index):
        """Refresh file list only when necessary (first visit or external changes)."""
        if self.tabs.widget(index) is self._files_tab:
            current_dir = self.path_entry.text().strip()
            if current_dir != getattr(self, '_files_last_directory', None):
                self._files_pending_refresh = True
                self._files_list_loaded = False

            if not self._files_list_loaded or self._files_pending_refresh:
                saved = self._current_detail_filepath
                self.refresh_files_list()
                if saved and os.path.isfile(saved):
                    self._current_detail_filepath = saved
                    self._show_file_detail(saved)
                    self._select_file_in_table(saved)

    def refresh_files_list(self):
        """Scan the output directory recursively in a background thread."""
        directory = self.path_entry.text().strip()
        self._files_last_directory = directory
        self._files_pending_refresh = False
        self._files_list_loaded = True

        # Reset watcher
        if hasattr(self, '_file_watcher'):
            dirs = self._file_watcher.directories()
            if dirs:
                self._file_watcher.removePaths(dirs)
            files = self._file_watcher.files()
            if files:
                self._file_watcher.removePaths(files)

        if not directory or not os.path.isdir(directory):
            self._files_table.setRowCount(0)
            self._show_file_detail(None)
            return

        # Avoid duplicate scans for the same directory
        if getattr(self, '_scanner', None) is not None and self._scanner.isRunning():
            if getattr(self, '_scanner_target_dir', None) == directory:
                return
            # Different directory: stop old thread and start new one
            self._scanner.requestInterruption()
            self._scanner.quit()
            self._scanner.wait(1000)

        self._scanner_target_dir = directory
        self._scanner = FileScanner(directory, self)
        self._scanner.results_ready.connect(self._on_scanner_finished)

        # Show loading state
        self._files_table.setSortingEnabled(False)
        self._files_table.setRowCount(1)
        loading = QTableWidgetItem(t("files.loading"))
        loading.setFlags(Qt.ItemIsEnabled)
        self._files_table.setItem(0, 0, loading)
        self._files_table.setItem(0, 1, QTableWidgetItem(""))
        self._files_table.setItem(0, 2, QTableWidgetItem(""))
        self._files_table.setItem(0, 3, QTableWidgetItem(""))
        self._files_table.setItem(0, 4, QTableWidgetItem(""))
        self._files_table.setEnabled(False)

        self._scanner.start()

    def _on_scanner_finished(self, results, scanned_directory):
        """Populate the file table from the background thread results."""
        # Ignore stale results if the directory changed while scanning
        current_dir = self.path_entry.text().strip()
        if scanned_directory != current_dir:
            return

        self._files_table.setSortingEnabled(False)
        self._files_table.setRowCount(0)
        self._files_table.setRowCount(len(results))
        ROW_HEIGHT = 24
        watched_dirs = set()

        for idx, (filepath, relpath, artist, title, lyrics, lyr_type, mtime) in enumerate(results):
            self._files_table.setRowHeight(idx, ROW_HEIGHT)
            watched_dirs.add(os.path.dirname(filepath))

            name_item = QTableWidgetItem(relpath)
            name_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            name_item.setData(Qt.UserRole, filepath)
            self._files_table.setItem(idx, 0, name_item)

            title_item = QTableWidgetItem(title)
            title_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self._files_table.setItem(idx, 1, title_item)

            artist_item = QTableWidgetItem(artist)
            artist_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self._files_table.setItem(idx, 2, artist_item)

            lyrics_item = QTableWidgetItem(lyrics)
            lyrics_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            lyrics_item.setData(Qt.UserRole, lyr_type)
            self._files_table.setItem(idx, 3, lyrics_item)

            mtime_item = QTableWidgetItem(mtime)
            mtime_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self._files_table.setItem(idx, 4, mtime_item)

        self._files_table.horizontalHeader().resizeSections(QHeaderView.ResizeToContents)
        self._files_table.setSortingEnabled(True)
        self._files_table.setEnabled(True)
        self._show_file_detail(None)

        # Watch directories so we know when to refresh without scanning every time
        if watched_dirs and hasattr(self, '_file_watcher'):
            try:
                self._file_watcher.addPaths(list(watched_dirs))
            except Exception:
                pass

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

    def _on_watcher_changed(self, path):
        """Mark file list as stale so it refreshes on next visit."""
        self._files_pending_refresh = True

    def _on_download_path_changed(self, text):
        """Invalidate cache when download path changes."""
        self._files_pending_refresh = True
        self._files_list_loaded = False
        if self.tabs.currentWidget() is self._files_tab:
            self.refresh_files_list()

    def _select_file_in_table(self, filepath):
        """Select the row matching *filepath* in the files table."""
        for r in range(self._files_table.rowCount()):
            item = self._files_table.item(r, 0)
            if item and item.data(Qt.UserRole) == filepath:
                self._files_table.selectRow(r)
                self._files_table.scrollToItem(item)
                return
