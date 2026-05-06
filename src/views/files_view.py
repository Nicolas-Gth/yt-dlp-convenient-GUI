"""
File browser tab mixin — lists downloaded media files in the output directory.
"""
import os
import re
import warnings
from typing import Optional, List, Tuple

# Suppress ffmpeg backend noise from QMediaPlayer
if 'AV_LOG_LEVEL' not in os.environ:
    os.environ['AV_LOG_LEVEL'] = 'quiet'
if 'QT_LOGGING_RULES' not in os.environ:
    os.environ['QT_LOGGING_RULES'] = 'qt.multimedia.ffmpeg.debug=false;qt.multimedia.ffmpeg.info=false'

from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QFrame, QSplitter, QLabel,
    QSizePolicy, QGroupBox, QPushButton, QSlider, QStyle, QTextEdit
)
from PySide6.QtGui import QPixmap, QImage, QResizeEvent, QPainter, QPainterPath
from PySide6.QtCore import Qt, QSize, QUrl, QTimer
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

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
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

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
        return QSize(20, 20)

    def sizeHint(self):
        if not self._pix or self._pix.isNull():
            return QSize(20, 20)
        w = max(self.width(), 20)
        ratio = self._pix.height() / max(self._pix.width(), 1)
        return QSize(w, int(w * ratio))


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


