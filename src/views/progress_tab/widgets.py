from PySide6.QtWidgets import QProgressBar, QLabel, QSizePolicy
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt, QSize

from views.common.pixmap_utils import round_pixmap


class TextProgressBar(QProgressBar):
    """QProgressBar that displays format text even in indeterminate mode."""
    def text(self):
        if self.minimum() == 0 and self.maximum() == 0:
            return self.format()
        return super().text()


class ScaledPixmapLabel(QLabel):
    """QLabel that scales its pixmap to fit, maintaining aspect ratio with rounded corners."""
    def __init__(self):
        super().__init__()
        self._original_pixmap = None
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    def setOriginalPixmap(self, pixmap):
        self._original_pixmap = pixmap
        self._update_scaled()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_scaled()

    def _update_scaled(self):
        if self._original_pixmap:
            target_height = self.height() if self.height() > 0 else self.minimumHeight()
            target_height = max(self.minimumHeight(), target_height)
            if self.maximumHeight() > 0:
                target_height = min(self.maximumHeight(), target_height)

            scaled = self._original_pixmap.scaledToHeight(target_height, Qt.SmoothTransformation)
            scaled = round_pixmap(scaled)
            super().setPixmap(scaled)
            if self.width() != scaled.width():
                self.setFixedWidth(scaled.width())
