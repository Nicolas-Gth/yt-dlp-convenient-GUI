from PySide6.QtWidgets import QLabel, QWidget, QSlider, QStyle, QSizePolicy, QPushButton, QLayout
from PySide6.QtGui import QPixmap, QResizeEvent, QIcon
from PySide6.QtCore import Qt, QSize, Signal, QRect, QPoint

from views.common.pixmap_utils import round_pixmap
from utils.i18n_utils import t


class _FlowLayout(QLayout):
    """Flow layout that wraps widgets left-to-right, top-to-bottom."""

    def __init__(self, parent=None, margin=0, spacing=-1):
        super().__init__(parent)
        if spacing >= 0:
            self.setSpacing(spacing)
        self._items = []

    def __del__(self):
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientations()

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margin = self.contentsMargins()
        size += QSize(margin.left() + margin.right(), margin.top() + margin.bottom())
        return size

    def _do_layout(self, rect, test_only):
        x = rect.x()
        y = rect.y()
        line_height = 0
        spacing = self.spacing()
        for item in self._items:
            wid = item.widget()
            space_x = spacing
            space_y = spacing
            next_x = x + item.sizeHint().width() + space_x
            if next_x - space_x > rect.right() and line_height > 0:
                x = rect.x()
                y = y + line_height + space_y
                next_x = x + item.sizeHint().width() + space_x
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))
            x = next_x
            line_height = max(line_height, item.sizeHint().height())
        return y + line_height - rect.y()


class _ArtworkLabel(QLabel):
    """QLabel that scales its pixmap to fit the label width."""

    def __init__(self):
        super().__init__()
        self._pix = None
        self.setAlignment(Qt.AlignCenter)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

    def setArtwork(self, pix):
        self._pix = pix
        self._apply()

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        self._apply()

    def _apply(self):
        if self._pix and not self._pix.isNull() and self.width() > 4 and self.height() > 4:
            scaled = self._pix.scaled(
                self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            rounded = round_pixmap(scaled, radius=4)
            self.setPixmap(rounded)
        else:
            self.clear()

    def minimumSizeHint(self):
        return QSize(20, 20)

    def sizeHint(self):
        if not self._pix or self._pix.isNull():
            return QSize(20, 20)
        w = max(self.width(), 20)
        ratio = self._pix.height() / max(self._pix.width(), 1)
        return QSize(w, int(w * ratio))


class _ArtworkEditable(_ArtworkLabel):
    """QLabel that shows artwork with an edit button on hover."""

    edit_requested = Signal()

    def __init__(self):
        super().__init__()
        self._btn = QPushButton(" " + t("artwork.edit"))
        self._btn.setFixedSize(80, 28)
        self._btn.setCursor(Qt.PointingHandCursor)
        self._btn.setIcon(QIcon("assets/ui/edit-icon-light.svg"))
        self._btn.setIconSize(QSize(14, 14))
        self._btn.setStyleSheet(
            "QPushButton {"
            "  background-color: rgba(0,0,0,0.6);"
            "  color: white;"
            "  border: none;"
            "  border-radius: 4px;"
            "  font-size: 12px;"
            "  padding: 0 6px;"
            "}"
            "QPushButton:hover { background-color: rgba(0,0,0,0.8); }"
        )
        self._btn.hide()
        self._btn.clicked.connect(self.edit_requested.emit)
        self._btn.setParent(self)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._btn.move(self.width() - self._btn.width() - 6, 6)

    def enterEvent(self, event):
        super().enterEvent(event)
        self._btn.show()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self._btn.hide()

    def retranslate(self):
        self._btn.setText(" " + t("artwork.edit"))


class _SeekSlider(QSlider):
    """Slider that jumps to click position (not just page-step)."""

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.setValue(QStyle.sliderValueFromPosition(
                self.minimum(), self.maximum(), event.pos().x(), self.width()))
        super().mousePressEvent(event)


class _ArtworkWrapper(QWidget):
    """Wrapper that caps its height at 50% of parent."""

    def resizeEvent(self, event):
        super().resizeEvent(event)
        p = self.parentWidget()
        if p:
            self.setMaximumHeight(max(int(p.height() * 0.5), 80))
