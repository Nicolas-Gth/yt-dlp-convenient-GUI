"""
File browser tab mixin — lists downloaded media files in the output directory.
"""
import os
import re
from typing import Optional, List, Tuple

from PySide6.QtWidgets import (
    QVBoxLayout, QWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QFrame, QSplitter, QLabel,
    QSizePolicy, QGroupBox,
)
from PySide6.QtGui import QPixmap, QImage, QResizeEvent, QPainter, QPainterPath
from PySide6.QtCore import Qt, QSize

from utils.i18n_utils import t


# Map mutagen tag keys to translation keys (human-readable labels)
_TAG_LABELS = {
    # ID3
    "TIT2": "files.title",
    "TPE1": "files.artist",
    "TALB": "tag.album",
    "TRCK": "tag.track",
    "TPOS": "tag.disc",
    "TDRC": "tag.year",
    "TCON": "tag.genre",
    "TCOM": "tag.composer",
    "TPUB": "tag.publisher",
    "TCOP": "tag.copyright",
    "TENC": "tag.encoder",
    "TLEN": "tag.length",
    "APIC": "tag.cover",
    "TPE2": "tag.album_artist",
    # MP4
    "\xa9nam": "files.title",
    "\xa9ART": "files.artist",
    "\xa9alb": "tag.album",
    "trkn": "tag.track",
    "disk": "tag.disc",
    "\xa9day": "tag.year",
    "\xa9gen": "tag.genre",
    "\xa9wrt": "tag.composer",
    "\xa9pub": "tag.publisher",
    "\xa9cpy": "tag.copyright",
    "\xa9too": "tag.encoder",
    "aART": "tag.album_artist",
    # Vorbis / Opus
    "title": "files.title",
    "artist": "files.artist",
    "album": "tag.album",
    "tracknumber": "tag.track",
    "discnumber": "tag.disc",
    "date": "tag.year",
    "genre": "tag.genre",
    "composer": "tag.composer",
    "organization": "tag.publisher",
    "copyright": "tag.copyright",
    "encoder": "tag.encoder",
    "duration": "tag.length",
    "albumartist": "tag.album_artist",
    "album artist": "tag.album_artist",
    "track": "tag.track",
    "disc": "tag.disc",
    "year": "tag.year",
    "length": "tag.length",
    "publisher": "tag.publisher",
    "cover": "tag.cover",
    "lyrics": "files.lyrics",
    "language": "tag.language",
    "originaldate": "tag.original_date",
    "tracktotal": "tag.track_total",
    # ID3 additional
    "COMM": "tag.comment",
    "TDRL": "tag.release_date",
    "TSSE": "tag.encoding",
    "TXXX": "tag.user_text",
    "USLT": "files.lyrics",
}


def _tag_label(key: str) -> str:
    """Return a translated label for *key*, falling back to the raw key."""
    name = _TAG_LABELS.get(key, key)
    return t(name) if name != key else key


