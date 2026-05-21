import os
import warnings

from PySide6.QtWidgets import (
    QTableWidgetItem, QFileDialog, QMessageBox, QDialog, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QScrollArea, QWidget, QGridLayout, QSizePolicy, QLayout,
    QLineEdit, QStackedWidget
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
            ki = QTableWidgetItem(t(_FIELD_LABELS[field_name]))
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
            if current_worker[0] is not None:
                current_worker[0].quit()
                current_worker[0].wait(2000)
            api_name = api_combo.currentText()
            worker = SearchWorker(api_name, query, artist, album, title, limit, seen_urls)
            current_worker[0] = worker

            def _on_results(new_items, limit_used, has_more):
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
            if current_worker[0] is not None:
                current_worker[0].quit()
                current_worker[0].wait(2000)
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
