import os
import re
import shutil
import unicodedata
from datetime import datetime

from PySide6.QtWidgets import (
    QTableWidgetItem, QHeaderView, QAbstractItemView, QFrame, QGroupBox, QMessageBox, QMenu
)
from PySide6.QtCore import Qt

from utils.i18n_utils import t, plural_suffix
from utils.settings_utils import settings_manager

from .metadata import _extract_template_info
from .scanner import FileScanner


class _NumericItem(QTableWidgetItem):
    """QTableWidgetItem that sorts by an internal numeric value."""

    def __init__(self, text: str, value: float):
        super().__init__(text)
        self._sort_value = value

    def __lt__(self, other):
        if isinstance(other, _NumericItem):
            return self._sort_value < other._sort_value
        return super().__lt__(other)


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
            self._update_files_group_title()
            return

        # Avoid duplicate scans for the same directory
        if getattr(self, '_scanner', None) is not None and self._scanner.isRunning():
            if getattr(self, '_scanner_target_dir', None) == directory:
                return
            # Different directory: stop old thread and start new one
            self._scanner.requestInterruption()
            self._scanner.wait(5000)

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
            for c in range(1, self._files_table.columnCount()):
                self._files_table.setItem(0, c, QTableWidgetItem(""))
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
            for idx, (filepath, relpath, artist, title, album, genre, year, tracknumber, lyrics, lyr_type, size, mtime) in enumerate(results):
                watched_dirs.add(os.path.dirname(filepath))
                row = existing_rows[filepath]
                self._files_table.item(row, 0).setText(relpath)
                self._files_table.item(row, 1).setText(title)
                self._files_table.item(row, 2).setText(artist)
                self._files_table.item(row, 3).setText(album)
                self._files_table.item(row, 4).setText(genre)
                self._files_table.item(row, 5).setText(year)
                self._files_table.item(row, 6).setText(tracknumber)
                l_item = self._files_table.item(row, 7)
                l_item.setText(lyrics)
                l_item.setData(Qt.UserRole, lyr_type)
                s_item = self._files_table.item(row, 8)
                if isinstance(s_item, _NumericItem):
                    s_item.setText(_format_size(size))
                    s_item._sort_value = size
                m_item = self._files_table.item(row, 9)
                if isinstance(m_item, _NumericItem):
                    m_item.setText(datetime.fromtimestamp(mtime).strftime("%d/%m/%Y %H:%M"))
                    m_item._sort_value = mtime
            self._restoring_widths = True
            self._files_table.horizontalHeader().resizeSections(QHeaderView.ResizeToContents)
            self._restoring_widths = False
            self._files_table.setSortingEnabled(True)
            self._files_table.blockSignals(False)
            self._restore_column_widths()
        else:
            # Full rebuild (files added/removed/reordered)
            self._files_table.blockSignals(True)
            self._files_table.setSortingEnabled(False)
            self._files_table.setRowCount(0)
            self._files_table.setRowCount(len(results))
            ROW_HEIGHT = 24
            selected_row = -1

            for idx, (filepath, relpath, artist, title, album, genre, year, tracknumber, lyrics, lyr_type, size, mtime) in enumerate(results):
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

                album_item = QTableWidgetItem(album)
                album_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                self._files_table.setItem(idx, 3, album_item)

                genre_item = QTableWidgetItem(genre)
                genre_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                self._files_table.setItem(idx, 4, genre_item)

                year_item = QTableWidgetItem(year)
                year_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                self._files_table.setItem(idx, 5, year_item)

                track_item = QTableWidgetItem(tracknumber)
                track_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                self._files_table.setItem(idx, 6, track_item)

                lyrics_item = QTableWidgetItem(lyrics)
                lyrics_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                lyrics_item.setData(Qt.UserRole, lyr_type)
                self._files_table.setItem(idx, 7, lyrics_item)

                size_item = _NumericItem(_format_size(size), size)
                size_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                self._files_table.setItem(idx, 8, size_item)

                mtime_item = _NumericItem(datetime.fromtimestamp(mtime).strftime("%d/%m/%Y %H:%M"), mtime)
                mtime_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                self._files_table.setItem(idx, 9, mtime_item)

            self._restoring_widths = True
            self._files_table.horizontalHeader().resizeSections(QHeaderView.ResizeToContents)
            self._restoring_widths = False
            self._restore_sort_column()
            self._files_table.setSortingEnabled(True)
            self._files_table.setEnabled(True)
            self._files_table.blockSignals(False)
            self._restore_column_widths()

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

        # Re-apply search filter if one is active
        if hasattr(self, '_files_search'):
            current_search = self._files_search.text()
            if current_search:
                self._on_files_search_changed(current_search)

        self._update_files_group_title()

    def _update_files_group_title(self):
        """Set the files group title to include the current file count."""
        count = self._files_table.rowCount()
        self._files_group.setTitle(
            t("files.group_title", count=count, count_s=plural_suffix(count))
        )

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

    def _on_files_context_menu(self, pos):
        """Right-click context menu on the file table."""
        from PySide6.QtGui import QIcon
        from PySide6.QtWidgets import QStyle
        rows = set(idx.row() for idx in self._files_table.selectedIndexes())
        if not rows:
            return
        style = self._files_table.style()
        menu = QMenu(self._files_table)
        open_folder_action = menu.addAction(style.standardIcon(QStyle.SP_DirOpenIcon), t("files.open_folder"))
        menu.addSeparator()
        copy_icon = QIcon.fromTheme("edit-copy")
        if copy_icon.isNull():
            copy_icon = style.standardIcon(QStyle.SP_FileIcon)
        copy_path_action = menu.addAction(copy_icon, t("files.copy_path"))
        copy_name_action = menu.addAction(copy_icon, t("files.copy_name"))
        menu.addSeparator()
        restructure_action = menu.addAction(QIcon.fromTheme("edit-rename"), t("files.restructure_selected"))
        menu.addSeparator()
        normalize_action = menu.addAction(QIcon.fromTheme("audio-volume-high"), t("files.normalize_context_menu"))
        menu.addSeparator()
        batch_icon = QIcon("assets/ui/search-icon-light.svg")
        batch_action = menu.addAction(batch_icon, t("batch.context_menu"))
        menu.addSeparator()
        delete_action = menu.addAction(style.standardIcon(QStyle.SP_TrashIcon), t("files.delete"))
        action = menu.exec(self._files_table.viewport().mapToGlobal(pos))
        if action == open_folder_action:
            self._open_selected_folders(rows)
        elif action == delete_action:
            self._delete_selected_files(rows)
        elif action == restructure_action:
            self._restructure_selected_files(rows)
        elif action == normalize_action:
            self._on_normalize_selected(rows)
        elif action == batch_action:
            self._on_batch_identify_selected(rows)
        elif action == copy_path_action:
            self._copy_selected_paths(rows)
        elif action == copy_name_action:
            self._copy_selected_names(rows)

    def _get_selected_filepaths(self, rows):
        """Return list of absolute paths for the given selected rows."""
        filepaths = []
        for r in rows:
            item = self._files_table.item(r, 0)
            if item:
                fp = item.data(Qt.UserRole)
                if fp and os.path.isfile(fp):
                    filepaths.append(fp)
        return filepaths

    def _copy_selected_paths(self, rows):
        filepaths = self._get_selected_filepaths(rows)
        if filepaths:
            from PySide6.QtWidgets import QApplication
            QApplication.clipboard().setText("\n".join(filepaths))

    def _copy_selected_names(self, rows):
        filepaths = self._get_selected_filepaths(rows)
        if filepaths:
            from PySide6.QtWidgets import QApplication
            QApplication.clipboard().setText("\n".join(os.path.basename(fp) for fp in filepaths))

    def _open_selected_files(self, rows):
        filepaths = self._get_selected_filepaths(rows)
        if filepaths:
            from PySide6.QtGui import QDesktopServices
            from PySide6.QtCore import QUrl
            for fp in filepaths:
                QDesktopServices.openUrl(QUrl.fromLocalFile(fp))

    def _open_selected_folders(self, rows):
        filepaths = self._get_selected_filepaths(rows)
        if filepaths:
            from PySide6.QtGui import QDesktopServices
            from PySide6.QtCore import QUrl
            folders = set(os.path.dirname(fp) for fp in filepaths)
            for folder in folders:
                QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    def _delete_selected_files(self, rows):
        """Delete the files in the given selected rows."""
        filepaths = []
        filenames = []
        for r in rows:
            item = self._files_table.item(r, 0)
            if item:
                fp = item.data(Qt.UserRole)
                if fp and os.path.isfile(fp):
                    filepaths.append(fp)
                    filenames.append(os.path.basename(fp))
        if not filepaths:
            return
        msg = t("files.delete_confirm_text") if len(filepaths) == 1 else t("files.delete_confirm_text_multi")
        reply = QMessageBox.question(
            self,
            t("files.delete_confirm_title"),
            msg.format(files="\n".join(f" • {n}" for n in filenames)),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        for fp in filepaths:
            try:
                os.remove(fp)
            except OSError:
                pass
        self.refresh_files_list()

    def _on_remove_empty_folders(self):
        """Remove all empty directories under the download folder."""
        directory = self.path_entry.text().strip()
        if not directory or not os.path.isdir(directory):
            return
        empty_dirs = self._find_empty_dirs(directory)
        if not empty_dirs:
            QMessageBox.information(self, t("files.remove_empty_folders"), t("files.remove_empty_none"))
            return
        reply = QMessageBox.question(
            self,
            t("files.remove_empty_folders"),
            t("files.remove_empty_confirm", count=len(empty_dirs)),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        removed = 0
        for path in empty_dirs:
            try:
                os.rmdir(path)
                removed += 1
            except OSError:
                pass
        QMessageBox.information(
            self, t("files.remove_empty_folders"), t("files.remove_empty_done", count=removed)
        )
        self.refresh_files_list()

    @staticmethod
    def _find_empty_dirs(root_dir: str) -> list:
        """Return paths of directories under *root_dir* that are empty
        after cascading removal of empty subdirectories."""
        empty = set()
        for current, dirs, files in os.walk(root_dir, topdown=False):
            for name in dirs:
                path = os.path.join(current, name)
                try:
                    entries = os.listdir(path)
                except OSError:
                    continue
                if all(os.path.join(path, e) in empty for e in entries):
                    empty.add(path)
        return sorted(empty, key=lambda p: p.count(os.sep), reverse=True)

    def _restructure_selected_files(self, rows):
        """Open a template dialog and restructure the selected files."""
        from PySide6.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QComboBox, QPushButton, QLabel
        )
        from PySide6.QtGui import QIcon
        from PySide6.QtCore import QSize
        from config import INFO_ICON_PATH
        from utils.settings_utils import settings_manager

        filepaths = []
        for r in rows:
            item = self._files_table.item(r, 0)
            if item:
                fp = item.data(Qt.UserRole)
                if fp and os.path.isfile(fp):
                    filepaths.append(fp)
        if not filepaths:
            return

        _TEMPLATE_PRESETS = [
            ("{artist} - {title}", "format.template_preset_default"),
            ("{Y}-{m}-{d} - {artist} - {title}", "format.template_preset_date_artist"),
            ("{Y}{m}{d}_{H}{M}{S}_{title}", "format.template_preset_date_time"),
            ("{tracknumber} - {artist} - {title}", "format.template_preset_track_artist"),
            ("{artist}/{album}/{artist} - {title}", "format.template_preset_artist_album"),
            ("{artist}/{album}/{tracknumber} - {title}", "format.template_preset_album_track"),
            ("{title}", "format.template_preset_simple"),
        ]

        dlg = QDialog(self)
        dlg.setWindowTitle(t("files.restructure_title"))
        dlg.setMinimumWidth(620)
        layout = QVBoxLayout(dlg)
        layout.setSpacing(8)

        # Template row: entry + presets dropdown + info button
        template_row = QHBoxLayout()
        template_entry = QLineEdit()
        default_template = settings_manager.get_setting("last_output_template", "")
        template_entry.setText(default_template)
        template_entry.setClearButtonEnabled(True)
        template_row.addWidget(template_entry, 1)

        template_presets = QComboBox()
        template_presets.setCursor(Qt.PointingHandCursor)
        for template_val, label_key in _TEMPLATE_PRESETS:
            template_presets.addItem(t(label_key), template_val)
        template_presets.addItem(t("format.template_preset_custom"), None)
        current_text = template_entry.text().strip()
        idx = template_presets.findData(current_text)
        template_presets.setCurrentIndex(idx if idx >= 0 else template_presets.count() - 1)
        template_presets.currentIndexChanged.connect(
            lambda i: template_entry.setText(template_presets.itemData(i) or template_entry.text())
        )
        template_row.addWidget(template_presets)

        info_btn = QPushButton()
        info_btn.setIcon(QIcon(INFO_ICON_PATH))
        info_btn.setIconSize(QSize(14, 14))
        info_btn.setFlat(True)
        info_btn.setCursor(Qt.PointingHandCursor)
        info_btn.setFixedSize(20, 20)
        info_btn.clicked.connect(
            lambda: QMessageBox.information(dlg, t("format.template_info_title"), t("format.template_info_text"))
        )
        template_row.addWidget(info_btn)

        layout.addLayout(template_row)

        # Selected files list (max 5, then summary)
        MAX_VISIBLE = 5
        remaining = len(filepaths) - MAX_VISIBLE
        names = [os.path.basename(fp) for fp in filepaths[:MAX_VISIBLE]]
        if remaining > 0:
            names.append(t("files.restructure_more_selected").format(n=remaining))
        files_label = QLabel("\n".join(f"  • {n}" for n in names))
        files_label.setWordWrap(True)
        layout.addWidget(files_label)

        # OK / Cancel
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton(t("button.cancel"))
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.clicked.connect(dlg.reject)
        btn_row.addWidget(cancel_btn)
        apply_btn = QPushButton(t("artwork.apply"))
        apply_btn.setCursor(Qt.PointingHandCursor)
        apply_btn.clicked.connect(dlg.accept)
        apply_btn.setDefault(True)
        btn_row.addWidget(apply_btn)
        layout.addLayout(btn_row)

        # Prevent Enter from closing without going through accept
        dlg.keyPressEvent_orig = dlg.keyPressEvent
        def _key_handler(event):
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                focused = dlg.focusWidget()
                if focused is template_entry:
                    dlg.accept()
                    return
            dlg.keyPressEvent_orig(event)
        dlg.keyPressEvent = _key_handler

        if dlg.exec() != QDialog.Accepted:
            return
        template = template_entry.text().strip()
        if not template:
            return

        settings_manager.set_setting("last_output_template", template)
        self._reorganize_selected(filepaths, template)

    def _on_files_search_changed(self, text):
        """Filter the file table rows based on the search text."""
        query = text.lower().strip()
        for row in range(self._files_table.rowCount()):
            if not query:
                self._files_table.setRowHidden(row, False)
                continue
            match = False
            for col in range(self._files_table.columnCount()):
                if self._files_table.isColumnHidden(col):
                    continue
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
    _FILENAME_ILLEGAL_RE = re.compile(r'[!?:#%&{}<>|*$@~/\\]')
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
        settings_manager.set_setting("last_output_template", template)
        self._reorganize_files(template)

    def _reorganize_files(self, template: str):
        """Move/rename all files in the table according to *template*."""
        directory = self.path_entry.text().strip()
        if not directory or not os.path.isdir(directory):
            return
        moved_from = set()
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
            new_path = unicodedata.normalize('NFC', new_path)
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
                moved_from.add(os.path.dirname(filepath))
            except Exception as e:
                QMessageBox.warning(
                    self._files_tab, t("files.reorganize_error"),
                    t("files.reorganize_error_detail").format(src=filepath, dst=new_path, error=str(e))
                )
        self._remove_empty_dirs(directory, moved_from)
        self._files_pending_refresh = True
        self.refresh_files_list()

    def _reorganize_selected(self, filepaths: list, template: str):
        """Move/rename the given *filepaths* according to *template*."""
        directory = self.path_entry.text().strip()
        if not directory or not os.path.isdir(directory):
            return
        moved_from = set()
        for filepath in filepaths:
            if not os.path.isfile(filepath):
                continue
            new_relpath = self._resolve_file_template(filepath, template)
            if not new_relpath:
                continue
            new_path = os.path.join(directory, new_relpath)
            new_path = unicodedata.normalize('NFC', new_path)
            orig_ext = os.path.splitext(filepath)[1]
            new_ext = os.path.splitext(new_path)[1]
            if new_ext.lower() != orig_ext.lower():
                new_path += orig_ext
            if os.path.normpath(filepath) == os.path.normpath(new_path):
                continue
            target_dir = os.path.dirname(new_path)
            if target_dir and not os.path.exists(target_dir):
                os.makedirs(target_dir, exist_ok=True)
            if os.path.exists(new_path):
                base, ext = os.path.splitext(new_path)
                counter = 1
                while os.path.exists(new_path):
                    new_path = f"{base} ({counter}){ext}"
                    counter += 1
            try:
                shutil.move(filepath, new_path)
                moved_from.add(os.path.dirname(filepath))
            except Exception as e:
                QMessageBox.warning(
                    self._files_tab, t("files.reorganize_error"),
                    t("files.reorganize_error_detail").format(src=filepath, dst=new_path, error=str(e))
                )
        self._remove_empty_dirs(directory, moved_from)
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
                return tokens[name].replace('/', '_').replace('\\', '_')
            if name in info:
                return info[name].replace('/', '_').replace('\\', '_')
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
        while len(s.encode('utf-8')) > 200:
            s = s[:-1]
        return unicodedata.normalize('NFC', s)

    @staticmethod
    def _remove_empty_dirs(root_dir: str, moved_from: set):
        """Remove directories in *moved_from* that became empty after moves.
        Walks upward until a non-empty directory or *root_dir* is reached."""
        if not root_dir or not os.path.isdir(root_dir):
            return
        root_dir = os.path.normpath(root_dir)
        for src_dir in sorted(moved_from, key=lambda d: d.count(os.sep), reverse=True):
            current = os.path.normpath(src_dir)
            while current and current.startswith(root_dir) and current != root_dir:
                try:
                    if not os.listdir(current):
                        os.rmdir(current)
                        current = os.path.dirname(current)
                    else:
                        break
                except OSError:
                    break


def _format_size(size: int) -> str:
    """Return a human-readable file size string (e.g. '3.5 MB')."""
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if size < 1024:
            if unit == 'B':
                return f"{size} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"
