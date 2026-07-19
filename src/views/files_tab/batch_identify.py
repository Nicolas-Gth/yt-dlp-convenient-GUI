"""
Batch identification for multiple audio files.

Provides:
- BatchIdentifyDialog: configuration dialog (scope, data types, strategy)
- BatchIdentifyMixin: processing logic (file iteration, API calls, auto/manual apply)
"""

import os

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QCheckBox,
    QPushButton, QProgressBar, QMessageBox, QGroupBox
)
from PySide6.QtCore import Qt, QTimer, QSize

from utils.i18n_utils import t
from utils.settings_utils import settings_manager
from .metadata import _load_audio, _extract_title_artist, _extract_artwork, _check_lyrics


class BatchIdentifyDialog(QDialog):
    """Configuration dialog for batch identification."""

    def __init__(self, parent=None, preselected_files=None):
        super().__init__(parent)
        self.setWindowTitle(t("batch.dialog_title"))
        self.setMinimumWidth(480)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowMaximizeButtonHint)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        if preselected_files:
            scope_group = QGroupBox(t("batch.scope_label"))
            scope_layout = QVBoxLayout(scope_group)
            scope_layout.setContentsMargins(5, 10, 5, 8)
            scope_label = QLabel(t("batch.selected_files", count=len(preselected_files), count_s="s" if len(preselected_files) != 1 else ""))
            scope_layout.addWidget(scope_label)
            self.scope_combo = None
            layout.addWidget(scope_group)
        else:
            scope_group = QGroupBox(t("batch.scope_label"))
            scope_layout = QVBoxLayout(scope_group)
            scope_layout.setContentsMargins(5, 10, 5, 8)
            self.scope_combo = QComboBox()
            self.scope_combo.setCursor(Qt.PointingHandCursor)
            self.scope_combo.addItem(t("batch.scope_none"))
            self.scope_combo.addItem(t("batch.scope_incomplete"))
            self.scope_combo.addItem(t("batch.scope_all"))
            saved_scope = settings_manager.get_setting("last_batch_scope", 1)
            self.scope_combo.setCurrentIndex(saved_scope if 0 <= saved_scope <= 2 else 1)
            scope_layout.addWidget(self.scope_combo)
            layout.addWidget(scope_group)

        type_group = QGroupBox(t("batch.type_label"))
        type_layout = QVBoxLayout(type_group)
        type_layout.setContentsMargins(5, 10, 5, 8)
        self.metadata_check = QCheckBox(t("batch.type_metadata"))
        self.metadata_check.setCursor(Qt.PointingHandCursor)
        self.metadata_check.setChecked(settings_manager.get_setting("last_batch_metadata", True))
        type_layout.addWidget(self.metadata_check)
        self.lyrics_check = QCheckBox(t("batch.type_lyrics"))
        self.lyrics_check.setCursor(Qt.PointingHandCursor)
        self.lyrics_check.setChecked(settings_manager.get_setting("last_batch_lyrics", True))
        type_layout.addWidget(self.lyrics_check)
        layout.addWidget(type_group)

        strategy_group = QGroupBox(t("batch.strategy_label"))
        strategy_layout = QVBoxLayout(strategy_group)
        strategy_layout.setContentsMargins(5, 10, 5, 8)
        self.strategy_combo = QComboBox()
        self.strategy_combo.setCursor(Qt.PointingHandCursor)
        self.strategy_combo.addItem(t("batch.strategy_ask_all"))
        self.strategy_combo.addItem(t("batch.strategy_skip_confident"))
        self.strategy_combo.addItem(t("batch.strategy_auto"))
        saved_strategy = settings_manager.get_setting("last_batch_strategy", 1)
        self.strategy_combo.setCurrentIndex(saved_strategy if 0 <= saved_strategy <= 2 else 1)
        strategy_layout.addWidget(self.strategy_combo)
        layout.addWidget(strategy_group)

        filter_group = QGroupBox(t("batch.filter_label"))
        filter_layout = QVBoxLayout(filter_group)
        filter_layout.setContentsMargins(5, 10, 5, 8)

        clean_row = QHBoxLayout()
        clean_row.setSpacing(6)
        self.filter_clean_check = QCheckBox(t("batch.filter_clean_title"))
        self.filter_clean_check.setCursor(Qt.PointingHandCursor)
        self.filter_clean_check.setChecked(settings_manager.get_setting("last_batch_filter_clean", False))
        clean_row.addWidget(self.filter_clean_check)

        from config import INFO_ICON_PATH
        from PySide6.QtGui import QIcon
        filter_info_btn = QPushButton()
        filter_info_btn.setIcon(QIcon(INFO_ICON_PATH))
        filter_info_btn.setIconSize(QSize(14, 14))
        filter_info_btn.setFlat(True)
        filter_info_btn.setCursor(Qt.PointingHandCursor)
        filter_info_btn.setFixedSize(20, 20)
        filter_info_btn.clicked.connect(
            lambda: QMessageBox.information(self, t("batch.filter_clean_title"), t("batch.filter_clean_info"))
        )
        clean_row.addWidget(filter_info_btn)
        clean_row.addStretch()
        filter_layout.addLayout(clean_row)

        self.filter_artist_check = QCheckBox(t("batch.filter_use_artist"))
        self.filter_artist_check.setCursor(Qt.PointingHandCursor)
        self.filter_artist_check.setChecked(settings_manager.get_setting("last_batch_filter_artist", True))
        filter_layout.addWidget(self.filter_artist_check)

        self.filter_title_check = QCheckBox(t("batch.filter_use_title"))
        self.filter_title_check.setCursor(Qt.PointingHandCursor)
        self.filter_title_check.setChecked(settings_manager.get_setting("last_batch_filter_title", True))
        filter_layout.addWidget(self.filter_title_check)

        self.filter_album_check = QCheckBox(t("batch.filter_use_album"))
        self.filter_album_check.setCursor(Qt.PointingHandCursor)
        self.filter_album_check.setChecked(settings_manager.get_setting("last_batch_filter_album", True))
        filter_layout.addWidget(self.filter_album_check)

        layout.addWidget(filter_group)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton(t("button.cancel"))
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        start_btn = QPushButton(t("batch.start"))
        start_btn.setCursor(Qt.PointingHandCursor)
        start_btn.clicked.connect(self._on_start)
        start_btn.setDefault(True)
        btn_row.addWidget(start_btn)
        layout.addLayout(btn_row)

    def _on_start(self):
        if not self.metadata_check.isChecked() and not self.lyrics_check.isChecked():
            return
        if self.scope_combo is not None:
            settings_manager.set_setting("last_batch_scope", self.scope_combo.currentIndex())
        settings_manager.set_setting("last_batch_metadata", self.metadata_check.isChecked())
        settings_manager.set_setting("last_batch_lyrics", self.lyrics_check.isChecked())
        settings_manager.set_setting("last_batch_strategy", self.strategy_combo.currentIndex())
        settings_manager.set_setting("last_batch_filter_clean", self.filter_clean_check.isChecked())
        settings_manager.set_setting("last_batch_filter_artist", self.filter_artist_check.isChecked())
        settings_manager.set_setting("last_batch_filter_title", self.filter_title_check.isChecked())
        settings_manager.set_setting("last_batch_filter_album", self.filter_album_check.isChecked())
        self.accept()

    def showEvent(self, event):
        super().showEvent(event)
        hint = self.sizeHint()
        w = max(hint.width(), 480)
        self.setFixedSize(w, hint.height())