class FilesMixin:
    """Mixin that provides the 'Download folder' tab."""

    _FIELD_KEYS = {
        'title':      ['TIT2', '\xa9nam', 'title'],
        'artist':     ['TPE1', '\xa9ART', 'artist'],
        'album':      ['TALB', '\xa9alb', 'album'],
        'year':       ['TDRC', '\xa9day', 'date', 'year'],
        'tracknumber':['TRCK', 'trkn', 'tracknumber'],
        'genre':      ['TCON', '\xa9gen', 'genre'],
    }
    _FIELD_LABELS = {
        'title':      'files.title',
        'artist':     'files.artist',
        'album':      'tag.album',
        'year':       'tag.year',
        'tracknumber':'tag.track',
        'genre':      'tag.genre',
    }

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
        detail_layout.setContentsMargins(0, 5, 0, 0)

        self._files_artwork = _ArtworkLabel()
        self._current_detail_filepath = None
        self._saved_stderr = None

        # Audio player
        self._audio_output = QAudioOutput()
        self._media_player = QMediaPlayer()
        self._media_player.setAudioOutput(self._audio_output)
        self._media_player.playbackStateChanged.connect(self._on_playback_state_changed)
        self._media_player.positionChanged.connect(self._on_position_changed)
        self._media_player.durationChanged.connect(self._on_duration_changed)
        self._seeking = False

        self._play_btn = QPushButton("⏵")
        self._play_btn.setFixedSize(28, 24)
        self._play_btn.setCursor(Qt.PointingHandCursor)
        self._play_btn.setEnabled(False)
        self._play_btn.clicked.connect(self._on_play_clicked)
        self._play_btn.setStyleSheet("QPushButton { padding: 0; text-align: center; }")

        self._seek_slider = _SeekSlider(Qt.Horizontal)
        self._seek_slider.setEnabled(False)
        self._seek_slider.setRange(0, 0)
        self._seek_slider.sliderPressed.connect(self._on_slider_pressed)
        self._seek_slider.sliderReleased.connect(self._on_slider_released)

        self._elapsed_label = QLabel("0:00")
        self._elapsed_label.setStyleSheet("QLabel { color: palette(dark); font-size: 11px; padding: 0; margin: 0; }")
        self._total_label = QLabel("0:00")
        self._total_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._total_label.setStyleSheet("QLabel { color: palette(dark); font-size: 11px; padding: 0; margin: 0; }")

        player_bar = QHBoxLayout()
        player_bar.setContentsMargins(0, 0, 0, 0)
        player_bar.setSpacing(3)
        player_bar.addWidget(self._play_btn)
        player_bar.addWidget(self._elapsed_label)
        player_bar.addWidget(self._seek_slider, 1)
        player_bar.addWidget(self._total_label)

        self._edit_btn_bar = QWidget()
        self._edit_btn_bar.hide()
        ebl = QHBoxLayout(self._edit_btn_bar)
        ebl.setContentsMargins(0, 0, 0, 0)
        ebl.setSpacing(6)
        ebl.addStretch()
        self._edit_reset_btn = QPushButton(t("button.reset"))
        self._edit_reset_btn.setCursor(Qt.PointingHandCursor)
        self._edit_reset_btn.clicked.connect(self._on_reset_metadata)
        ebl.addWidget(self._edit_reset_btn)
        self._edit_save_btn = QPushButton(t("button.save"))
        self._edit_save_btn.setCursor(Qt.PointingHandCursor)
        self._edit_save_btn.clicked.connect(self._on_save_metadata)
        ebl.addWidget(self._edit_save_btn)

        artwork_wrapper = _ArtworkWrapper()
        self._artwork_wrapper = artwork_wrapper
        aw = QVBoxLayout(artwork_wrapper)
        aw.setContentsMargins(5, 5, 5, 8)
        aw.setSpacing(6)
        aw.addWidget(self._files_artwork)
        aw.addLayout(player_bar)
        aw.addWidget(self._edit_btn_bar)

        self._modified_rows = set()

        self._files_meta = QTableWidget(0, 2)
        self._files_meta.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._files_meta.setEditTriggers(QAbstractItemView.AllEditTriggers)
        self._files_meta.setSelectionMode(QAbstractItemView.NoSelection)
        self._files_meta.verticalHeader().setVisible(False)
        self._files_meta.horizontalHeader().setVisible(False)
        self._files_meta.setShowGrid(False)
        self._files_meta.setFrameShape(QFrame.NoFrame)
        self._files_meta.setStyleSheet(
            "QTableWidget { border: none; background: transparent; }"
            "QTableWidget::item { padding: 2px 4px; }"
        )
        self._edited = False
        mhdr = self._files_meta.horizontalHeader()
        mhdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        mhdr.setSectionResizeMode(1, QHeaderView.Stretch)

        detail_layout.addWidget(artwork_wrapper)

        # Splitter between meta table and lyrics
        self._meta_splitter = QSplitter(Qt.Vertical)
        self._meta_splitter.setChildrenCollapsible(False)
        self._meta_splitter.addWidget(self._files_meta)

        # Lyrics label + edit
        lyrics_bottom = QWidget()
        lbl = QVBoxLayout(lyrics_bottom)
        lbl.setContentsMargins(0, 4, 0, 0)
        lbl.setSpacing(2)
        self._lyrics_label = QLabel(t("files.lyrics"))
        f = self._lyrics_label.font(); f.setBold(True); self._lyrics_label.setFont(f)
        self._lyrics_label.hide()
        lbl.addWidget(self._lyrics_label)
        self._lyrics_edit = QTextEdit()
        self._lyrics_edit.setAcceptRichText(False)
        self._lyrics_edit.setPlaceholderText(t("files.no_lyrics"))
        self._lyrics_edit.textChanged.connect(self._on_lyrics_changed)
        self._lyrics_edit.setStyleSheet("QTextEdit { border: none; background: transparent; }")
        self._lyrics_edit.hide()
        lbl.addWidget(self._lyrics_edit)
        self._meta_splitter.addWidget(lyrics_bottom)
        self._meta_splitter.setSizes([300, 80])

        detail_layout.addWidget(self._meta_splitter, 1)

        right_layout.addWidget(detail_group, 1)
        splitter.addWidget(right)

        splitter.setSizes([400, 200])
        layout.addWidget(splitter, 1)

        self.tabs.addTab(self._files_tab, t("tabs.files"))
        self.tabs.currentChanged.connect(self._on_tab_changed)

    def _on_play_clicked(self):
        if not self._current_detail_filepath:
            return
        if self._media_player.playbackState() == QMediaPlayer.PlayingState:
            self._media_player.pause()
        elif self._media_player.playbackState() == QMediaPlayer.PausedState:
            self._media_player.play()
        else:
            self._mute_stderr()
            self._media_player.setSource(QUrl.fromLocalFile(self._current_detail_filepath))
            self._media_player.play()

    def _mute_stderr(self):
        if self._saved_stderr is not None:
            return
        fd = os.open(os.devnull, os.O_WRONLY)
        self._saved_stderr = os.dup(2)
        os.dup2(fd, 2)
        os.close(fd)

    def _restore_stderr(self):
        if self._saved_stderr is None:
            return
        os.dup2(self._saved_stderr, 2)
        os.close(self._saved_stderr)
        self._saved_stderr = None

    def _on_playback_state_changed(self, state):
        self._play_btn.setText("⏸" if state == QMediaPlayer.PlayingState else "⏵")
        if state == QMediaPlayer.StoppedState:
            self._restore_stderr()

    def _on_position_changed(self, pos_ms):
        if not self._seeking:
            self._seek_slider.setValue(pos_ms)
        pos = pos_ms // 1000
        self._elapsed_label.setText(f"{pos//60}:{pos%60:02d}")

    def _on_duration_changed(self, dur_ms):
        self._seek_slider.setRange(0, dur_ms)
        self._seek_slider.setEnabled(dur_ms > 0)
        dur = dur_ms // 1000
        self._total_label.setText(f"{dur//60}:{dur%60:02d}")

    def _on_slider_pressed(self):
        self._seeking = True

    def _on_slider_released(self):
        self._seeking = False
        self._media_player.setPosition(self._seek_slider.value())

    def _clear_meta_panel(self):
        """Remove all rows and cell widgets from the metadata table."""
        for r in range(self._files_meta.rowCount()):
            if self._files_meta.cellWidget(r, 1):
                self._files_meta.removeCellWidget(r, 1)
        self._files_meta.setRowCount(0)

    def _on_lyrics_changed(self, row):
        self._modified_rows.add(row)
        self._edited = True

    def _on_meta_cell_clicked(self, row, col):
        if col == 1:
            item = self._files_meta.item(row, col)
            if item and item.flags() & Qt.ItemIsEditable:
                self._edit_btn_bar.show()

    def _select_file_in_table(self, filepath):
        """Select the row matching *filepath* in the files table."""
        for r in range(self._files_table.rowCount()):
            item = self._files_table.item(r, 0)
            if item and item.data(Qt.UserRole) == filepath:
                self._files_table.selectRow(r)
                self._files_table.scrollToItem(item)
                return

    def _on_tab_changed(self, index):
        """Refresh file list when the files tab is selected."""
        if self.tabs.widget(index) is self._files_tab:
            saved = self._current_detail_filepath
            self.refresh_files_list()
            if saved and os.path.isfile(saved):
                self._current_detail_filepath = saved
                self._show_file_detail(saved)
                self._select_file_in_table(saved)

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

    def _show_empty_detail(self):
        if self._current_detail_filepath:
            return  # file has been selected since the timer was set
        self._files_meta.setRowCount(1)
        self._files_meta.setRowHeight(0, max(self._files_meta.viewport().height(), 60))
        item = QTableWidgetItem(t("files.no_selection"))
        item.setFlags(Qt.ItemIsEnabled)
        item.setTextAlignment(Qt.AlignCenter)
        self._files_meta.setItem(0, 0, item)
        self._files_meta.setSpan(0, 0, 1, 2)

    def _show_file_detail(self, filepath):
        """Populate the right panel with artwork and metadata."""
        if filepath is None or not os.path.isfile(filepath):
            self._clear_meta_panel()
            self._files_artwork.setArtwork(None)
            self._artwork_wrapper.hide()
            self._current_detail_filepath = None
            self._play_btn.setEnabled(False)
            self._seek_slider.setEnabled(False)
            self._seek_slider.setValue(0)
            self._elapsed_label.setText("0:00")
            self._total_label.setText("0:00")
            self._edit_btn_bar.hide()
            self._lyrics_label.hide()
            self._lyrics_edit.hide()
            QTimer.singleShot(0, self._show_empty_detail)
            return

        self._artwork_wrapper.show()

        if self._current_detail_filepath != filepath:
            self._media_player.stop()
            self._restore_stderr()
            self._seek_slider.setValue(0)
        self._current_detail_filepath = filepath
        self._play_btn.setEnabled(True)
        self._seek_slider.setEnabled(True)

        audio = _load_audio(filepath)
        if audio is None:
            self._clear_meta_panel()
            self._files_artwork.setArtwork(None)
            return

        # Artwork
        pix = _extract_artwork(audio)
        self._files_artwork.setArtwork(pix if pix and not pix.isNull() else None)

        # Metadata table — clear old cell widgets first
        self._clear_meta_panel()
        self._modified_rows.clear()
        self._edited = False
        self._edit_btn_bar.hide()
        self._files_meta.blockSignals(True)

        # Extract values for always-shown fields
        meta_dict = {}
        for k, v in _extract_all_metadata(audio):
            meta_dict[k] = v

        fixed = []
        for field_name in ('title', 'artist', 'album', 'year', 'tracknumber', 'genre'):
            val = ''
            raw_key = ''
            for candidate in self._FIELD_KEYS[field_name]:
                if candidate in meta_dict and meta_dict[candidate]:
                    val = meta_dict[candidate]
                    raw_key = candidate
                    break
            fixed.append((field_name, raw_key, val))
            # Remove from meta_dict so they don't appear twice
            for candidate in self._FIELD_KEYS[field_name]:
                meta_dict.pop(candidate, None)

        # Remaining tags (sorted alphabetically)
        remaining = sorted(meta_dict.items(), key=lambda r: r[0].lower())

        num_rows = 1 + len(fixed) + len(remaining)  # filename + fixed + remaining
        self._files_meta.setRowCount(num_rows)

        row = 0
        # Filename
        self._files_meta.setRowHeight(row, 22)
        ki = QTableWidgetItem(t("tag.filename"))
        ki.setFlags(Qt.NoItemFlags); f = ki.font(); f.setBold(True); ki.setFont(f)
        self._files_meta.setItem(row, 0, ki)
        vi = QTableWidgetItem(os.path.basename(filepath))
        vi.setFlags(Qt.ItemIsEnabled | Qt.ItemIsEditable)
        vi.setData(Qt.UserRole, '_filename_')
        self._files_meta.setItem(row, 1, vi)
        row += 1

        # Fixed fields
        for field_name, raw_key, val in fixed:
            self._files_meta.setRowHeight(row, 22)
            ki = QTableWidgetItem(t(self._FIELD_LABELS[field_name]))
            ki.setFlags(Qt.NoItemFlags); f = ki.font(); f.setBold(True); ki.setFont(f)
            self._files_meta.setItem(row, 0, ki)
            vi = QTableWidgetItem(val)
            vi.setFlags(Qt.ItemIsEnabled | Qt.ItemIsEditable)
            vi.setData(Qt.UserRole, field_name)  # store field name, not tag key
            self._files_meta.setItem(row, 1, vi)
            row += 1

        # Remaining tags
        for key, val in remaining:
            self._files_meta.setRowHeight(row, 22)
            ki = QTableWidgetItem(_tag_label(key))
            ki.setFlags(Qt.NoItemFlags); f = ki.font(); f.setBold(True); ki.setFont(f)
            ki.setData(Qt.UserRole, key)
            self._files_meta.setItem(row, 0, ki)
            vi = QTableWidgetItem(val)
            vi.setFlags(Qt.ItemIsEnabled | Qt.ItemIsEditable)
            vi.setData(Qt.UserRole, key)
            self._files_meta.setItem(row, 1, vi)
            row += 1

        # Lyrics — separate widget below the table
        lyrics_text = _extract_lyrics_text(audio)
        self._lyrics_edit.blockSignals(True)
        self._lyrics_edit.setPlainText(lyrics_text or '')
        self._lyrics_edit.blockSignals(False)
        self._lyrics_edit.setVisible(True)
        self._lyrics_label.setVisible(True)

        self._files_meta.blockSignals(False)
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', RuntimeWarning)
            try:
                self._files_meta.itemChanged.disconnect(self._on_meta_item_changed)
            except (TypeError, RuntimeError):
                pass
        self._files_meta.itemChanged.connect(self._on_meta_item_changed)

    def _on_meta_item_changed(self, item):
        if item.column() == 1 and item.flags() & Qt.ItemIsEditable:
            self._modified_rows.add(item.row())
            self._edited = True
            self._edit_btn_bar.show()

    def _on_lyrics_changed(self):
        self._edited = True
        self._edit_btn_bar.show()

    def _on_reset_metadata(self):
        if self._current_detail_filepath:
            self._files_meta.itemChanged.disconnect(self._on_meta_item_changed)
            self._show_file_detail(self._current_detail_filepath)

    def _on_save_metadata(self):
        if not self._current_detail_filepath:
            return
        self._files_meta.setCurrentCell(-1, -1)
        audio = _load_audio(self._current_detail_filepath)
        if audio is None or audio.tags is None:
            return
        try:
            from mutagen.mp4 import MP4
            from mutagen.oggopus import OggOpus
            tags = audio.tags
            new_filepath = self._current_detail_filepath
            # Handle lyrics (separate widget)
            lyrics_val = self._lyrics_edit.toPlainText()
            if lyrics_val.strip():
                if isinstance(audio, OggOpus):
                    tags['lyrics'] = [lyrics_val]
                elif isinstance(audio, MP4):
                    tags['\xa9lyr'] = [lyrics_val]
                else:
                    from mutagen.id3 import USLT
                    uslt = USLT(encoding=3, lang='eng', desc='', text=lyrics_val)
                    tags.delall('USLT')
                    tags.add(uslt)
            for row in range(self._files_meta.rowCount()):
                val_item = self._files_meta.item(row, 1)
                if not val_item:
                    continue
                key = val_item.data(Qt.UserRole)
                if key == '_filename_':
                    new_name = val_item.text().strip()
                    if new_name:
                        base, ext = os.path.splitext(new_name)
                        orig_ext = os.path.splitext(self._current_detail_filepath)[1]
                        if not ext:
                            ext = orig_ext
                        elif ext.lower() != orig_ext.lower():
                            ext = orig_ext
                        new_filepath = os.path.join(os.path.dirname(self._current_detail_filepath), base + ext)
                    continue
                if key in self._FIELD_KEYS:
                    tag_key = self._FIELD_KEYS[key][0]
                    if isinstance(audio, OggOpus):
                        tag_key = self._FIELD_KEYS[key][2]  # 'album', 'title', etc.
                    elif isinstance(audio, MP4):
                        tag_key = self._FIELD_KEYS[key][1]  # '\xa9alb', '\xa9nam', etc.
                    key = tag_key
                val = val_item.text()
                if isinstance(audio, OggOpus):
                    tags[key] = [val]
                elif isinstance(audio, MP4):
                    tags[key] = [val]
                else:
                    frame = tags.get(key)
                    if frame and hasattr(frame, 'text'):
                        frame.text = [val]
                    elif val:
                        try:
                            cls = type(tags).__module__
                            frame_cls = getattr(tags, '_ID3Tags__module', {}).get(key)
                            if frame_cls:
                                tags.add(frame_cls(encoding=3, text=[val]))
                        except (KeyError, AttributeError):
                            pass
            audio.save()
            if new_filepath != self._current_detail_filepath and os.path.exists(self._current_detail_filepath):
                os.rename(self._current_detail_filepath, new_filepath)
                self._current_detail_filepath = new_filepath
            self._modified_rows.clear()
            self._edited = False
            self._edit_btn_bar.hide()
            self.refresh_files_list()
            self._show_file_detail(new_filepath)
            self._select_file_in_table(new_filepath)
        except Exception as e:
            print(f"Save metadata error: {e}")

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
        if hasattr(self, '_edit_reset_btn') and self._edit_reset_btn is not None:
            self._edit_reset_btn.setText(t("button.reset"))
            self._edit_save_btn.setText(t("button.save"))
        if hasattr(self, '_lyrics_label') and self._lyrics_label is not None:
            self._lyrics_label.setText(t("files.lyrics"))
            self._lyrics_edit.setPlaceholderText(t("files.no_lyrics"))
        # Retranslate metadata keys (skip row 0 = filename)
        if hasattr(self, '_files_meta') and self._files_meta is not None:
            if self._files_meta.rowCount() > 0:
                self._files_meta.item(0, 0).setText(t("tag.filename"))
            for r in range(1, self._files_meta.rowCount()):
                item = self._files_meta.item(r, 0)
                if item:
                    raw_key = item.data(Qt.UserRole)
                    if raw_key:
                        item.setText(_tag_label(raw_key))
