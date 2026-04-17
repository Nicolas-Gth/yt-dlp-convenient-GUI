"""
Theme management utilities.

Provides dark / light palette definitions and system-preference detection
so the controller stays lean.
"""
import subprocess
import sys

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette, QColor


def system_prefers_dark() -> bool:
    """Detect if the OS is using a dark colour scheme."""
    if sys.platform.startswith('linux'):
        try:
            out = subprocess.check_output(
                ['gsettings', 'get', 'org.gnome.desktop.interface', 'color-scheme'],
                stderr=subprocess.DEVNULL, timeout=2
            ).decode().strip().strip("'")
            if 'dark' in out:
                return True
            if 'light' in out or 'default' in out:
                return False
        except Exception:
            pass
        try:
            out = subprocess.check_output(
                ['gsettings', 'get', 'org.gnome.desktop.interface', 'gtk-theme'],
                stderr=subprocess.DEVNULL, timeout=2
            ).decode().strip().strip("'")
            if 'dark' in out.lower():
                return True
        except Exception:
            pass
    hints = QApplication.instance().styleHints()
    if hasattr(hints, 'colorScheme'):
        scheme = hints.colorScheme()
        if scheme == Qt.ColorScheme.Dark:
            return True
        if scheme == Qt.ColorScheme.Light:
            return False
    return False


def _build_dark_palette() -> QPalette:
    """Build the dark Fusion palette."""
    palette = QPalette()
    bg = QColor('#333333')
    dark = QColor('#2a2a2a')
    mid = QColor('#444444')
    text = QColor('white')
    highlight = QColor('#238a45')
    palette.setColor(QPalette.Window, bg)
    palette.setColor(QPalette.WindowText, text)
    palette.setColor(QPalette.Base, mid)
    palette.setColor(QPalette.AlternateBase, dark)
    palette.setColor(QPalette.ToolTipBase, QColor('#222222'))
    palette.setColor(QPalette.ToolTipText, text)
    palette.setColor(QPalette.Text, text)
    palette.setColor(QPalette.Button, mid)
    palette.setColor(QPalette.ButtonText, text)
    palette.setColor(QPalette.BrightText, QColor('red'))
    palette.setColor(QPalette.Highlight, highlight)
    palette.setColor(QPalette.HighlightedText, text)
    palette.setColor(QPalette.Mid, QColor('#666666'))
    palette.setColor(QPalette.Dark, QColor('#888888'))
    palette.setColor(QPalette.Shadow, QColor('#111111'))
    palette.setColor(QPalette.Midlight, QColor('#555555'))
    palette.setColor(QPalette.Light, QColor('#666666'))
    palette.setColor(QPalette.PlaceholderText, QColor('#999999'))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor('#888888'))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor('#888888'))
    return palette


def _build_light_palette() -> QPalette:
    """Build the light Fusion palette."""
    palette = QPalette()
    bg = QColor('#f0f0f0')
    base = QColor('#ffffff')
    alt = QColor('#e8e8e8')
    text = QColor('#1a1a1a')
    highlight = QColor('#238a45')
    palette.setColor(QPalette.Window, bg)
    palette.setColor(QPalette.WindowText, text)
    palette.setColor(QPalette.Base, base)
    palette.setColor(QPalette.AlternateBase, alt)
    palette.setColor(QPalette.ToolTipBase, QColor('#ffffdc'))
    palette.setColor(QPalette.ToolTipText, text)
    palette.setColor(QPalette.Text, text)
    palette.setColor(QPalette.Button, bg)
    palette.setColor(QPalette.ButtonText, text)
    palette.setColor(QPalette.BrightText, QColor('red'))
    palette.setColor(QPalette.Highlight, highlight)
    palette.setColor(QPalette.HighlightedText, QColor('white'))
    palette.setColor(QPalette.Mid, QColor('#b0b0b0'))
    palette.setColor(QPalette.Dark, QColor('#808080'))
    palette.setColor(QPalette.Shadow, QColor('#505050'))
    palette.setColor(QPalette.Midlight, QColor('#d8d8d8'))
    palette.setColor(QPalette.Light, QColor('#ffffff'))
    palette.setColor(QPalette.PlaceholderText, QColor('#888888'))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor('#aaaaaa'))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor('#aaaaaa'))
    return palette


def apply_theme(app: QApplication, name: str):
    """Apply the given theme ('system', 'dark', or 'light') to *app*."""
    app.setStyle('Fusion')
    if name == 'dark':
        app.setPalette(_build_dark_palette())
    elif name == 'light':
        app.setPalette(_build_light_palette())
    else:
        if system_prefers_dark():
            app.setPalette(_build_dark_palette())
        else:
            app.setPalette(_build_light_palette())
