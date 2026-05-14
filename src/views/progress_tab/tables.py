from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QGroupBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QSplitter, QWidget
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont

from utils.i18n_utils import t

from views.common.table_widgets import CopyableTableWidget


class ProgressTablesMixin:
    """Mixin that manages skipped-entries and normalize-feedback tables."""

    def _get_or_create_tables_splitter(self):
        """Lazily create the QSplitter that holds the two summary tables."""
        if not hasattr(self, '_tables_splitter') or self._tables_splitter is None:
            self._tables_splitter = QSplitter(Qt.Vertical)
            self._tables_splitter.setChildrenCollapsible(False)
            self._splitter_user_moved = False
            self._tables_splitter.splitterMoved.connect(
                lambda: setattr(self, '_splitter_user_moved', True)
            )
            self.tables_layout.addWidget(self._tables_splitter, 1)
            self.tables_container.show()
        return self._tables_splitter

    def _snap_splitter_to_skipped(self):
        """Give the skipped table its natural size and leave the rest to normalize."""
        if getattr(self, '_splitter_user_moved', False):
            return
        splitter = getattr(self, '_tables_splitter', None)
        if splitter is None or splitter.count() < 2:
            return
        def _do():
            if splitter is None or splitter.count() < 2:
                return
            total = splitter.height()
            if total < 20:
                return
            skipped_h = self._skipped_group.sizeHint().height()
            norm_h = max(80, total - skipped_h)
            splitter.setSizes([norm_h, skipped_h])
        QTimer.singleShot(0, _do)

    def add_skipped_entry(self, entry: dict, reason: str, reason_key: str = ""):
        """Add one unavailable entry to the skipped entries table."""
        if not hasattr(self, 'progress_frame') or self.progress_frame is None:
            return

        ROW_HEIGHT = 24

        # Lazy-create the group box and table
        if not hasattr(self, '_skipped_group') or self._skipped_group is None:
            self._skipped_group = QGroupBox()
            skipped_layout = QVBoxLayout(self._skipped_group)
            skipped_layout.setContentsMargins(5, 10, 5, 8)

            self._skipped_table = CopyableTableWidget()
            self._skipped_table.setColumnCount(4)
            self._skipped_table.setHorizontalHeaderLabels([
                "#",
                t("progress.table.artist"),
                t("progress.table.title"),
                t("progress.table.reason"),
            ])
            self._skipped_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
            self._skipped_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
            self._skipped_table.verticalHeader().setVisible(False)
            self._skipped_table.setShowGrid(False)
            self._skipped_table.setStyleSheet(
                "QTableWidget { border: none; background: transparent; }"
                "QTableWidget QTableCornerButton::section { background: transparent; }"
                "QHeaderView { background: transparent; font-weight: normal; }"
                "QHeaderView::section { border: none; border-bottom: 1px solid palette(mid); background: transparent; font-weight: normal; }"
            )
            header = self._skipped_table.horizontalHeader()
            header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
            header.setSectionResizeMode(1, QHeaderView.Stretch)
            header.setSectionResizeMode(2, QHeaderView.Stretch)
            header.setSectionResizeMode(3, QHeaderView.Stretch)
            header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)

            skipped_layout.addWidget(self._skipped_table, 1)
            splitter = self._get_or_create_tables_splitter()
            splitter.addWidget(self._skipped_group)
            self._skipped_count = 0
            self._snap_splitter_to_skipped()

        # Add row
        self._skipped_count += 1
        row = self._skipped_table.rowCount()
        self._skipped_table.insertRow(row)
        self._skipped_table.setRowHeight(row, ROW_HEIGHT)

        num_item = QTableWidgetItem(str(self._skipped_count))
        num_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._skipped_table.setItem(row, 0, num_item)
        self._skipped_table.setItem(row, 1, QTableWidgetItem(entry.get('channel', '') or ''))
        self._skipped_table.setItem(row, 2, QTableWidgetItem(entry.get('title', '') or ''))
        self._skipped_table.setItem(row, 3, QTableWidgetItem(reason))
        if reason_key:
            self._skipped_table.item(row, 3).setData(Qt.UserRole, reason_key)

        # Update group title
        key = "progress.skipped_header"
        self._skipped_group.setTitle(t(key))

    def show_normalize_feedback(self, info: dict):
        """Show per-track summary feedback below the progress widgets."""
        if not hasattr(self, 'progress_frame') or self.progress_frame is None:
            return

        if not hasattr(self, '_info_item_count') or self._info_item_count is None:
            self._info_item_count = 0
        self._info_item_count += 1
        num = self._info_item_count

        artist = info.get('artist', '')
        title = info.get('title', info.get('display_name', 'Unknown'))
        metadata = t("table.yes") if info.get('metadata_found') else t("table.none")
        lyrics_type = info.get('lyrics_type', 'No')
        if lyrics_type == 'No':
            lyrics_type = t("table.none")

        volume = info.get('volume')
        if volume:
            diff = volume['measured'] - volume['target']
            norm_str = f"{-diff:+.1f} dB" if diff > 0 else f"{abs(diff):+.1f} dB"
        else:
            norm_str = t("table.none")

        ROW_HEIGHT = 24

        if not hasattr(self, '_normalize_labels') or self._normalize_labels is None:
            self._normalize_labels = []

            self.normalize_outer_frame = QGroupBox(t("progress.downloaded_elements"))
            norm_layout = QVBoxLayout(self.normalize_outer_frame)
            norm_layout.setContentsMargins(5, 10, 5, 8)

            self._normalize_table = CopyableTableWidget(0, 6)
            self._normalize_table.setHorizontalHeaderLabels(
                [t("progress.table.number"), t("progress.table.artist"), t("progress.table.title"),
                 t("progress.table.metadatas"), t("progress.table.lyrics"), t("progress.table.norm")]
            )
            self._normalize_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
            self._normalize_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
            self._normalize_table.verticalHeader().setVisible(False)
            self._normalize_table.setShowGrid(False)
            self._normalize_table.setStyleSheet(
                "QTableWidget { border: none; background: transparent; }"
                "QTableWidget QTableCornerButton::section { background: transparent; }"
                "QHeaderView { background: transparent; font-weight: normal; }"
                "QHeaderView::section { border: none; border-bottom: 1px solid palette(mid); background: transparent; font-weight: normal; }"
            )

            header = self._normalize_table.horizontalHeader()
            header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # #
            header.setSectionResizeMode(1, QHeaderView.Stretch)          # Artist
            header.setSectionResizeMode(2, QHeaderView.Stretch)          # Title
            header.setSectionResizeMode(3, QHeaderView.Stretch)          # Metadatas
            header.setSectionResizeMode(4, QHeaderView.Stretch)          # Lyrics
            header.setSectionResizeMode(5, QHeaderView.Stretch)          # Norm.
            header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)

            norm_layout.addWidget(self._normalize_table, 1)
            splitter = self._get_or_create_tables_splitter()
            splitter.insertWidget(0, self.normalize_outer_frame)
            self._snap_splitter_to_skipped()

        # Add a row
        row = self._normalize_table.rowCount()
        self._normalize_table.insertRow(row)
        self._normalize_table.setRowHeight(row, ROW_HEIGHT)
        for col, text in enumerate([str(num), artist, title, metadata, lyrics_type, norm_str]):
            item = QTableWidgetItem(text)
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self._normalize_table.setItem(row, col, item)
        # Store translation keys for retranslation (col 3 = metadatas, col 4 = lyrics, col 5 = norm)
        meta_key = "table.yes" if info.get('metadata_found') else "table.none"
        self._normalize_table.item(row, 3).setData(Qt.UserRole, meta_key)
        if info.get('lyrics_type', 'No') == 'No':
            self._normalize_table.item(row, 4).setData(Qt.UserRole, "table.none")
        if not info.get('volume'):
            self._normalize_table.item(row, 5).setData(Qt.UserRole, "table.none")
        self._normalize_labels.append(num)

        count = len(self._normalize_labels)
        key = "progress.downloaded_element" if count == 1 else "progress.downloaded_elements"
        self.normalize_outer_frame.setTitle(t(key))

        self._normalize_table.scrollToBottom()