class BatchIdentifyMixin:
    """Mixin that provides batch identification functionality."""

    # Threshold for auto-apply in "skip confident" strategy
    # Same logic as download-time enrichment (metadata_enricher_utils.py:220)
    CONFIDENCE_THRESHOLD = 0.6

    def _on_batch_identify(self):
        """Open the batch identification configuration dialog."""
        directory = self.path_entry.text().strip()
        if not directory or not os.path.isdir(directory):
            return

        if self._files_table.rowCount() == 0:
            QMessageBox.information(self, t("batch.dialog_title"), t("batch.no_files_in_dir"))
            return

        dlg = BatchIdentifyDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return

        scope = dlg.scope_combo.currentIndex()
        do_metadata = dlg.metadata_check.isChecked()
        do_lyrics = dlg.lyrics_check.isChecked()
        strategy = dlg.strategy_combo.currentIndex()
        filter_clean = dlg.filter_clean_check.isChecked()
        filter_artist = dlg.filter_artist_check.isChecked()
        filter_title = dlg.filter_title_check.isChecked()
        filter_album = dlg.filter_album_check.isChecked()

        if not do_metadata and not do_lyrics:
            return

        eligible = self._gather_batch_files(scope, do_lyrics)
        if not eligible:
            QMessageBox.information(self, t("batch.dialog_title"), t("batch.no_files"))
            return

        self._start_batch_processing(eligible, do_metadata, do_lyrics, strategy, filter_clean, filter_artist, filter_title, filter_album)

    def _on_batch_identify_selected(self, rows):
        """Open batch identification for the given selected rows only."""
        from PySide6.QtWidgets import QApplication
        filepaths = []
        for r in rows:
            item = self._files_table.item(r, 0)
            if item:
                fp = item.data(Qt.UserRole)
                if fp and os.path.isfile(fp):
                    filepaths.append(fp)
        if not filepaths:
            return

        dlg = BatchIdentifyDialog(self, preselected_files=filepaths)
        if dlg.exec() != QDialog.Accepted:
            return

        do_metadata = dlg.metadata_check.isChecked()
        do_lyrics = dlg.lyrics_check.isChecked()
        strategy = dlg.strategy_combo.currentIndex()
        filter_clean = dlg.filter_clean_check.isChecked()
        filter_artist = dlg.filter_artist_check.isChecked()
        filter_title = dlg.filter_title_check.isChecked()
        filter_album = dlg.filter_album_check.isChecked()

        if not do_metadata and not do_lyrics:
            return

        self._start_batch_processing(filepaths, do_metadata, do_lyrics, strategy, filter_clean, filter_artist, filter_title, filter_album)

    def _gather_batch_files(self, scope, check_lyrics):
        """Return list of filepaths matching the scope criteria.

        scope: 0 = no data (no artist AND no title),
               1 = incomplete,
               2 = all
        """
        results = []
        for r in range(self._files_table.rowCount()):
            item = self._files_table.item(r, 0)
            if not item:
                continue
            filepath = item.data(Qt.UserRole)
            if not filepath or not os.path.isfile(filepath):
                continue

            if scope == 2:
                results.append(filepath)
            elif scope == 0:
                artist, title = _extract_title_artist(filepath)
                if not artist.strip() and not title.strip():
                    results.append(filepath)
            elif scope == 1:
                is_complete, _ = self._check_file_completeness(filepath, check_lyrics)
                if not is_complete:
                    results.append(filepath)
        return results

    def _check_file_completeness(self, filepath, check_lyrics):
        """Check if a file has all expected metadata fields.

        Returns (is_complete: bool, missing_fields: list).
        Required fields: artist, title, album, genre, year, artwork,
        (+ lyrics if check_lyrics is True).
        """
        audio = _load_audio(filepath)
        if audio is None or audio.tags is None:
            return False, ["all"]

        from mutagen.mp4 import MP4
        from mutagen.oggopus import OggOpus

        missing = []
        artist = ""
        title = ""
        album = ""
        genre = ""
        year = ""

        tags = audio.tags
        try:
            if isinstance(audio, OggOpus):
                artist = "; ".join(tags.get('artist', []) or []).strip()
                title = "; ".join(tags.get('title', []) or []).strip()
                album = "; ".join(tags.get('album', []) or []).strip()
                genre = "; ".join(tags.get('genre', []) or []).strip()
                raw_year = "; ".join(tags.get('date', []) or []).strip()
                year = raw_year[:4] if raw_year and raw_year[:4].isdigit() else ""
            elif isinstance(audio, MP4):
                artist = (tags.get('\xa9ART', [None])[0] or "").strip()
                title = (tags.get('\xa9nam', [None])[0] or "").strip()
                album = (tags.get('\xa9alb', [None])[0] or "").strip()
                genre = (tags.get('\xa9gen', [None])[0] or "").strip()
                raw_year = (tags.get('\xa9day', [None])[0] or "").strip()
                year = raw_year[:4] if raw_year and raw_year[:4].isdigit() else ""
            else:  # MP3
                def _text(frame):
                    return "; ".join(str(v) for v in frame.text) if hasattr(frame, 'text') else str(frame)

                if tags.get('TPE1'):
                    artist = _text(tags['TPE1']).strip()
                if tags.get('TIT2'):
                    title = _text(tags['TIT2']).strip()
                if tags.get('TALB'):
                    album = _text(tags['TALB']).strip()
                if tags.get('TCON'):
                    genre = _text(tags['TCON']).strip()
                year_frame = tags.get('TDRC') or tags.get('TYER')
                if year_frame:
                    raw = _text(year_frame).strip()
                    year = raw[:4] if raw and raw[:4].isdigit() else raw
        except Exception:
            return False, ["read_error"]

        if not artist:
            missing.append("artist")
        if not title:
            missing.append("title")
        if not album:
            missing.append("album")
        if not genre:
            missing.append("genre")
        if not year:
            missing.append("year")

        # Check artwork
        pix = _extract_artwork(audio)
        if pix is None or pix.isNull():
            missing.append("artwork")

        # Check lyrics if requested
        if check_lyrics:
            l_text, l_type = _check_lyrics(filepath)
            if not l_type:
                missing.append("lyrics")

        return len(missing) == 0, missing

    # ------------------------------------------------------------------
    # Batch processing state machine (QTimer-driven sequential loop)
    # ------------------------------------------------------------------

    def _start_batch_processing(self, files, do_metadata, do_lyrics, strategy, filter_clean, filter_artist, filter_title, filter_album):
        """Initialize batch state and show progress dialog."""
        self._batch_files = files
        self._batch_idx = 0
        self._batch_do_metadata = do_metadata
        self._batch_do_lyrics = do_lyrics
        self._batch_strategy = strategy
        self._batch_filter_clean = filter_clean
        self._batch_filter_artist = filter_artist
        self._batch_filter_title = filter_title
        self._batch_filter_album = filter_album
        self._batch_cancelled = False
        self._batch_meta_found = 0
        self._batch_lyrics_found = 0
        self._batch_ignored = 0
        self._batch_failed = 0

        self._batch_progress = QDialog(self)
        self._batch_progress.setWindowTitle(t("batch.progress_title"))
        self._batch_progress.setMinimumWidth(480)
        self._batch_progress.setWindowModality(Qt.NonModal)
        layout = QVBoxLayout(self._batch_progress)
        layout.setSpacing(12)

        self._batch_progress_label = QLabel()
        layout.addWidget(self._batch_progress_label)

        self._batch_progress_bar = QProgressBar()
        self._batch_progress_bar.setRange(0, len(files))
        self._batch_progress_bar.setValue(0)
        self._batch_progress_bar.setTextVisible(True)
        self._batch_progress_bar.setFormat("")
        layout.addWidget(self._batch_progress_bar)

        self._batch_status_label = QLabel()
        layout.addWidget(self._batch_status_label)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._batch_cancel_btn = QPushButton(t("button.cancel"))
        self._batch_cancel_btn.setCursor(Qt.PointingHandCursor)
        self._batch_cancel_btn.clicked.connect(self._on_batch_cancel)
        btn_row.addWidget(self._batch_cancel_btn)
        layout.addLayout(btn_row)

        self._batch_progress.finished.connect(self._on_batch_progress_closed)
        self._batch_progress.show()
        self._batch_progress.adjustSize()
        hint = self._batch_progress.sizeHint()
        self._batch_progress.setFixedSize(max(hint.width(), 480), hint.height())
        self._update_batch_progress()
        QTimer.singleShot(150, self._process_next_batch_file)

    def _on_batch_cancel(self):
        self._batch_cancelled = True
        if self._batch_progress:
            self._batch_cancel_btn.setEnabled(False)
            self._batch_cancel_btn.setText(t("batch.cancelling"))

    def _on_batch_progress_closed(self):
        self._batch_cancelled = True

    def _update_batch_progress(self):
        total = len(self._batch_files)
        idx = self._batch_idx
        cur_file = ""
        if idx < total:
            cur_file = os.path.basename(self._batch_files[idx])
        self._batch_progress_label.setText(
            t("batch.processing_file", index=idx + 1, total=total, file=cur_file)
        )
        self._batch_progress_bar.setValue(idx)
        self._batch_progress_bar.setFormat(f"{t('batch.progress_bar_text', index=idx + 1, total=total)}")

        lines = []
        if self._batch_do_metadata:
            c = self._batch_meta_found
            lines.append(t("batch.status_meta", count=c, count_s="" if c <= 1 else "s"))
        if self._batch_do_lyrics:
            c = self._batch_lyrics_found
            lines.append(t("batch.status_lyrics", count=c, count_s="" if c <= 1 else "s"))
        c = self._batch_ignored
        lines.append(t("batch.status_ignored", count=c, count_s="" if c <= 1 else "s"))
        if self._batch_failed > 0:
            c = self._batch_failed
            lines.append(t("batch.status_failed", count=c, count_s="" if c <= 1 else "s"))
        self._batch_status_label.setText("\n".join(lines))

    def _process_next_batch_file(self):
        """Process a single file, then schedule the next via QTimer."""
        if self._batch_cancelled:
            self._finish_batch()
            return

        if self._batch_idx >= len(self._batch_files):
            self._finish_batch()
            return

        filepath = self._batch_files[self._batch_idx]
        self._update_batch_progress()

        try:
            mtime_before = os.path.getmtime(filepath)
        except OSError:
            mtime_before = -1

        try:
            if self._batch_do_metadata and not self._batch_cancelled:
                try:
                    meta_before = os.path.getmtime(filepath)
                except OSError:
                    meta_before = -1
                self._batch_identify_metadata(filepath, self._batch_strategy)
                try:
                    meta_after = os.path.getmtime(filepath)
                except OSError:
                    meta_after = -1
                if meta_after != meta_before:
                    self._batch_meta_found += 1

            if self._batch_do_lyrics and not self._batch_cancelled:
                try:
                    lyr_before = os.path.getmtime(filepath)
                except OSError:
                    lyr_before = -1
                self._batch_identify_lyrics(filepath, self._batch_strategy)
                try:
                    lyr_after = os.path.getmtime(filepath)
                except OSError:
                    lyr_after = -1
                if lyr_after != lyr_before:
                    self._batch_lyrics_found += 1

            try:
                mtime_after = os.path.getmtime(filepath)
            except OSError:
                mtime_after = -1

            if mtime_after != mtime_before:
                pass  # file was modified by at least one operation
            else:
                self._batch_ignored += 1
        except Exception as e:
            self._batch_failed += 1
            print(f"[batch] Error processing {filepath}: {e}")

        self._batch_idx += 1
        QTimer.singleShot(80, self._process_next_batch_file)

    # ------------------------------------------------------------------
    # Per-file metadata identification
    # ------------------------------------------------------------------

    _CLEAN_PATTERNS = [
        r'[\(\{\[].*?[\)\}\]\]]',   # content between (), {}, []
        r'(?i)\b(official|video|audio|lyrics?|visualizer|hd|hq|remaster(ed)?|'
        r'deluxe|expanded|anniversary|special\s*edition|bonus\s*track|'
        r'feat\.?|ft\.?|soundtrack|ost|theme|original\s*mix|'
        r'radio\s*edit|extended\s*mix|club\s*mix|instrumental|acoustic|live|'
        r'cover|tribute|karaoke|explicit|clean|version|edit)\.?\b',
        r'\s+',                       # collapse whitespace
    ]

    def _batch_clean_title(self, text):
        """Remove non-essential content from a title string."""
        import re
        cleaned = text
        # Remove content between brackets
        cleaned = re.sub(r'[\(\{\[].*?[\)\}\]\]]', '', cleaned)
        # Remove common filler words
        cleaned = re.sub(
            r'(?i)\b(official|video|audio|lyrics?|visualizer|h[dp]|hq|'
            r'remaster(ed)?|deluxe|expanded|anniversary|special\s*edition|bonus\s*track|'
            r'feat\.?\s*.*$|ft\.?\s*.*$|soundtrack|ost|theme|'
            r'radio\s*edit|extended\s*mix|club\s*mix|instrumental|acoustic|live|'
            r'cover|tribute|karaoke|explicit|clean|version|edit)\.?\b',
            '', cleaned, flags=re.IGNORECASE
        )
        # Collapse whitespace and strip
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        # Remove trailing punctuation
        cleaned = re.sub(r'[\s\-_.,;:!]+$', '', cleaned).strip()
        return cleaned

    def _batch_extract_search_terms(self, filepath):
        """Extract (artist, title, album) for API search, applying active filters."""
        artist, title = _extract_title_artist(filepath)

        # Read album from tags (not in _extract_title_artist, so read it here)
        album = ""
        audio = _load_audio(filepath)
        if audio is not None and audio.tags is not None:
            from mutagen.mp4 import MP4
            from mutagen.oggopus import OggOpus
            try:
                if isinstance(audio, OggOpus):
                    album = "; ".join(audio.tags.get('album', []) or []).strip()
                elif isinstance(audio, MP4):
                    album = (audio.tags.get('\xa9alb', [None])[0] or "").strip()
                else:
                    frame = audio.tags.get('TALB')
                    if frame:
                        album = ("; ".join(str(v) for v in frame.text) if hasattr(frame, 'text') else str(frame)).strip()
            except Exception:
                pass

        # Apply artist filter: if unchecked or empty, clear artist
        if not self._batch_filter_artist or not artist.strip():
            artist = ""

        # Apply title filter: if unchecked or empty, fall back to filename
        if not self._batch_filter_title or not title.strip():
            filename = os.path.splitext(os.path.basename(filepath))[0]
            title = filename

        # Apply album filter: if unchecked or empty, don't use album
        if not self._batch_filter_album or not album:
            album = ""

        # Apply cleaning
        if self._batch_filter_clean:
            title = self._batch_clean_title(title)
            artist = self._batch_clean_title(artist)
            album = self._batch_clean_title(album)

        return artist, title, album

    def _batch_identify_metadata(self, filepath, strategy):
        """Identify metadata for a single file."""
        artist, title, album = self._batch_extract_search_terms(filepath)

        if strategy == 0:
            self._show_metadata_selector(filepath, search_artist=artist, search_title=title, search_album=album)
            return

        from utils.metadata_enricher_utils import search_metadata_itunes, search_metadata_candidates

        if not artist and not title:
            return

        candidates = []
        try:
            itunes_results = search_metadata_itunes(artist, title, album, limit=3)
            candidates.extend(itunes_results)
        except Exception:
            pass

        if not candidates:
            try:
                mb_results = search_metadata_candidates(artist, title, album, limit=3)
                candidates.extend(mb_results)
            except Exception:
                pass

        if not candidates:
            if strategy == 1:
                self._show_metadata_selector(filepath, search_artist=artist, search_title=title, search_album=album)
            return

        best = candidates[0]
        confidence = self._batch_compute_confidence(best, artist, title, album)

        if strategy == 2 or confidence >= self.CONFIDENCE_THRESHOLD:
            self._apply_metadata_result(filepath, best)
        elif strategy == 1:
            self._show_metadata_selector(filepath, search_artist=artist, search_title=title, search_album=album)

    # ------------------------------------------------------------------
    # Per-file lyrics identification
    # ------------------------------------------------------------------

    def _batch_identify_lyrics(self, filepath, strategy):
        """Identify lyrics for a single file."""
        artist, title, album = self._batch_extract_search_terms(filepath)
        if not artist and not title:
            return

        if strategy == 0:
            self._show_lyrics_search_dialog(filepath, search_artist=artist, search_title=title)
            return

        from utils.metadata_enricher_utils import search_lyrics_lrclib, _fetch_lyrics_genius

        audio = _load_audio(filepath)
        duration = 0
        if audio:
            try:
                duration = int(getattr(audio.info, 'length', 0))
            except Exception:
                pass

        results = []
        try:
            lrclib = search_lyrics_lrclib(artist, title, album, duration, limit=5)
            results.extend(lrclib)
        except Exception:
            pass

        if not results:
            try:
                genius = _fetch_lyrics_genius(artist, title)
                if genius:
                    lines_count = len(genius.splitlines())
                    results.append({
                        "title": title,
                        "artist": artist,
                        "album": "",
                        "lines": lines_count,
                        "synced": False,
                        "source": "Genius",
                        "duration": 0,
                        "lyrics": genius,
                        "lyrics_type": "plain",
                    })
            except Exception:
                pass

        if not results:
            return

        best = results[0]
        confidence = self._batch_compute_confidence(best, artist, title, album)

        if strategy == 2 or confidence >= self.CONFIDENCE_THRESHOLD:
            self._apply_lyrics_result(filepath, best)
        elif strategy == 1:
            self._show_lyrics_search_dialog(filepath, search_artist=artist, search_title=title)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _batch_compute_confidence(self, candidate, artist, title, album=""):
        """Compute match confidence (0.0-1.0) similar to download-time logic.

        Uses word-overlap similarity between expected artist/title/album and
        candidate artist/title/album. Threshold >= 0.6 is considered confident
        (same as download-time).
        """
        from utils.metadata_enricher_utils import _similarity

        artist_sim = 0.0
        title_sim = 0.0
        album_sim = 0.0

        if artist and candidate.get("artist"):
            artist_sim = _similarity(artist, candidate["artist"])
        if title and candidate.get("title"):
            title_sim = _similarity(title, candidate["title"])
        if album and candidate.get("album"):
            album_sim = _similarity(album, candidate["album"])

        if album:
            return (artist_sim * 0.35 + title_sim * 0.35 + album_sim * 0.30)
        return (artist_sim * 0.5 + title_sim * 0.5)

    def _finish_batch(self):
        """Show summary and clean up."""
        if self._batch_progress:
            self._batch_progress.close()
            self._batch_progress = None

        self.refresh_files_list()

        def _s(count):
            return "" if count == 1 else "s"

        lines = []
        if self._batch_do_metadata:
            c = self._batch_meta_found
            lines.append(t("batch.status_meta", count=c, count_s=_s(c)))
        if self._batch_do_lyrics:
            c = self._batch_lyrics_found
            lines.append(t("batch.status_lyrics", count=c, count_s=_s(c)))
        c = self._batch_ignored
        lines.append(t("batch.status_ignored", count=c, count_s=_s(c)))
        if self._batch_failed > 0:
            c = self._batch_failed
            lines.append(t("batch.status_failed", count=c, count_s=_s(c)))

        prefix = t("batch.done_title")
        msg = prefix + "\n\n" + "\n".join(lines) if lines else prefix

        QMessageBox.information(self, t("batch.dialog_title"), msg)

        self._batch_files = []
        self._batch_cancelled = False
