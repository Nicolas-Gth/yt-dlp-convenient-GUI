from PySide6.QtWidgets import QTableWidget, QMenu, QApplication
from PySide6.QtGui import QKeySequence
from PySide6.QtCore import Qt

from utils.i18n_utils import t


class CopyableTableWidget(QTableWidget):
    """QTableWidget that supports Ctrl+C to copy selected cells."""

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.Copy):
            self._copy_selection()
        else:
            super().keyPressEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        copy_action = menu.addAction(t("table.copy"))
        copy_action.setEnabled(bool(self.selectedIndexes()))
        action = menu.exec(event.globalPos())
        if action == copy_action:
            self._copy_selection()

    def _copy_selection(self):
        selected = self.selectedIndexes()
        if not selected:
            return
        rows = sorted(set(idx.row() for idx in selected))
        cols = sorted(set(idx.column() for idx in selected))
        lines = []
        for r in rows:
            cells = []
            for c in cols:
                item = self.item(r, c)
                cells.append(item.text() if item else '')
            lines.append('\t'.join(cells))
        QApplication.clipboard().setText('\n'.join(lines))
