from io import BytesIO

from PIL import Image
from PySide6.QtGui import QImage, QPixmap, QPainter, QPainterPath
from PySide6.QtCore import Qt


def qpixmap_from_data(data: bytes) -> QPixmap:
    """Decode *data* into a QPixmap using Pillow.

    Qt's bundled libjpeg prints noisy warnings ("Corrupt JPEG data: ...",
    "Unsupported marker type ...") for embedded cover art that contains stray
    bytes. Pillow decodes these silently, so decode there and hand the raw
    pixels to Qt.
    """
    if not data:
        return QPixmap()
    try:
        im = Image.open(BytesIO(data))
        im.load()
    except Exception:
        return QPixmap()
    if "A" in im.getbands():
        im = im.convert("RGBA")
        fmt = QImage.Format_RGBA8888
    else:
        im = im.convert("RGB")
        fmt = QImage.Format_RGB888
    # .copy() detaches Qt from the temporary Python buffer.
    qimg = QImage(im.tobytes(), im.width, im.height, im.width * len(im.getbands()), fmt).copy()
    return QPixmap.fromImage(qimg)


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
