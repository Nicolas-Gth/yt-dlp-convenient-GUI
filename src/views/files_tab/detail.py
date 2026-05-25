import os
import warnings

from PySide6.QtWidgets import (
    QTableWidgetItem, QFileDialog, QMessageBox, QDialog, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QScrollArea, QWidget, QGridLayout, QSizePolicy, QLayout,
    QLineEdit, QStackedWidget, QTextEdit, QListWidget, QListWidgetItem
)
from PySide6.QtCore import Qt, QTimer, QRect, QPoint, QSize, QThread, Signal
from PySide6.QtGui import QPixmap

from utils.i18n_utils import t

from .metadata import _load_audio, _extract_artwork, _extract_all_metadata, _extract_lyrics_text, _tag_label, _embed_artwork
from .widgets import _FlowLayout
from .constants import _FIELD_KEYS, _FIELD_LABELS


class FilesDetailMixin:
    """Mixin that populates the right-side detail panel."""

    def _clear_meta_panel(self):
        """Remove all rows and cell widgets from the metadata table."""
        for r in range(self._files_meta.rowCount()):
            if self._files_meta.cellWidget(r, 1):
                self._files_meta.removeCellWidget(r, 1)
        self._files_meta.setRowCount(0)

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
            self._lyrics_search_btn.hide()
            QTimer.singleShot(0, self._show_empty_detail)
            return

        self._artwork_wrapper.show()

        if self._current_detail_filepath != filepath:
            self._media_player.stop()
            self._seek_slider.setValue(0)
        self._current_detail_filepath = filepath
        self._play_btn.setEnabled(True)
        self._seek_slider.setEnabled(True)

        audio = _load_audio(filepath)
        if audio is None:
            self._clear_meta_panel()
            self._files_artwork.setArtwork(None)
            self._edit_btn_bar.hide()
            self._lyrics_search_btn.hide()
            return

        # Artwork
        pix = _extract_artwork(audio)
        self._files_artwork.setArtwork(pix if pix and not pix.isNull() else None)

        # Metadata table — clear old cell widgets first
        self._clear_meta_panel()
        self._modified_rows.clear()
        self._edited = False
        self._edit_btn_bar.show()
        self._edit_reset_btn.hide()
        self._edit_save_btn.hide()
        self._files_meta.blockSignals(True)

        # Extract values for always-shown fields
        meta_dict = {}
        for k, v in _extract_all_metadata(audio):
            meta_dict[k] = v

        fixed = []
        for field_name in ('title', 'artist', 'album', 'year', 'tracknumber', 'genre'):
            val = ''
            raw_key = ''
            for candidate in _FIELD_KEYS[field_name]:
                if candidate in meta_dict and meta_dict[candidate]:
                    val = meta_dict[candidate]
                    raw_key = candidate
                    break
            fixed.append((field_name, raw_key, val))
            # Remove from meta_dict so they don't appear twice
            for candidate in _FIELD_KEYS[field_name]:
                meta_dict.pop(candidate, None)

        # Remaining tags (sorted alphabetically)
        remaining = sorted(meta_dict.items(), key=lambda r: r[0].lower())

        num_rows = 1 + len(fixed) + len(remaining)  # filename + fixed + remaining
        self._files_meta.setRowCount(num_rows)

        row = 0
        # Filename
        self._files_meta.setRowHeight(row, 22)
        ki = QTableWidgetItem(t("tag.filename"))
        ki.setFlags(Qt.NoItemFlags)
        self._files_meta.setItem(row, 0, ki)
        vi = QTableWidgetItem(os.path.basename(filepath))
        vi.setFlags(Qt.ItemIsEnabled | Qt.ItemIsEditable)
        vi.setData(Qt.UserRole, '_filename_')
        self._files_meta.setItem(row, 1, vi)
        row += 1

        # Fixed fields
        for field_name, raw_key, val in fixed:
            self._files_meta.setRowHeight(row, 22)
            ki = QTableWidgetItem(t(_FIELD_LABELS[field_name]))
            ki.setFlags(Qt.NoItemFlags)
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
            ki.setFlags(Qt.NoItemFlags)
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
        self._lyrics_search_btn.setVisible(True)

        self._files_meta.blockSignals(False)
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', RuntimeWarning)
            try:
                self._files_meta.itemChanged.disconnect(self._on_meta_item_changed)
            except (TypeError, RuntimeError):
                pass
        self._files_meta.itemChanged.connect(self._on_meta_item_changed)

    def _on_edit_artwork_clicked(self):
        """Show a dialog to choose between local file or online search for cover art."""
        filepath = self._current_detail_filepath
        if not filepath or not os.path.isfile(filepath):
            return

        dlg = QDialog(self)
        dlg.setWindowTitle(t("artwork.edit_title"))
        dlg.setMinimumWidth(420)
        layout = QVBoxLayout(dlg)
        layout.setSpacing(12)

        lbl = QLabel(t("artwork.edit_prompt"))
        lbl.setWordWrap(True)
        lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl)

        btn_row = QHBoxLayout()
        btn_local = QPushButton(t("artwork.btn_local"))
        btn_local.setCursor(Qt.PointingHandCursor)
        btn_local.clicked.connect(lambda: dlg.done(1))
        btn_row.addWidget(btn_local)

        btn_search = QPushButton(t("artwork.btn_search"))
        btn_search.setCursor(Qt.PointingHandCursor)
        btn_search.clicked.connect(lambda: dlg.done(2))
        btn_row.addWidget(btn_search)

        btn_cancel = QPushButton(t("button.cancel"))
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.clicked.connect(dlg.reject)
        btn_row.addWidget(btn_cancel)
        layout.addLayout(btn_row)

        result = dlg.exec()
        if result == 1:
            self._choose_local_artwork(filepath)
        elif result == 2:
            self._show_cover_selector(filepath)

    def _choose_local_artwork(self, filepath: str):
        """Let the user pick an image file and embed it."""
        image_path, _ = QFileDialog.getOpenFileName(
            self, t("artwork.file_dialog_title"), "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if not image_path or not os.path.isfile(image_path):
            return
        try:
            with open(image_path, 'rb') as f:
                image_data = f.read()
        except Exception as e:
            QMessageBox.warning(self, t("artwork.error_title"), str(e))
            return
        mime = "image/png" if image_path.lower().endswith('.png') else "image/jpeg"
        if _embed_artwork(filepath, image_data, mime):
            self._show_file_detail(filepath)
        else:
            QMessageBox.warning(self, t("artwork.error_title"), t("artwork.error_msg"))

    def _show_cover_selector(self, filepath: str):
        """Show a dialog with cover art candidates. Dialog appears immediately with a spinner."""
        from utils.metadata_enricher_utils import search_cover_art_itunes, search_cover_art_musicbrainz, _request
        from PySide6.QtWidgets import QApplication, QComboBox

        class SearchWorker(QThread):
            results_ready = Signal(list, int, bool)  # (new_results, limit_used, has_more)
            error = Signal()

            def __init__(self, api_name, query, artist, album, title, limit, seen):
                super().__init__()
                self.api_name = api_name
                self.query = query
                self.artist = artist
                self.album = album
                self.title = title
                self.limit = limit
                self.seen = seen

            def run(self):
                try:
                    if self.api_name == "MusicBrainz":
                        raw = search_cover_art_musicbrainz(
                            self.query, artist=self.artist, album=self.album,
                            title=self.title, limit=self.limit
                        )
                    else:
                        raw = search_cover_art_itunes(
                            self.query, artist=self.artist, album=self.album,
                            title=self.title, limit=self.limit
                        )
                except Exception:
                    raw = []
                if self.isInterruptionRequested():
                    return
                new_items = []
                for item in raw:
                    url = item.get("artwork_url", "")
                    if url and url not in self.seen:
                        self.seen.add(url)
                        new_items.append(item)
                # If API returned fewer results than requested, there are no more pages
                has_more = len(raw) >= self.limit
                self.results_ready.emit(new_items, self.limit, has_more)

        dlg = QDialog(self)
        dlg.setWindowTitle(t("artwork.select_title"))
        dlg.setMinimumWidth(500)
        dlg.setMinimumHeight(400)
        dlg.resize(750, 550)
        layout = QVBoxLayout(dlg)
        layout.setSpacing(8)

        # API selector + Artist + Type + Term + Search button
        search_row = QHBoxLayout()
        api_combo = QComboBox()
        api_combo.addItem("iTunes")
        api_combo.addItem("MusicBrainz")
        api_combo.setCursor(Qt.PointingHandCursor)
        search_row.addWidget(api_combo)

        artist_edit = QLineEdit()
        artist_edit.setPlaceholderText(t("files.artist"))
        artist_edit.setClearButtonEnabled(True)
        search_row.addWidget(artist_edit, 1)

        type_combo = QComboBox()
        type_combo.addItem(t("tag.album"))
        type_combo.addItem(t("files.title"))
        type_combo.setCursor(Qt.PointingHandCursor)
        search_row.addWidget(type_combo)

        search_term_edit = QLineEdit()
        search_term_edit.setPlaceholderText(t("tag.album"))
        search_term_edit.setClearButtonEnabled(True)
        search_row.addWidget(search_term_edit, 1)

        search_btn = QPushButton(t("artwork.search_btn"))
        search_btn.setCursor(Qt.PointingHandCursor)
        search_btn.setDefault(True)
        search_row.addWidget(search_btn)
        layout.addLayout(search_row)

        # Spinner (centered in its own page)
        spinner_lbl = QLabel(t("artwork.loading"))
        spinner_lbl.setAlignment(Qt.AlignCenter)
        spinner_lbl.setStyleSheet("QLabel { font-size: 14px; color: palette(text); padding: 40px; }")
        spinner_container = QWidget()
        spinner_layout = QVBoxLayout(spinner_container)
        spinner_layout.addStretch()
        spinner_layout.addWidget(spinner_lbl, alignment=Qt.AlignCenter)
        spinner_layout.addStretch()

        # Results scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        container = QWidget()
        flow_container = QWidget()
        flow = _FlowLayout(flow_container, spacing=16)
        flow.setContentsMargins(8, 8, 8, 8)

        selected_url = [None]
        selected_card_border = [None]
        no_results_lbl = QLabel(t("artwork.no_results"))
        no_results_lbl.setAlignment(Qt.AlignCenter)
        no_results_lbl.hide()

        all_results = []
        seen_urls = set()
        current_limit = [10]
        current_query = [""]
        current_artist = [""]
        current_album = [""]
        current_title = [""]
        current_search_type = [0]  # 0 = album, 1 = title
        current_worker = [None]

        def _on_pick(url: str, card: QWidget):
            selected_url[0] = url
            apply_btn.setEnabled(True)
            if selected_card_border[0] is not None:
                prev = selected_card_border[0]
                prev.setStyleSheet(f"#{prev.objectName()}:hover {{ background-color: palette(midlight); border-radius: 4px; }}")
            card.setStyleSheet(
                f"#{card.objectName()} {{ border: 2px solid palette(highlight); border-radius: 4px; }}"
                f" #{card.objectName()}:hover {{ background-color: palette(midlight); border-radius: 4px; }}"
            )
            selected_card_border[0] = card

        def _clear_flow():
            while flow.count():
                item = flow.takeAt(0)
                w = item.widget()
                if w:
                    w.deleteLater()
            selected_card_border[0] = None

        def _build_cards():
            _clear_flow()
            no_results_lbl.setVisible(not all_results)
            for i, item in enumerate(all_results):
                card = QWidget()
                card.setObjectName(f"cover_card_{i}")
                card.setCursor(Qt.PointingHandCursor)
                card.setFixedSize(170, 240)
                card.setStyleSheet(f"#{card.objectName()}:hover {{ background-color: palette(midlight); border-radius: 4px; }}")
                card_layout = QVBoxLayout(card)
                card_layout.setContentsMargins(6, 6, 6, 6)
                card_layout.setSpacing(6)

                thumb_lbl = QLabel()
                thumb_lbl.setAlignment(Qt.AlignCenter)
                thumb_lbl.setFixedSize(150, 150)
                thumb_lbl.setStyleSheet("QLabel { background: transparent; }")
                data = item.get("artwork_data")
                if data:
                    pix = QPixmap()
                    pix.loadFromData(data)
                    if not pix.isNull():
                        thumb_lbl.setPixmap(pix.scaled(150, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                card_layout.addWidget(thumb_lbl, alignment=Qt.AlignCenter)

                album_lbl = QLabel(item.get("album", "") or item.get("track", ""))
                album_lbl.setWordWrap(True)
                album_lbl.setAlignment(Qt.AlignCenter)
                album_lbl.setFixedSize(150, 40)
                card_layout.addWidget(album_lbl)

                artist_lbl = QLabel(item.get("artist", ""))
                artist_lbl.setWordWrap(True)
                artist_lbl.setAlignment(Qt.AlignCenter)
                artist_lbl.setFixedSize(150, 22)
                card_layout.addWidget(artist_lbl)

                url = item.get("artwork_url", "")
                card.mousePressEvent = lambda _e, u=url, c=card: _on_pick(u, c)
                thumb_lbl.mousePressEvent = lambda _e, u=url, c=card: _on_pick(u, c)
                album_lbl.mousePressEvent = lambda _e, u=url, c=card: _on_pick(u, c)
                artist_lbl.mousePressEvent = lambda _e, u=url, c=card: _on_pick(u, c)

                flow.addWidget(card)

        def _set_loading(loading: bool):
            stack.setCurrentIndex(0 if loading else 1)
            search_btn.setEnabled(not loading)
            artist_edit.setEnabled(not loading)
            type_combo.setEnabled(not loading)
            search_term_edit.setEnabled(not loading)
            load_more_btn.setEnabled(not loading)
            api_combo.setEnabled(not loading)

        def _start_worker(query: str, artist: str, album: str, title: str, limit: int):
            old = current_worker[0]
            if old is not None:
                try:
                    old.results_ready.disconnect()
                except Exception:
                    pass
                try:
                    old.error.disconnect()
                except Exception:
                    pass
                try:
                    old.finished.disconnect()
                except Exception:
                    pass
                old.requestInterruption()
                old.wait(2000)
            api_name = api_combo.currentText()
            worker = SearchWorker(api_name, query, artist, album, title, limit, seen_urls)
            current_worker[0] = worker

            def _on_results(new_items, limit_used, has_more):
                if current_worker[0] != worker:
                    return
                current_worker[0] = None
                _set_loading(False)
                all_results.extend(new_items)
                _build_cards()
                load_more_btn.setVisible(has_more and limit_used < 50)

            worker.results_ready.connect(_on_results)
            worker.error.connect(lambda: (_set_loading(False), load_more_btn.setVisible(False)))
            worker.finished.connect(worker.deleteLater)
            _set_loading(True)
            worker.start()

        def _do_search():
            artist = artist_edit.text().strip()
            term = search_term_edit.text().strip()
            if not artist and not term:
                return
            current_query[0] = ""
            current_artist[0] = artist
            current_search_type[0] = type_combo.currentIndex()
            is_title = type_combo.currentIndex() == 1
            current_album[0] = "" if is_title else term
            current_title[0] = term if is_title else ""
            current_limit[0] = 10
            all_results.clear()
            seen_urls.clear()
            selected_url[0] = None
            apply_btn.setEnabled(False)
            load_more_btn.setVisible(False)
            _start_worker("", artist, current_album[0], current_title[0], 10)

        def _on_load_more():
            current_limit[0] += 10
            load_more_btn.setVisible(False)
            _start_worker(
                "", current_artist[0], current_album[0],
                current_title[0], current_limit[0]
            )

        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)
        vbox.addWidget(flow_container)
        vbox.addWidget(no_results_lbl, alignment=Qt.AlignCenter)

        load_more_widget = QWidget()
        load_more_layout = QHBoxLayout(load_more_widget)
        load_more_layout.setContentsMargins(0, 8, 0, 8)
        load_more_layout.addStretch()
        load_more_btn = QPushButton(t("artwork.load_more"))
        load_more_btn.setCursor(Qt.PointingHandCursor)
        load_more_btn.clicked.connect(_on_load_more)
        load_more_layout.addWidget(load_more_btn)
        load_more_layout.addStretch()
        vbox.addWidget(load_more_widget)
        vbox.addStretch()

        scroll.setWidget(container)

        stack = QStackedWidget()
        stack.addWidget(spinner_container)
        stack.addWidget(scroll)
        layout.addWidget(stack, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton(t("button.cancel"))
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.clicked.connect(dlg.reject)
        btn_row.addWidget(cancel_btn)

        apply_btn = QPushButton(t("artwork.apply"))
        apply_btn.setCursor(Qt.PointingHandCursor)
        apply_btn.setEnabled(False)
        apply_btn.clicked.connect(dlg.accept)
        btn_row.addWidget(apply_btn)
        layout.addLayout(btn_row)

        def _on_type_changed(index):
            search_term_edit.setPlaceholderText(t("files.title") if index == 1 else t("tag.album"))

        type_combo.currentIndexChanged.connect(_on_type_changed)

        search_btn.clicked.connect(_do_search)
        artist_edit.returnPressed.connect(_do_search)
        search_term_edit.returnPressed.connect(_do_search)

        # Prevent Enter/Return from closing the dialog
        original_key_press = dlg.keyPressEvent
        def _dlg_key_press(event):
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                focused = dlg.focusWidget()
                if focused in (artist_edit, search_term_edit):
                    _do_search()
                    return
                event.ignore()
                return
            original_key_press(event)
        dlg.keyPressEvent = _dlg_key_press

        def _cleanup():
            old = current_worker[0]
            if old is not None:
                try:
                    old.results_ready.disconnect()
                except Exception:
                    pass
                try:
                    old.error.disconnect()
                except Exception:
                    pass
                try:
                    old.finished.disconnect()
                except Exception:
                    pass
                old.requestInterruption()
                old.wait(5000)
        dlg.finished.connect(_cleanup)

        # ── Show dialog immediately, then load data ──
        dlg.show()
        dlg.raise_()
        QApplication.processEvents()

        # Read file metadata (fast, local)
        audio = _load_audio(filepath)
        artist, title, album = "", "", ""
        if audio is not None and audio.tags is not None:
            from mutagen.mp4 import MP4
            from mutagen.oggopus import OggOpus
            try:
                if isinstance(audio, OggOpus):
                    artist = "; ".join(audio.tags.get('artist', []) or []).strip()
                    title = "; ".join(audio.tags.get('title', []) or []).strip()
                    album = "; ".join(audio.tags.get('album', []) or []).strip()
                elif isinstance(audio, MP4):
                    artist = (audio.tags.get('\xa9ART', [None])[0] or "").strip()
                    title = (audio.tags.get('\xa9nam', [None])[0] or "").strip()
                    album = (audio.tags.get('\xa9alb', [None])[0] or "").strip()
                else:  # MP3
                    artist = "; ".join(audio.tags.get('TPE1') or []).strip()
                    title = "; ".join(audio.tags.get('TIT2') or []).strip()
                    album = "; ".join(audio.tags.get('TALB') or []).strip()
            except Exception:
                pass

        # Fallback to filename if no tags
        filename = os.path.splitext(os.path.basename(filepath))[0]
        clean_album = album if album and album.lower() not in ("unknown album", "") else ""
        artist_edit.setText(artist)

        if clean_album:
            type_combo.setCurrentIndex(0)
            search_term_edit.setText(clean_album)
            search_term_edit.setPlaceholderText(t("tag.album"))
            current_album[0] = clean_album
            current_title[0] = ""
        elif title:
            type_combo.setCurrentIndex(1)
            search_term_edit.setText(title)
            search_term_edit.setPlaceholderText(t("files.title"))
            current_album[0] = ""
            current_title[0] = title
        else:
            # No tags: use filename as title search term
            type_combo.setCurrentIndex(1)
            search_term_edit.setText(filename)
            search_term_edit.setPlaceholderText(t("files.title"))
            current_album[0] = ""
            current_title[0] = filename

        current_query[0] = ""
        current_artist[0] = artist
        current_search_type[0] = type_combo.currentIndex()
        current_limit[0] = 10
        _start_worker("", artist, current_album[0], current_title[0], 10)

        if dlg.exec() != QDialog.Accepted or not selected_url[0]:
            return

        cover_data = _request(selected_url[0], timeout=15)
        if cover_data and len(cover_data) > 1000:
            mime = "image/png" if cover_data[:4] == b'\x89PNG' else "image/jpeg"
            if _embed_artwork(filepath, cover_data, mime):
                self._show_file_detail(filepath)
            else:
                QMessageBox.warning(self, t("artwork.error_title"), t("artwork.error_msg"))
        else:
            QMessageBox.warning(self, t("artwork.error_title"), t("artwork.error_msg"))

    def _on_identify_metadata(self):
        """Open metadata identification dialog for the current file."""
        filepath = self._current_detail_filepath
        if not filepath or not os.path.isfile(filepath):
            return
        self._show_metadata_selector(filepath)

    def _show_metadata_selector(self, filepath: str):
        """Show a dialog with metadata candidates. Same UI as cover selector."""
        from utils.metadata_enricher_utils import search_metadata_candidates, search_metadata_itunes, _request
        from PySide6.QtWidgets import QApplication, QComboBox

        dlg = QDialog(self)
        dlg.setWindowTitle(t("metadata.identify_title"))
        dlg.setMinimumWidth(500)
        dlg.setMinimumHeight(400)
        dlg.resize(750, 550)
        layout = QVBoxLayout(dlg)
        layout.setSpacing(8)

        # API selector + Artist + Type + Term + Search button
        search_row = QHBoxLayout()
        api_combo = QComboBox()
        api_combo.addItem("iTunes")
        api_combo.addItem("MusicBrainz")
        api_combo.setCurrentIndex(0)
        api_combo.setCursor(Qt.PointingHandCursor)
        search_row.addWidget(api_combo)

        artist_edit = QLineEdit()
        artist_edit.setPlaceholderText(t("files.artist"))
        artist_edit.setClearButtonEnabled(True)
        search_row.addWidget(artist_edit, 1)

        album_edit = QLineEdit()
        album_edit.setPlaceholderText(t("tag.album"))
        album_edit.setClearButtonEnabled(True)
        search_row.addWidget(album_edit, 1)

        title_edit = QLineEdit()
        title_edit.setPlaceholderText(t("files.title"))
        title_edit.setClearButtonEnabled(True)
        search_row.addWidget(title_edit, 1)

        search_btn = QPushButton(t("artwork.search_btn"))
        search_btn.setCursor(Qt.PointingHandCursor)
        search_btn.setDefault(True)
        search_row.addWidget(search_btn)
        layout.addLayout(search_row)

        # Spinner (centered in its own page)
        spinner_lbl = QLabel(t("artwork.loading"))
        spinner_lbl.setAlignment(Qt.AlignCenter)
        spinner_lbl.setStyleSheet("QLabel { font-size: 14px; color: palette(text); padding: 40px; }")
        spinner_container = QWidget()
        spinner_layout = QVBoxLayout(spinner_container)
        spinner_layout.addStretch()
        spinner_layout.addWidget(spinner_lbl, alignment=Qt.AlignCenter)
        spinner_layout.addStretch()

        # Results scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        container = QWidget()
        flow_container = QWidget()
        flow = _FlowLayout(flow_container, spacing=16)
        flow.setContentsMargins(8, 8, 8, 8)

        selected_result = [None]
        selected_card_border = [None]
        no_results_lbl = QLabel(t("artwork.no_results"))
        no_results_lbl.setAlignment(Qt.AlignCenter)
        no_results_lbl.hide()

        all_results = []
        seen_ids = set()
        current_limit = [10]
        current_artist = [""]
        current_album = [""]
        current_title = [""]
        current_api = ["MusicBrainz"]
        current_worker = [None]

        def _on_pick(result: dict, card: QWidget):
            selected_result[0] = result
            apply_btn.setEnabled(True)
            if selected_card_border[0] is not None:
                prev = selected_card_border[0]
                prev.setStyleSheet(f"#{prev.objectName()}:hover {{ background-color: palette(midlight); border-radius: 4px; }}")
            card.setStyleSheet(
                f"#{card.objectName()} {{ border: 2px solid palette(highlight); border-radius: 4px; }}"
                f" #{card.objectName()}:hover {{ background-color: palette(midlight); border-radius: 4px; }}"
            )
            selected_card_border[0] = card

        def _clear_flow():
            while flow.count():
                item = flow.takeAt(0)
                w = item.widget()
                if w:
                    w.deleteLater()
            selected_card_border[0] = None

        def _build_cards():
            _clear_flow()
            no_results_lbl.setVisible(not all_results)
            for i, item in enumerate(all_results):
                card = QWidget()
                card.setObjectName(f"meta_card_{i}")
                card.setCursor(Qt.PointingHandCursor)
                card.setFixedSize(200, 280)
                card.setStyleSheet(f"#{card.objectName()}:hover {{ background-color: palette(midlight); border-radius: 4px; }}")
                card_layout = QVBoxLayout(card)
                card_layout.setContentsMargins(8, 8, 8, 8)
                card_layout.setSpacing(4)

                thumb_lbl = QLabel()
                thumb_lbl.setAlignment(Qt.AlignCenter)
                thumb_lbl.setFixedSize(150, 150)
                thumb_lbl.setStyleSheet("QLabel { background: transparent; }")
                data = item.get("artwork_data")
                if data:
                    pix = QPixmap()
                    pix.loadFromData(data)
                    if not pix.isNull():
                        thumb_lbl.setPixmap(pix.scaled(150, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                card_layout.addWidget(thumb_lbl, alignment=Qt.AlignCenter)

                title_lbl = QLabel(item.get("title", ""))
                title_lbl.setWordWrap(True)
                title_lbl.setAlignment(Qt.AlignCenter)
                title_lbl.setFixedSize(180, 30)
                f = title_lbl.font(); f.setBold(True); title_lbl.setFont(f)
                card_layout.addWidget(title_lbl)

                artist_lbl = QLabel(item.get("artist", ""))
                artist_lbl.setWordWrap(True)
                artist_lbl.setAlignment(Qt.AlignCenter)
                artist_lbl.setFixedSize(180, 20)
                card_layout.addWidget(artist_lbl)

                album_text = item.get("album", "")
                year = item.get("date", "")
                if year:
                    album_text += f" ({year})"
                album_lbl = QLabel(album_text)
                album_lbl.setWordWrap(True)
                album_lbl.setAlignment(Qt.AlignCenter)
                album_lbl.setFixedSize(180, 20)
                album_lbl.setStyleSheet("QLabel { color: palette(dark); font-size: 11px; }")
                card_layout.addWidget(album_lbl)

                info_parts = []
                if item.get("genre"):
                    info_parts.append(item["genre"])
                if item.get("track_number") and item.get("total_tracks"):
                    info_parts.append(f"Track {item['track_number']}/{item['total_tracks']}")
                info_lbl = QLabel("  |  ".join(info_parts))
                info_lbl.setWordWrap(True)
                info_lbl.setAlignment(Qt.AlignCenter)
                info_lbl.setFixedSize(180, 20)
                info_lbl.setStyleSheet("QLabel { color: palette(dark); font-size: 10px; }")
                card_layout.addWidget(info_lbl)

                card.mousePressEvent = lambda _e, r=item, c=card: _on_pick(r, c)
                thumb_lbl.mousePressEvent = lambda _e, r=item, c=card: _on_pick(r, c)
                title_lbl.mousePressEvent = lambda _e, r=item, c=card: _on_pick(r, c)
                artist_lbl.mousePressEvent = lambda _e, r=item, c=card: _on_pick(r, c)
                album_lbl.mousePressEvent = lambda _e, r=item, c=card: _on_pick(r, c)
                info_lbl.mousePressEvent = lambda _e, r=item, c=card: _on_pick(r, c)

                flow.addWidget(card)

        def _set_loading(loading: bool):
            stack.setCurrentIndex(0 if loading else 1)
            search_btn.setEnabled(not loading)
            artist_edit.setEnabled(not loading)
            album_edit.setEnabled(not loading)
            title_edit.setEnabled(not loading)
            load_more_btn.setEnabled(not loading)
            api_combo.setEnabled(not loading)

        class IdentifyWorker(QThread):
            results_ready = Signal(list, int, bool)
            error = Signal()

            def __init__(self, artist, album, title, limit, seen, api):
                super().__init__()
                self.artist = artist
                self.album = album
                self.title = title
                self.limit = limit
                self.seen = seen
                self.api = api

            def run(self):
                try:
                    if self.api == "iTunes":
                        raw = search_metadata_itunes(self.artist, self.title, self.album, limit=self.limit)
                    else:
                        raw = search_metadata_candidates(self.artist, self.title, self.album, limit=self.limit)
                except Exception:
                    raw = []
                if self.isInterruptionRequested():
                    return
                new_items = []
                for item in raw:
                    rid = item.get("mb_release_group_id") or item.get("mb_release_id") or item.get("itunes_track_id")
                    if rid and rid not in self.seen:
                        self.seen.add(rid)
                        new_items.append(item)
                has_more = len(raw) >= self.limit
                self.results_ready.emit(new_items, self.limit, has_more)

        def _start_worker(artist: str, album: str, title: str, limit: int):
            old = current_worker[0]
            if old is not None:
                try:
                    old.results_ready.disconnect()
                except Exception:
                    pass
                try:
                    old.error.disconnect()
                except Exception:
                    pass
                try:
                    old.finished.disconnect()
                except Exception:
                    pass
                old.requestInterruption()
                old.wait(2000)
            worker = IdentifyWorker(artist, album, title, limit, seen_ids, current_api[0])
            current_worker[0] = worker

            def _on_results(new_items, limit_used, has_more):
                if current_worker[0] != worker:
                    return
                current_worker[0] = None
                all_results.extend(new_items)
                _set_loading(False)
                _build_cards()
                load_more_btn.setVisible(has_more and limit_used < 50)

            worker.results_ready.connect(_on_results)
            worker.error.connect(lambda: (_set_loading(False), load_more_btn.setVisible(False)))
            worker.finished.connect(worker.deleteLater)
            _set_loading(True)
            worker.start()

        def _do_search():
            artist = artist_edit.text().strip()
            album = album_edit.text().strip()
            title = title_edit.text().strip()
            if not artist and not album and not title:
                return
            current_artist[0] = artist
            current_album[0] = album
            current_title[0] = title
            current_limit[0] = 10
            current_api[0] = api_combo.currentText()
            all_results.clear()
            seen_ids.clear()
            selected_result[0] = None
            apply_btn.setEnabled(False)
            load_more_btn.setVisible(False)
            _start_worker(artist, album, title, 10)

        def _on_load_more():
            current_limit[0] += 10
            load_more_btn.setVisible(False)
            _start_worker(current_artist[0], current_album[0], current_title[0], current_limit[0])

        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)
        vbox.addWidget(flow_container)
        vbox.addWidget(no_results_lbl, alignment=Qt.AlignCenter)

        load_more_widget = QWidget()
        load_more_layout = QHBoxLayout(load_more_widget)
        load_more_layout.setContentsMargins(0, 8, 0, 8)
        load_more_layout.addStretch()
        load_more_btn = QPushButton(t("artwork.load_more"))
        load_more_btn.setCursor(Qt.PointingHandCursor)
        load_more_btn.clicked.connect(_on_load_more)
        load_more_layout.addWidget(load_more_btn)
        load_more_layout.addStretch()
        vbox.addWidget(load_more_widget)
        vbox.addStretch()

        scroll.setWidget(container)

        stack = QStackedWidget()
        stack.addWidget(spinner_container)
        stack.addWidget(scroll)
        layout.addWidget(stack, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton(t("button.cancel"))
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.clicked.connect(dlg.reject)
        btn_row.addWidget(cancel_btn)

        apply_btn = QPushButton(t("artwork.apply"))
        apply_btn.setCursor(Qt.PointingHandCursor)
        apply_btn.setEnabled(False)
        apply_btn.clicked.connect(dlg.accept)
        btn_row.addWidget(apply_btn)
        layout.addLayout(btn_row)

        search_btn.clicked.connect(_do_search)
        artist_edit.returnPressed.connect(_do_search)
        album_edit.returnPressed.connect(_do_search)
        title_edit.returnPressed.connect(_do_search)

        original_key_press = dlg.keyPressEvent
        def _dlg_key_press(event):
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                focused = dlg.focusWidget()
                if focused in (artist_edit, album_edit, title_edit):
                    _do_search()
                    return
                event.ignore()
                return
            original_key_press(event)
        dlg.keyPressEvent = _dlg_key_press

        def _cleanup():
            old = current_worker[0]
            if old is not None:
                try:
                    old.results_ready.disconnect()
                except Exception:
                    pass
                try:
                    old.error.disconnect()
                except Exception:
                    pass
                try:
                    old.finished.disconnect()
                except Exception:
                    pass
                old.requestInterruption()
                old.wait(5000)
        dlg.finished.connect(_cleanup)

        # ── Show dialog immediately, then load data ──
        dlg.show()
        dlg.raise_()
        QApplication.processEvents()

        # Read file metadata (fast, local)
        audio = _load_audio(filepath)
        artist, title, album = "", "", ""
        if audio is not None and audio.tags is not None:
            from mutagen.mp4 import MP4
            from mutagen.oggopus import OggOpus
            try:
                if isinstance(audio, OggOpus):
                    artist = "; ".join(audio.tags.get('artist', []) or []).strip()
                    title = "; ".join(audio.tags.get('title', []) or []).strip()
                    album = "; ".join(audio.tags.get('album', []) or []).strip()
                elif isinstance(audio, MP4):
                    artist = (audio.tags.get('\xa9ART', [None])[0] or "").strip()
                    title = (audio.tags.get('\xa9nam', [None])[0] or "").strip()
                    album = (audio.tags.get('\xa9alb', [None])[0] or "").strip()
                else:
                    artist = "; ".join(audio.tags.get('TPE1') or []).strip()
                    title = "; ".join(audio.tags.get('TIT2') or []).strip()
                    album = "; ".join(audio.tags.get('TALB') or []).strip()
            except Exception:
                pass

        clean_album = album if album and album.lower() not in ("unknown album", "") else ""
        artist_edit.setText(artist)
        album_edit.setText(clean_album)
        title_edit.setText(title)

        if not clean_album and not title:
            filename = os.path.splitext(os.path.basename(filepath))[0]
            title_edit.setText(filename)

        current_artist[0] = artist
        current_album[0] = clean_album
        current_title[0] = title if title else (filename if not clean_album else "")
        current_limit[0] = 10
        current_api[0] = api_combo.currentText()
        _start_worker(current_artist[0], current_album[0], current_title[0], 10)

        if dlg.exec() != QDialog.Accepted or not selected_result[0]:
            return

        result = selected_result[0]
        self._apply_metadata_result(filepath, result)

    def _apply_metadata_result(self, filepath: str, result: dict):
        """Apply a metadata candidate to the audio file.

        Replaces ALL known fields. If a field is absent from the result,
        the existing tag is cleared/deleted.
        """
        from mutagen.mp3 import MP3
        from mutagen.mp4 import MP4
        from mutagen.oggopus import OggOpus
        from utils.metadata_enricher_utils import _request

        audio = _load_audio(filepath)
        if audio is None:
            QMessageBox.warning(self, t("artwork.error_title"), t("artwork.no_metadata"))
            return

        try:
            # ── Opus ──
            if isinstance(audio, OggOpus):
                tags = audio.tags
                for key in ("title", "artist", "album", "albumartist", "date", "genre", "tracknumber"):
                    if key in tags:
                        del tags[key]
                if result.get("title"):
                    tags["title"] = result["title"]
                if result.get("artist"):
                    tags["artist"] = result["artist"]
                if result.get("album"):
                    tags["album"] = result["album"]
                if result.get("album_artist"):
                    tags["albumartist"] = result["album_artist"]
                if result.get("date"):
                    tags["date"] = result["date"]
                if result.get("genre"):
                    tags["genre"] = result["genre"]
                if result.get("track_number"):
                    tags["tracknumber"] = result["track_number"]

            # ── MP4 ──
            elif isinstance(audio, MP4):
                tags = audio.tags
                for key in ("\xa9nam", "\xa9ART", "\xa9alb", "aART", "\xa9day", "\xa9gen", "trkn"):
                    if key in tags:
                        del tags[key]
                if result.get("title"):
                    tags["\xa9nam"] = [result["title"]]
                if result.get("artist"):
                    tags["\xa9ART"] = [result["artist"]]
                if result.get("album"):
                    tags["\xa9alb"] = [result["album"]]
                if result.get("album_artist"):
                    tags["aART"] = [result["album_artist"]]
                if result.get("date"):
                    tags["\xa9day"] = [result["date"]]
                if result.get("genre"):
                    tags["\xa9gen"] = [result["genre"]]
                if result.get("track_number"):
                    try:
                        tn = int(result["track_number"])
                        tt_raw = result.get("total_tracks", "")
                        tt = int(tt_raw) if str(tt_raw).strip() else 0
                        tags["trkn"] = [(tn, tt)]
                    except (ValueError, TypeError):
                        pass

            # ── MP3 ──
            else:
                from mutagen.id3 import ID3, TIT2, TPE1, TALB, TPE2, TDRC, TCON, TRCK
                if audio.tags is None:
                    audio.tags = ID3()
                tags = audio.tags
                for frame_id in ("TIT2", "TPE1", "TALB", "TPE2", "TDRC", "TCON", "TRCK", "APIC"):
                    tags.delall(frame_id)
                if result.get("title"):
                    tags["TIT2"] = TIT2(encoding=3, text=result["title"])
                if result.get("artist"):
                    tags["TPE1"] = TPE1(encoding=3, text=result["artist"])
                if result.get("album"):
                    tags["TALB"] = TALB(encoding=3, text=result["album"])
                if result.get("album_artist"):
                    tags["TPE2"] = TPE2(encoding=3, text=result["album_artist"])
                if result.get("date"):
                    tags["TDRC"] = TDRC(text=result["date"])
                if result.get("genre"):
                    tags["TCON"] = TCON(encoding=3, text=result["genre"])
                if result.get("track_number"):
                    total = result.get("total_tracks", "")
                    track_text = f"{result['track_number']}/{total}" if total else result["track_number"]
                    tags["TRCK"] = TRCK(encoding=3, text=track_text)

            # ── Cover art (pass audio_obj so text tags aren't overwritten) ──
            cover_url = result.get("artwork_url", "")
            if cover_url:
                cover_data = _request(cover_url, timeout=15)
                if cover_data and len(cover_data) > 1000:
                    mime = "image/png" if cover_data[:4] == b'\x89PNG' else "image/jpeg"
                    _embed_artwork(filepath, cover_data, mime, audio_obj=audio)

            audio.save()
            self._show_file_detail(filepath)
            self.refresh_files_list()
        except Exception as e:
            QMessageBox.warning(self, t("artwork.error_title"), str(e))

    def _on_search_lyrics(self):
        """Open lyrics search dialog for the current file."""
        filepath = self._current_detail_filepath
        if not filepath or not os.path.isfile(filepath):
            return
        self._show_lyrics_search_dialog(filepath)

    def _show_lyrics_search_dialog(self, filepath: str):
        """Show a dialog to search lyrics from LRCLIB and Genius."""
        from utils.metadata_enricher_utils import search_lyrics_lrclib, _fetch_lyrics_genius
        from PySide6.QtWidgets import QApplication

        # Read file metadata for pre-fill and duration
        audio = _load_audio(filepath)
        file_duration = 0
        artist, title, album = "", "", ""
        if audio is not None:
            try:
                file_duration = int(getattr(audio.info, 'length', 0))
            except Exception:
                pass
            if audio.tags is not None:
                from mutagen.mp4 import MP4
                from mutagen.oggopus import OggOpus
                try:
                    if isinstance(audio, OggOpus):
                        artist = "; ".join(audio.tags.get('artist', []) or []).strip()
                        title = "; ".join(audio.tags.get('title', []) or []).strip()
                        album = "; ".join(audio.tags.get('album', []) or []).strip()
                    elif isinstance(audio, MP4):
                        artist = (audio.tags.get('\xa9ART', [None])[0] or "").strip()
                        title = (audio.tags.get('\xa9nam', [None])[0] or "").strip()
                        album = (audio.tags.get('\xa9alb', [None])[0] or "").strip()
                    else:
                        artist = "; ".join(audio.tags.get('TPE1') or []).strip()
                        title = "; ".join(audio.tags.get('TIT2') or []).strip()
                        album = "; ".join(audio.tags.get('TALB') or []).strip()
                except Exception:
                    pass

        dlg = QDialog(self)
        dlg.setWindowTitle(t("lyrics.search_title"))
        dlg.setMinimumWidth(900)
        dlg.setMinimumHeight(500)
        layout = QVBoxLayout(dlg)
        layout.setSpacing(8)

        # Search fields — single row, no labels
        search_row = QHBoxLayout()
        search_row.setSpacing(6)
        title_edit = QLineEdit()
        title_edit.setPlaceholderText(t("files.title"))
        title_edit.setText(title)
        title_edit.setClearButtonEnabled(True)
        search_row.addWidget(title_edit, 2)

        album_edit = QLineEdit()
        album_edit.setPlaceholderText(t("tag.album"))
        album_edit.setText(album)
        album_edit.setClearButtonEnabled(True)
        search_row.addWidget(album_edit, 2)

        artist_edit = QLineEdit()
        artist_edit.setPlaceholderText(t("files.artist"))
        artist_edit.setText(artist)
        artist_edit.setClearButtonEnabled(True)
        search_row.addWidget(artist_edit, 2)

        search_btn = QPushButton(t("artwork.search_btn"))
        search_btn.setCursor(Qt.PointingHandCursor)
        search_btn.setDefault(True)
        search_row.addWidget(search_btn)
        layout.addLayout(search_row)

        # Splitter: results list (left) | lyrics preview (right)
        from PySide6.QtWidgets import QSplitter
        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.setHandleWidth(6)

        # Left: results list with header
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 6, 0)
        left_layout.setSpacing(4)
        results_label = QLabel(t("lyrics.results"))
        left_layout.addWidget(results_label)
        results_list = QListWidget()
        results_list.setSpacing(2)
        results_list.setStyleSheet(
            "QListWidget { border: 1px solid palette(mid); border-radius: 4px; }"
            "QListWidget::item { padding: 8px; border-bottom: 1px solid palette(midlight); }"
            "QListWidget::item:selected { background: palette(highlight); color: palette(highlighted-text); }"
        )
        left_layout.addWidget(results_list, 1)
        main_splitter.addWidget(left_container)

        # Right: lyrics preview with header
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(6, 0, 0, 0)
        right_layout.setSpacing(4)
        preview_label = QLabel(t("lyrics.preview"))
        right_layout.addWidget(preview_label)
        preview_edit = QTextEdit()
        preview_edit.setReadOnly(True)
        preview_edit.setPlaceholderText(t("files.no_lyrics"))
        preview_edit.setStyleSheet("QTextEdit { border: 1px solid palette(mid); border-radius: 4px; background: palette(base); }")
        right_layout.addWidget(preview_edit, 1)
        main_splitter.addWidget(right_container)
        main_splitter.setSizes([280, 420])

        layout.addWidget(main_splitter, 1)

        # Bottom buttons
        bottom_row = QHBoxLayout()
        bottom_row.addStretch()
        cancel_btn = QPushButton(t("button.cancel"))
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.clicked.connect(dlg.reject)
        bottom_row.addWidget(cancel_btn)

        apply_btn = QPushButton(t("artwork.apply"))
        apply_btn.setCursor(Qt.PointingHandCursor)
        apply_btn.setEnabled(False)
        apply_btn.clicked.connect(dlg.accept)
        bottom_row.addWidget(apply_btn)
        layout.addLayout(bottom_row)

        # State
        all_results = []
        selected_result = [None]
        current_worker = [None]

        def _format_duration_diff(result_duration) -> str:
            result_duration = int(result_duration) if result_duration else 0
            if result_duration <= 0 or file_duration <= 0:
                return ""
            diff = result_duration - file_duration
            if diff == 0:
                return ""
            sign = "+" if diff > 0 else ""
            minutes = abs(diff) // 60
            seconds = abs(diff) % 60
            return f"{sign}{minutes:02d}:{seconds:02d}"

        def _build_result_item(result: dict) -> QListWidgetItem:
            item = QListWidgetItem()
            title = result.get("title", "")
            artist = result.get("artist", "")
            lines = result.get("lines", 0)
            synced = result.get("synced", False)
            source = result.get("source", "")
            duration_diff = _format_duration_diff(result.get("duration", 0))

            # Line 1: Artist - Title
            line1 = f"{artist} - {title}" if artist and title else (artist or title)

            # Line 2: lines - synced status (+diff) - source
            line2_parts = []
            if lines > 0:
                line2_parts.append(f"{lines} {t('lyrics.lines')}")
            synced_text = t("lyrics.synced") if synced else t("lyrics.unsynced")
            if synced and duration_diff:
                synced_text += f" ({duration_diff})"
            line2_parts.append(synced_text)
            if source:
                line2_parts.append(source)
            line2 = " - ".join(line2_parts)

            full_text = f"{line1}\n{line2}"
            item.setText(full_text)
            item.setData(Qt.UserRole, result)
            return item

        def _add_results(results: list):
            for r in results:
                all_results.append(r)
                results_list.addItem(_build_result_item(r))
            if not all_results:
                item = QListWidgetItem(t("artwork.no_results"))
                item.setFlags(Qt.ItemIsEnabled)
                item.setTextAlignment(Qt.AlignCenter)
                results_list.addItem(item)

        def _set_loading(loading: bool):
            search_btn.setEnabled(not loading)
            title_edit.setEnabled(not loading)
            album_edit.setEnabled(not loading)
            artist_edit.setEnabled(not loading)
            if loading:
                results_list.clear()
                all_results.clear()
                item = QListWidgetItem(t("artwork.loading"))
                item.setFlags(Qt.NoItemFlags)
                item.setTextAlignment(Qt.AlignCenter)
                results_list.addItem(item)
                results_list.setCurrentItem(None)

        class LyricsSearchWorker(QThread):
            results_ready = Signal(list)

            def __init__(self, artist, title, album, duration):
                super().__init__()
                self.artist = artist
                self.title = title
                self.album = album
                self.duration = duration

            def _search_lrclib(self, album: str, limit: int = 10) -> list:
                try:
                    return search_lyrics_lrclib(self.artist, self.title, album, self.duration, limit=limit)
                except Exception:
                    return []

            def run(self):
                results = []
                seen = set()

                from concurrent.futures import ThreadPoolExecutor

                with ThreadPoolExecutor(max_workers=3) as pool:
                    # Submit all searches in parallel
                    f_album = pool.submit(self._search_lrclib, self.album, 10) if self.album else None
                    f_noalbum = pool.submit(self._search_lrclib, "", 10)
                    f_genius = pool.submit(_fetch_lyrics_genius, self.artist, self.title)

                    # Process album results first to ensure correct priority
                    tagged = []
                    if f_album:
                        try:
                            for r in (f_album.result(timeout=15) or []):
                                tagged.append((r, True))
                        except Exception:
                            pass
                    try:
                        for r in (f_noalbum.result(timeout=15) or []):
                            tagged.append((r, False))
                    except Exception:
                        pass

                    for r, album_match in tagged:
                        key = f"{r.get('artist', '')}|{r.get('title', '')}"
                        if key not in seen:
                            seen.add(key)
                            r["_album_match"] = album_match
                            results.append(r)

                    # Genius fallback
                    try:
                        genius_lyrics = f_genius.result(timeout=15)
                        if genius_lyrics:
                            lines_count = len(genius_lyrics.splitlines())
                            results.append({
                                "title": self.title,
                                "artist": self.artist,
                                "album": "",
                                "lines": lines_count,
                                "synced": False,
                                "source": "Genius",
                                "duration": 0,
                                "lyrics": genius_lyrics,
                                "lyrics_type": "plain",
                                "_album_match": False,
                            })
                    except Exception:
                        pass

                # Sort: album-matched first, then by duration match / synced
                def _sort_key(r):
                    score = 0
                    if r.get("_album_match"):
                        score += 10000
                    dur = r.get("duration", 0)
                    if dur > 0 and self.duration > 0:
                        score += -abs(dur - self.duration)
                    if r.get("synced"):
                        score += 1000
                    return score

                results.sort(key=_sort_key, reverse=True)
                if not self.isInterruptionRequested():
                    self.results_ready.emit(results)

        def _do_search():
            a = artist_edit.text().strip()
            t_ = title_edit.text().strip()
            if not a and not t_:
                return
            _set_loading(True)
            selected_result[0] = None
            apply_btn.setEnabled(False)
            preview_edit.clear()

            old = current_worker[0]
            if old is not None:
                try:
                    old.results_ready.disconnect()
                except Exception:
                    pass
                try:
                    old.finished.disconnect()
                except Exception:
                    pass
                old.requestInterruption()
                old.wait(2000)
            worker = LyricsSearchWorker(a, t_, album_edit.text().strip(), file_duration)
            current_worker[0] = worker

            def _on_results(results):
                if current_worker[0] != worker:
                    return
                current_worker[0] = None
                results_list.clear()
                all_results.clear()
                _add_results(results)
                search_btn.setEnabled(True)
                title_edit.setEnabled(True)
                album_edit.setEnabled(True)
                artist_edit.setEnabled(True)

            worker.results_ready.connect(_on_results)
            worker.finished.connect(worker.deleteLater)
            worker.start()

        def _on_item_clicked(item: QListWidgetItem):
            result = item.data(Qt.UserRole)
            if not result:
                return
            selected_result[0] = result
            apply_btn.setEnabled(True)
            lyrics = result.get("lyrics", "")
            preview_edit.setPlainText(lyrics)

        search_btn.clicked.connect(_do_search)
        title_edit.returnPressed.connect(_do_search)
        album_edit.returnPressed.connect(_do_search)
        artist_edit.returnPressed.connect(_do_search)
        results_list.itemClicked.connect(_on_item_clicked)

        original_key_press = dlg.keyPressEvent
        def _dlg_key_press(event):
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                focused = dlg.focusWidget()
                if focused in (title_edit, album_edit, artist_edit):
                    _do_search()
                    return
                event.ignore()
                return
            original_key_press(event)
        dlg.keyPressEvent = _dlg_key_press

        def _cleanup():
            old = current_worker[0]
            if old is not None:
                try:
                    old.results_ready.disconnect()
                except Exception:
                    pass
                try:
                    old.error.disconnect()
                except Exception:
                    pass
                try:
                    old.finished.disconnect()
                except Exception:
                    pass
                old.requestInterruption()
                old.wait(5000)
        dlg.finished.connect(_cleanup)

        # Show dialog and auto-search if we have data
        dlg.show()
        dlg.raise_()
        QApplication.processEvents()
        if title or artist:
            _do_search()

        if dlg.exec() != QDialog.Accepted or not selected_result[0]:
            return

        result = selected_result[0]
        self._apply_lyrics_result(filepath, result)

    def _apply_lyrics_result(self, filepath: str, result: dict):
        """Apply lyrics from search result to the audio file."""
        from mutagen.mp4 import MP4
        from mutagen.oggopus import OggOpus
        from mutagen.id3 import USLT

        audio = _load_audio(filepath)
        if audio is None:
            QMessageBox.warning(self, t("artwork.error_title"), t("artwork.no_metadata"))
            return

        try:
            lyrics_text = result.get("lyrics", "")
            if not lyrics_text:
                return

            if isinstance(audio, OggOpus):
                audio.tags['lyrics'] = [lyrics_text]
            elif isinstance(audio, MP4):
                audio.tags['\xa9lyr'] = [lyrics_text]
            else:  # MP3
                uslt = USLT(encoding=3, lang='eng', desc='', text=lyrics_text)
                if audio.tags is None:
                    from mutagen.id3 import ID3
                    audio.tags = ID3()
                audio.tags.delall('USLT')
                audio.tags.add(uslt)

            audio.save()
            self._show_file_detail(filepath)
            self.refresh_files_list()
        except Exception as e:
            QMessageBox.warning(self, t("artwork.error_title"), str(e))
