import os
import re
import shutil
from datetime import datetime

from PySide6.QtWidgets import (
    QTableWidgetItem, QHeaderView, QAbstractItemView, QFrame, QGroupBox, QMessageBox
)
from PySide6.QtCore import Qt

from utils.i18n_utils import t

from .metadata import _extract_title_artist, _check_lyrics, _extract_template_info
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
                # Preserve the file currently shown in the detail panel
                # so that music keeps playing and the panel is not cleared.
                saved = self._current_detail_filepath
                if saved and os.path.isfile(saved):
                    self._files_saved_selection = saved
                self.refresh_files_list()

    def refresh_files_list(self):
        """Scan the output directory recursively in a background thread."""
        directory = self.path_entry.text().strip()
        self._files_last_directory = directory
        self._files_pending_refresh = False
        self._files_list_loaded = True

        # If nobody pre-set the file to restore (editor, tab switch…),
        # fall back to the table's current selection.
        if not getattr(self, '_files_saved_selection', None):
            rows = set(idx.row() for idx in self._files_table.selectedIndexes())
            if rows:
                item = self._files_table.item(min(rows), 0)
                if item:
                    self._files_saved_selection = item.data(Qt.UserRole)

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

        # Only show loading state on first visit (empty table).
        # On subsequent refreshes keep the existing rows visible to avoid
        # flicker, selection loss and music interruption.
        self._files_table.setSortingEnabled(False)
        if self._files_table.rowCount() == 0:
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

        selected_filepath = getattr(self, '_files_saved_selection', None)
        current_detail = getattr(self, '_current_detail_filepath', None)
        watched_dirs = set()

        # Build map of existing rows by filepath
        existing_rows = {}
        for r in range(self._files_table.rowCount()):
            item = self._files_table.item(r, 0)
            if item:
                existing_rows[item.data(Qt.UserRole)] = r

        new_files = [r[0] for r in results]
        same_set = set(existing_rows.keys()) == set(new_files)

        # In-place update: same files, only metadata may have changed.
        # No row clearing → no flicker, no selection loss, no music stop.
        if same_set and len(existing_rows) == len(results):
            self._files_table.blockSignals(True)
            self._files_table.setSortingEnabled(False)
            for idx, (filepath, relpath, artist, title, lyrics, lyr_type, mtime) in enumerate(results):
                watched_dirs.add(os.path.dirname(filepath))
                row = existing_rows[filepath]
                self._files_table.item(row, 0).setText(relpath)
                self._files_table.item(row, 1).setText(title)
                self._files_table.item(row, 2).setText(artist)
                l_item = self._files_table.item(row, 3)
                l_item.setText(lyrics)
                l_item.setData(Qt.UserRole, lyr_type)
                self._files_table.item(row, 4).setText(mtime)
            self._files_table.horizontalHeader().resizeSections(QHeaderView.ResizeToContents)
            self._files_table.setSortingEnabled(True)
            self._files_table.blockSignals(False)
        else:
            # Full rebuild (files added/removed/reordered)
            self._files_table.blockSignals(True)
            self._files_table.setSortingEnabled(False)
            self._files_table.setRowCount(0)
            self._files_table.setRowCount(len(results))
            ROW_HEIGHT = 24
            selected_row = -1

            for idx, (filepath, relpath, artist, title, lyrics, lyr_type, mtime) in enumerate(results):
                self._files_table.setRowHeight(idx, ROW_HEIGHT)
                watched_dirs.add(os.path.dirname(filepath))

                if selected_filepath and filepath == selected_filepath:
                    selected_row = idx

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
            self._files_table.blockSignals(False)

            # Restore selection by filepath — row index may have changed due to sorting.
            if selected_filepath:
                self._select_file_in_table(selected_filepath)

            # Only update the detail panel if the selected file changed or was deleted.
            if selected_filepath:
                file_still_exists = any(r[0] == selected_filepath for r in results)
                if file_still_exists:
                    if current_detail != selected_filepath:
                        self._show_file_detail(selected_filepath)
                else:
                    if current_detail == selected_filepath:
                        self._show_file_detail(None)
            elif current_detail is None:
                # No saved selection and panel is empty → show the empty state
                self._show_file_detail(None)

        # Watch directories so we know when to refresh without scanning every time
        if watched_dirs and hasattr(self, '_file_watcher'):
            try:
                self._file_watcher.addPaths(list(watched_dirs))
            except Exception:
                pass

        # Clear the saved selection so the next refresh reads from the table again.
        self._files_saved_selection = None

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

    def _on_files_search_changed(self, text):
        """Filter the file table rows based on the search text."""
        query = text.lower().strip()
        for row in range(self._files_table.rowCount()):
            if not query:
                self._files_table.setRowHidden(row, False)
                continue
            match = False
            for col in (0, 1, 2):
                item = self._files_table.item(row, col)
                if item and query in item.text().lower():
                    match = True
                    break
            self._files_table.setRowHidden(row, not match)

    def _on_watcher_changed(self, path):
        """Mark file list as stale — refresh will happen on next explicit request."""
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

    # ------------------------------------------------------------------
    # Folder structure (template apply)
    # ------------------------------------------------------------------

    _TEMPLATE_VAR_RE = re.compile(r'\{(\w+)\}')
    _FILENAME_ILLEGAL_RE = re.compile(r'[!?:#%&{}<>|*$@~]')
    _DATE_TOKENS = ('Y', 'y', 'm', 'd', 'H', 'M', 'S', 'B', 'b')

    def _on_files_template_preset_changed(self, index):
        """Handle template preset dropdown change."""
        if index < 0:
            return
        template_val = self._files_template_presets.itemData(index)
        if template_val:
            self._files_template_entry.blockSignals(True)
            self._files_template_entry.setText(template_val)
            self._files_template_entry.blockSignals(False)

    def _on_apply_format_clicked(self):
        """Show confirmation and reorganize files according to the template."""
        template = self._files_template_entry.text().strip()
        if not template:
            return
        reply = QMessageBox.question(
            self,
            t("files.confirm_reorganize_title"),
            t("files.confirm_reorganize_text"),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        self._reorganize_files(template)

    def _reorganize_files(self, template: str):
        """Move/rename all files in the table according to *template*."""
        directory = self.path_entry.text().strip()
        if not directory or not os.path.isdir(directory):
            return
        for r in range(self._files_table.rowCount()):
            item = self._files_table.item(r, 0)
            if not item:
                continue
            filepath = item.data(Qt.UserRole)
            if not filepath or not os.path.isfile(filepath):
                continue
            new_relpath = self._resolve_file_template(filepath, template)
            if not new_relpath:
                continue
            new_path = os.path.join(directory, new_relpath)
            # ensure extension is preserved
            orig_ext = os.path.splitext(filepath)[1]
            new_ext = os.path.splitext(new_path)[1]
            if new_ext.lower() != orig_ext.lower():
                new_path += orig_ext
            if os.path.normpath(filepath) == os.path.normpath(new_path):
                continue
            # create target directories
            target_dir = os.path.dirname(new_path)
            if target_dir and not os.path.exists(target_dir):
                os.makedirs(target_dir, exist_ok=True)
            # avoid overwriting existing files
            if os.path.exists(new_path):
                base, ext = os.path.splitext(new_path)
                counter = 1
                while os.path.exists(new_path):
                    new_path = f"{base} ({counter}){ext}"
                    counter += 1
            try:
                shutil.move(filepath, new_path)
            except Exception as e:
                print(f"[reorganize] Error moving {filepath} -> {new_path}: {e}")
        self._files_pending_refresh = True
        self.refresh_files_list()

    def _resolve_file_template(self, filepath: str, template: str) -> str:
        """Resolve a filename template using existing file metadata."""
        info = _extract_template_info(filepath)
        mtime = os.path.getmtime(filepath)
        dt = datetime.fromtimestamp(mtime)
        tokens = {t: '' for t in self._DATE_TOKENS}
        for t in self._DATE_TOKENS:
            try:
                tokens[t] = dt.strftime(f'%{t}')
            except (ValueError, OSError):
                tokens[t] = ''

        def replace_var(m):
            name = m.group(1)
            if name in tokens:
                return tokens[name]
            if name in info:
                return info[name]
            return m.group(0)

        raw_name = self._TEMPLATE_VAR_RE.sub(replace_var, template)
        # sanitize each path component
        sanitized = '/'.join(
            self._sanitize_path_component(part) for part in raw_name.split('/')
        )
        return sanitized

    @staticmethod
    def _sanitize_path_component(component: str) -> str:
        """Strip characters that are illegal in file/directory names."""
        sanitized = FilesListMixin._FILENAME_ILLEGAL_RE.sub('', component)
        s = sanitized.strip()
        if not s or s in ('.', '..'):
            return '_'
        return s