class _ArtworkLabel(QLabel):
    """QLabel that scales its pixmap to fit the label width."""

    def __init__(self):
        super().__init__()
        self._pix = None
        self.setAlignment(Qt.AlignCenter)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)

    def setArtwork(self, pix: Optional[QPixmap]):
        self._pix = pix
        self._apply()

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        self._apply()

    def _apply(self):
        if self._pix and not self._pix.isNull() and self.width() > 4 and self.height() > 4:
            scaled = self._pix.scaled(
                self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            # Round corners
            rounded = QPixmap(scaled.size())
            rounded.fill(Qt.transparent)
            p = QPainter(rounded)
            p.setRenderHint(QPainter.Antialiasing)
            path = QPainterPath()
            path.addRoundedRect(0, 0, scaled.width(), scaled.height(), 4, 4)
            p.setClipPath(path)
            p.drawPixmap(0, 0, scaled)
            p.end()
            self.setPixmap(rounded)
        else:
            self.clear()

    def minimumSizeHint(self):
        return QSize(20, 80) if self._pix else QSize(0, 0)

    def sizeHint(self):
        return self._pix.size() if self._pix else QSize(20, 80)


def _load_audio(filepath):
    """Return a mutagen audio object for *filepath*, or None."""
    ext = os.path.splitext(filepath)[1].lower()
    try:
        if ext == '.mp3':
            from mutagen.mp3 import MP3
            return MP3(filepath)
        elif ext == '.mp4':
            from mutagen.mp4 import MP4
            return MP4(filepath)
        elif ext == '.opus':
            from mutagen.oggopus import OggOpus
            return OggOpus(filepath)
    except Exception:
        pass
    return None


def _extract_title_artist(filepath):
    """Extract (title, artist) from an audio/video file using mutagen."""
    from mutagen.mp4 import MP4
    from mutagen.oggopus import OggOpus
    audio = _load_audio(filepath)
    if audio is None or audio.tags is None:
        return "", ""
    artist = ""
    title = ""
    tags = audio.tags
    try:
        if isinstance(audio, OggOpus):
            artist = "; ".join(tags.get('artist', []) or [])
            title = "; ".join(tags.get('title', []) or [])
        elif isinstance(audio, MP4):
            artist = tags.get('\xa9ART', [None])[0] or ""
            title = tags.get('\xa9nam', [None])[0] or ""
        else:  # MP3
            artist = "; ".join(tags.get('TPE1') or [])
            title = "; ".join(tags.get('TIT2') or [])
    except Exception:
        pass
    return artist.strip(), title.strip()


def _check_lyrics(filepath):
    """Check for lyrics: sidecar .lrc/.txt files or embedded metadata.
    Returns (display_text, type_key) where type_key is 'lrc'|'txt'|''.
    """
    base = os.path.splitext(filepath)[0]
    if os.path.exists(base + '.lrc'):
        return 'LRC', 'lrc'
    if os.path.exists(base + '.txt'):
        return 'Txt', 'txt'

    audio = _load_audio(filepath)
    if audio is None or audio.tags is None:
        return t("table.none"), ''
    try:
        from mutagen.mp4 import MP4
        from mutagen.oggopus import OggOpus
        text = None
        if isinstance(audio, OggOpus):
            val = audio.tags.get('lyrics')
            text = val[0] if val else None
        elif isinstance(audio, MP4):
            val = audio.tags.get('\xa9lyr')
            text = val[0] if val else None
        else:
            for tag in audio.tags.values():
                if tag.FrameID == 'USLT':
                    text = str(tag)
                    break
        if text:
            # Detect LRC: lines starting with [mm:ss.xx]
            if re.search(r'^\[\d{2}:\d{2}[.:]\d{2}\]', text, re.MULTILINE):
                return 'LRC', 'lrc'
            return 'Txt', 'txt'
    except Exception:
        pass
    return t("table.none"), ''


def _extract_artwork(audio) -> Optional[QPixmap]:
    """Extract embedded cover art from a mutagen audio object."""
    try:
        from mutagen.mp4 import MP4
        from mutagen.oggopus import OggOpus

        if isinstance(audio, OggOpus):
            pics = audio.tags.get('metadata_block_picture', []) if audio.tags else []
            if pics:
                import base64
                data = base64.b64decode(pics[0])
                idx = data.find(b'\xff\xd8')
                if idx < 0:
                    idx = data.find(b'\x89PNG')
                if idx >= 0:
                    qimg = QImage()
                    qimg.loadFromData(data[idx:])
                    return QPixmap.fromImage(qimg)
            return None

        elif isinstance(audio, MP4):
            covr = audio.tags.get('covr', []) if audio.tags else []
            if covr:
                data = covr[0]
                qimg = QImage()
                qimg.loadFromData(data)
                return QPixmap.fromImage(qimg)
            return None

        else:
            if audio.tags is None:
                return None
            for tag in audio.tags.values():
                if tag.FrameID == 'APIC':
                    qimg = QImage()
                    qimg.loadFromData(tag.data)
                    return QPixmap.fromImage(qimg)
    except Exception:
        pass
    return None


def _extract_all_metadata(audio) -> List[Tuple[str, str]]:
    """Return a list of (key, value) pairs for all tags in *audio*."""
    rows = []
    if audio is None or audio.tags is None:
        return rows
    try:
        from mutagen.mp4 import MP4
        from mutagen.oggopus import OggOpus

        if isinstance(audio, OggOpus):
            for key, values in (audio.tags or {}).items():
                if key.startswith('metadata_block_picture') or key in ('cover', 'lyrics'):
                    continue
                rows.append((key, "; ".join(values)))
            rows.sort(key=lambda r: r[0])
        elif isinstance(audio, MP4):
            for key in sorted(audio.tags.keys()):
                if key in ('covr', '\xa9lyr'):
                    continue
                rows.append((key, "; ".join(str(v) for v in (audio.tags[key] or []))))
        else:  # MP3 ID3
            for tag in sorted(audio.tags.values(), key=lambda t: t.FrameID):
                if tag.FrameID in ('APIC', 'USLT'):
                    continue
                rows.append((tag.FrameID, "; ".join(str(v) for v in tag.text) if hasattr(tag, 'text') else str(tag)))
    except Exception:
        pass
    return rows


def _extract_lyrics_text(audio) -> Optional[str]:
    """Return the full embedded lyrics text, or None."""
    if audio is None or audio.tags is None:
        return None
    try:
        from mutagen.mp4 import MP4
        from mutagen.oggopus import OggOpus
        if isinstance(audio, OggOpus):
            val = audio.tags.get('lyrics')
            return val[0] if val else None
        elif isinstance(audio, MP4):
            val = audio.tags.get('\xa9lyr')
            return val[0] if val else None
        else:
            for tag in audio.tags.values():
                if tag.FrameID == 'USLT':
                    return str(tag)
    except Exception:
        pass
    return None


class FilesMixin:
    """Mixin that provides the 'Download folder' tab."""

    def setup_files_tab(self):
        """Create the file browser tab and add it to the QTabWidget."""
        self._files_tab = QWidget()
        layout = QVBoxLayout(self._files_tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        # ── Left: file table ──
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(8, 8, 4, 8)
        left_layout.setSpacing(0)

        files_group = QGroupBox(t("files.group_title"))
        self._files_group = files_group
        files_layout = QVBoxLayout(files_group)
        files_layout.setContentsMargins(5, 10, 5, 8)

        self._files_table = QTableWidget(0, 4)
        self._files_table.setHorizontalHeaderLabels([
            t("files.filename"),
            t("files.title"),
            t("files.artist"),
            t("files.lyrics"),
        ])
        self._files_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._files_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._files_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._files_table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self._files_table.verticalHeader().setVisible(False)
        self._files_table.setShowGrid(False)
        self._files_table.setFrameShape(QFrame.NoFrame)
        self._files_table.setStyleSheet(
            "QTableWidget { border: none; background: transparent; }"
            "QTableWidget QTableCornerButton::section { background: transparent; }"
            "QHeaderView { background: transparent; font-weight: normal; }"
            "QHeaderView::section {"
            "  border: none; border-bottom: 1px solid palette(mid);"
            "  background: transparent; font-weight: normal;"
            "}"
        )
        hdr = self._files_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Interactive)
        hdr.setSectionResizeMode(1, QHeaderView.Interactive)
        hdr.setSectionResizeMode(2, QHeaderView.Interactive)
        hdr.setSectionResizeMode(3, QHeaderView.Interactive)
        hdr.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._files_table.itemSelectionChanged.connect(self._on_file_selected)
        files_layout.addWidget(self._files_table, 1)
        left_layout.addWidget(files_group, 1)
        splitter.addWidget(left)

        # ── Right: detail panel ──
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 8, 8, 8)
        right_layout.setSpacing(0)

        detail_group = QGroupBox(t("metadata.group_title"))
        self._detail_group = detail_group
        detail_layout = QVBoxLayout(detail_group)
        detail_layout.setContentsMargins(5, 10, 5, 8)

        v_splitter = QSplitter(Qt.Vertical)
        v_splitter.setChildrenCollapsible(False)

        self._files_artwork = _ArtworkLabel()
        artwork_wrapper = QWidget()
        aw = QVBoxLayout(artwork_wrapper)
        aw.setContentsMargins(0, 0, 0, 8)
        aw.addWidget(self._files_artwork)
        v_splitter.addWidget(artwork_wrapper)

        self._files_meta = QTableWidget(0, 2)
        self._files_meta.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._files_meta.setSelectionMode(QAbstractItemView.NoSelection)
        self._files_meta.verticalHeader().setVisible(False)
        self._files_meta.horizontalHeader().setVisible(False)
        self._files_meta.setShowGrid(False)
        self._files_meta.setFrameShape(QFrame.NoFrame)
        self._files_meta.setStyleSheet(
            "QTableWidget { border: none; background: transparent; }"
            "QTableWidget::item { padding: 2px 4px; }"
        )
        mhdr = self._files_meta.horizontalHeader()
        mhdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        mhdr.setSectionResizeMode(1, QHeaderView.Stretch)
        v_splitter.addWidget(self._files_meta)

        v_splitter.setSizes([150, 300])
        detail_layout.addWidget(v_splitter, 1)
        right_layout.addWidget(detail_group, 1)
        splitter.addWidget(right)

        splitter.setSizes([400, 200])
        layout.addWidget(splitter, 1)

        self.tabs.addTab(self._files_tab, t("tabs.files"))
        self.tabs.currentChanged.connect(self._on_tab_changed)

    def _on_tab_changed(self, index):
        """Refresh file list when the files tab is selected."""
        if self.tabs.widget(index) is self._files_tab:
            self.refresh_files_list()

    def refresh_files_list(self):
        """Scan the output directory recursively and populate the file table."""
        directory = self.path_entry.text().strip()
        if not directory or not os.path.isdir(directory):
            self._files_table.setRowCount(0)
            self._show_file_detail(None)
            return

        extensions = ('.mp3', '.mp4', '.opus')
        files = []
        for root, _dirs, filenames in os.walk(directory):
            for fname in filenames:
                if os.path.splitext(fname)[1].lower() in extensions:
                    full = os.path.join(root, fname)
                    rel = os.path.relpath(full, directory)
                    files.append((full, rel))

        files.sort(key=lambda x: x[1].lower())

        self._files_table.setSortingEnabled(False)
        self._files_table.setRowCount(0)
        self._files_table.setRowCount(len(files))
        ROW_HEIGHT = 24

        for idx, (filepath, relpath) in enumerate(files):
            self._files_table.setRowHeight(idx, ROW_HEIGHT)

            name_item = QTableWidgetItem(relpath)
            name_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            name_item.setData(Qt.UserRole, filepath)
            self._files_table.setItem(idx, 0, name_item)

            artist, title = _extract_title_artist(filepath)

            title_item = QTableWidgetItem(title)
            title_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self._files_table.setItem(idx, 1, title_item)

            artist_item = QTableWidgetItem(artist)
            artist_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self._files_table.setItem(idx, 2, artist_item)

            lyrics, lyr_type = _check_lyrics(filepath)
            lyrics_item = QTableWidgetItem(lyrics)
            lyrics_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            lyrics_item.setData(Qt.UserRole, lyr_type)
            self._files_table.setItem(idx, 3, lyrics_item)

        self._files_table.horizontalHeader().resizeSections(QHeaderView.ResizeToContents)
        self._files_table.setSortingEnabled(True)
        self._show_file_detail(None)

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

    def _show_file_detail(self, filepath):
        """Populate the right panel with artwork and metadata."""
        if filepath is None or not os.path.isfile(filepath):
            self._files_artwork.setArtwork(None)
            self._files_meta.setRowCount(0)
            return

        audio = _load_audio(filepath)
        if audio is None:
            self._files_artwork.setArtwork(None)
            self._files_meta.setRowCount(0)
            return

        # Artwork
        pix = _extract_artwork(audio)
        self._files_artwork.setArtwork(pix if pix and not pix.isNull() else None)

        # Metadata table
        meta = _extract_all_metadata(audio)
        lyrics_text = _extract_lyrics_text(audio)
        num_rows = len(meta) + 1 + (1 if lyrics_text else 0)
        self._files_meta.setRowCount(num_rows)
        # Filename row
        self._files_meta.setRowHeight(0, 22)
        key_item = QTableWidgetItem(t("tag.filename"))
        key_item.setFlags(Qt.ItemIsEnabled)
        f = key_item.font(); f.setBold(True); key_item.setFont(f)
        self._files_meta.setItem(0, 0, key_item)
        val_item = QTableWidgetItem(os.path.basename(filepath))
        val_item.setFlags(Qt.ItemIsEnabled)
        self._files_meta.setItem(0, 1, val_item)
        for i, (key, val) in enumerate(meta):
            row = i + 1
            self._files_meta.setRowHeight(row, 22)
            key_item = QTableWidgetItem(_tag_label(key))
            key_item.setFlags(Qt.ItemIsEnabled)
            key_item.setData(Qt.UserRole, key)
            f = key_item.font(); f.setBold(True); key_item.setFont(f)
            self._files_meta.setItem(row, 0, key_item)
            val_item = QTableWidgetItem(val)
            val_item.setFlags(Qt.ItemIsEnabled)
            self._files_meta.setItem(row, 1, val_item)
        if lyrics_text:
            row = len(meta) + 1
            key_item = QTableWidgetItem(t("files.lyrics"))
            key_item.setFlags(Qt.ItemIsEnabled)
            key_item.setData(Qt.UserRole, '_lyrics_')
            f = key_item.font(); f.setBold(True); key_item.setFont(f)
            key_item.setTextAlignment(Qt.AlignLeft | Qt.AlignTop)
            self._files_meta.setItem(row, 0, key_item)
            lbl = QLabel(lyrics_text)
            lbl.setWordWrap(True)
            lbl.setTextFormat(Qt.PlainText)
            lbl.setContentsMargins(4, 2, 4, 2)
            self._files_meta.setCellWidget(row, 1, lbl)
            self._files_meta.resizeRowToContents(row)

    def retranslate_files_tab(self):
        """Update tab and table header labels after a language change."""
        idx = self.tabs.indexOf(self._files_tab)
        if idx >= 0:
            self.tabs.setTabText(idx, t("tabs.files"))
        if hasattr(self, '_files_table') and self._files_table is not None:
            self._files_table.setHorizontalHeaderLabels([
                t("files.filename"),
                t("files.title"),
                t("files.artist"),
                t("files.lyrics"),
            ])
            for r in range(self._files_table.rowCount()):
                item = self._files_table.item(r, 3)
                if item:
                    lyr_type = item.data(Qt.UserRole)
                    if lyr_type == 'lrc':
                        item.setText('LRC')
                    elif lyr_type == 'txt':
                        item.setText('Txt')
                    else:
                        item.setText(t("table.none"))
                    item.setText(t("table.none"))
        if hasattr(self, '_files_group') and self._files_group is not None:
            self._files_group.setTitle(t("files.group_title"))
        if hasattr(self, '_detail_group') and self._detail_group is not None:
            self._detail_group.setTitle(t("metadata.group_title"))
        # Retranslate metadata keys (skip row 0 = filename)
        if hasattr(self, '_files_meta') and self._files_meta is not None:
            if self._files_meta.rowCount() > 0:
                self._files_meta.item(0, 0).setText(t("tag.filename"))
            for r in range(1, self._files_meta.rowCount()):
                item = self._files_meta.item(r, 0)
                if item:
                    raw_key = item.data(Qt.UserRole)
                    if raw_key == '_lyrics_':
                        item.setText(t("files.lyrics"))
                    elif raw_key:
                        item.setText(_tag_label(raw_key))
