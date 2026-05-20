from PySide6.QtGui import QPixmap, QPainter, QPainterPath
from PySide6.QtCore import Qt


def round_pixmap(pixmap: QPixmap, radius: int = 4) -> QPixmap:
    """Return a copy of *pixmap* with rounded corners."""
    rounded = QPixmap(pixmap.size())
    rounded.fill(Qt.transparent)
    painter = QPainter(rounded)
    painter.setRenderHint(QPainter.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(0, 0, pixmap.width(), pixmap.height(), radius, radius)
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, pixmap)
    painter.end()
    return rounded
