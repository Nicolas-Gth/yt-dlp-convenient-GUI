from PySide6.QtWidgets import QLabel, QWidget, QSlider, QStyle, QSizePolicy
from PySide6.QtGui import QPixmap, QResizeEvent
from PySide6.QtCore import Qt, QSize

from views.common.pixmap_utils import round_pixmap


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
