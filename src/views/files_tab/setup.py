from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QFrame, QSplitter, QLabel,
    QSizePolicy, QGroupBox, QPushButton, QSlider, QTextEdit,
    QLineEdit, QComboBox, QMessageBox, QCheckBox
)
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt, QTimer, QFileSystemWatcher, QSize
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

from config import INFO_ICON_PATH
from utils.i18n_utils import t
from utils.theme_utils import is_dark_mode
from utils.settings_utils import settings_manager

from .widgets import _ArtworkLabel, _SeekSlider, _ArtworkWrapper, _ArtworkEditable


class FilesSetupMixin:
    """Mixin that creates the files-tab UI."""

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

        # ── Structure group (above files) ──
        structure_group = QGroupBox(t("files.structure_title"))
        self._files_structure_group = structure_group
        structure_layout = QVBoxLayout(structure_group)
        structure_layout.setContentsMargins(5, 10, 5, 8)
        structure_layout.setSpacing(6)

        structure_row = QHBoxLayout()
        structure_row.setSpacing(6)

        self._files_template_entry = QLineEdit("{artist} - {title}")
        self._files_template_entry.setPlaceholderText(t("format.template_placeholder"))

        self._files_template_presets = QComboBox()
        self._files_template_presets.setCursor(Qt.PointingHandCursor)
        _TEMPLATE_PRESETS = [
            ("{artist} - {title}",          "format.template_preset_default"),
            ("{Y}-{m}-{d} - {artist} - {title}", "format.template_preset_date_artist"),
            ("{Y}{m}{d}_{H}{M}{S}_{title}", "format.template_preset_date_time"),
            ("{tracknumber} - {artist} - {title}", "format.template_preset_track_artist"),
            ("{artist}/{album}/{artist} - {title}", "format.template_preset_artist_album"),
            ("{artist}/{album}/{tracknumber} - {title}", "format.template_preset_album_track"),
            ("{title}",                      "format.template_preset_simple"),
        ]
        for template_val, label_key in _TEMPLATE_PRESETS:
            self._files_template_presets.addItem(t(label_key), template_val)
        self._files_template_presets.addItem(t("format.template_preset_custom"), None)
        self._files_template_presets.currentIndexChanged.connect(self._on_files_template_preset_changed)

        self._files_template_info_btn = QPushButton()
        self._files_template_info_btn.setIcon(QIcon(INFO_ICON_PATH))
        self._files_template_info_btn.setIconSize(QSize(14, 14))
        self._files_template_info_btn.setFlat(True)
        self._files_template_info_btn.setCursor(Qt.PointingHandCursor)
        self._files_template_info_btn.setFixedSize(20, 20)
        self._files_template_info_btn.clicked.connect(
            lambda: QMessageBox.information(self, t("format.template_info_title"), t("format.template_info_text"))
        )

        self._files_apply_format_btn = QPushButton(t("files.apply_format"))
        self._files_apply_format_btn.setCursor(Qt.PointingHandCursor)
        self._files_apply_format_btn.clicked.connect(self._on_apply_format_clicked)

        structure_row.addWidget(self._files_template_entry, 1)
        structure_row.addWidget(self._files_template_presets)
        structure_row.addWidget(self._files_template_info_btn)
        structure_row.addWidget(self._files_apply_format_btn)
        structure_layout.addLayout(structure_row)
        left_layout.addWidget(structure_group)

        files_group = QGroupBox(t("files.group_title"))
        self._files_group = files_group
        files_layout = QVBoxLayout(files_group)
        files_layout.setContentsMargins(5, 10, 5, 8)

        # Search bar above the file table
        self._files_search = QLineEdit()
        self._files_search.setPlaceholderText(t("files.search_placeholder"))
        self._files_search.setClearButtonEnabled(True)
        self._files_search.textChanged.connect(self._on_files_search_changed)
        files_layout.addWidget(self._files_search)

        self._files_table = QTableWidget(0, 6)
        self._files_table.setHorizontalHeaderLabels([
            t("files.filename"),
            t("files.title"),
            t("files.artist"),
            t("files.lyrics"),
            t("files.size"),
            t("files.modified"),
        ])
        self._files_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._files_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._files_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._files_table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self._files_table.verticalHeader().setVisible(False)
        self._files_table.setShowGrid(True)
        self._files_table.setFrameShape(QFrame.NoFrame)
        self._files_table.setStyleSheet(
            "QTableWidget { border: none; background: palette(base); gridline-color: palette(mid); }"
            "QTableWidget QTableCornerButton::section { background: palette(window); border: none; border-right: 1px solid palette(mid); border-bottom: 1px solid palette(mid); }"
            "QHeaderView { background: transparent; font-weight: normal; }"
            "QHeaderView::section {"
            "  border: none; border-right: 1px solid palette(mid); border-bottom: 1px solid palette(mid);"
            "  background: palette(window); font-weight: normal;"
            "}"
        )
        hdr = self._files_table.horizontalHeader()
        hdr.setMinimumSectionSize(60)
        hdr.setSectionResizeMode(0, QHeaderView.Interactive)
        hdr.setSectionResizeMode(1, QHeaderView.Interactive)
        hdr.setSectionResizeMode(2, QHeaderView.Interactive)
        hdr.setSectionResizeMode(3, QHeaderView.Interactive)
        hdr.setSectionResizeMode(4, QHeaderView.Interactive)
        hdr.setStretchLastSection(True)
        hdr.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        hdr.sectionResized.connect(self._on_section_resized)
        hdr.sortIndicatorChanged.connect(self._save_sort_column)
        self._files_table.itemSelectionChanged.connect(self._on_file_selected)
        self._files_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._files_table.customContextMenuRequested.connect(self._on_files_context_menu)
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

        self._files_artwork = _ArtworkEditable()
        self._files_artwork.edit_requested.connect(self._on_edit_artwork_clicked)
        self._current_detail_filepath = None

        # Audio player
        self._audio_output = QAudioOutput()
        self._media_player = QMediaPlayer()
        self._media_player.setAudioOutput(self._audio_output)
        self._media_player.playbackStateChanged.connect(self._on_playback_state_changed)
        self._media_player.positionChanged.connect(self._on_position_changed)
        self._media_player.durationChanged.connect(self._on_duration_changed)
        self._seeking = False

        self._play_btn = QPushButton()
        self._play_btn.setFixedSize(28, 24)
        self._play_btn.setCursor(Qt.PointingHandCursor)
        self._play_btn.setEnabled(False)
        self._play_btn.clicked.connect(self._on_play_clicked)
        self._play_btn.setStyleSheet("QPushButton { padding: 0; text-align: center; }")
        self._update_play_icon(is_playing=False)

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
        self._identify_btn = QPushButton(t("button.identify"))
        self._identify_btn.setCursor(Qt.PointingHandCursor)
        identify_icon = "assets/ui/search-icon-light.svg" if is_dark_mode() else "assets/ui/search-icon-dark.svg"
        self._identify_btn.setIcon(QIcon(identify_icon))
        self._identify_btn.setIconSize(QSize(16, 16))
        self._identify_btn.clicked.connect(self._on_identify_metadata)
        ebl.addWidget(self._identify_btn)
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

        # Lyrics label + search button + edit
        lyrics_bottom = QWidget()
        lbl = QVBoxLayout(lyrics_bottom)
        lbl.setContentsMargins(0, 4, 0, 0)
        lbl.setSpacing(2)

        lyrics_header = QHBoxLayout()
        self._lyrics_label = QLabel(t("files.lyrics"))
        self._lyrics_label.setStyleSheet("QLabel { color: palette(dark); }")
        self._lyrics_label.hide()
        lyrics_header.addWidget(self._lyrics_label)
        lyrics_header.addStretch()
        self._lyrics_search_btn = QPushButton(t("lyrics.search"))
        self._lyrics_search_btn.setCursor(Qt.PointingHandCursor)
        lyrics_search_icon = "assets/ui/search-icon-light.svg" if is_dark_mode() else "assets/ui/search-icon-dark.svg"
        self._lyrics_search_btn.setIcon(QIcon(lyrics_search_icon))
        self._lyrics_search_btn.setIconSize(QSize(16, 16))
        self._lyrics_search_btn.clicked.connect(self._on_search_lyrics)
        self._lyrics_search_btn.hide()
        lyrics_header.addWidget(self._lyrics_search_btn)
        lbl.addLayout(lyrics_header)

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

        # ── Watcher to avoid full rescans on every tab switch ──
        self._files_last_directory = None
        self._files_pending_refresh = True
        self._files_list_loaded = False
        self._file_watcher = QFileSystemWatcher(self)
        self._file_watcher.directoryChanged.connect(self._on_watcher_changed)
        self._file_watcher.fileChanged.connect(self._on_watcher_changed)
        self.path_entry.textChanged.connect(self._on_download_path_changed)

    def _update_search_icons(self):
        """Update search button icons (identify & lyrics) based on current theme."""
        icon = "assets/ui/search-icon-light.svg" if is_dark_mode() else "assets/ui/search-icon-dark.svg"
        for attr in ('_identify_btn', '_lyrics_search_btn'):
            btn = getattr(self, attr, None)
            if btn is not None:
                btn.setIcon(QIcon(icon))

    def _restore_column_widths(self):
        """Restore file table column widths from settings."""
        self._columns_ready = True
        widths = settings_manager.get_setting("files_table_column_widths")
        if not widths or len(widths) != self._files_table.columnCount():
            return
        self._restoring_widths = True
        hdr = self._files_table.horizontalHeader()
        minimums = {3: 70, 4: 110}
        for i, w in enumerate(widths):
            w = max(w, minimums.get(i, 60))
            hdr.resizeSection(i, w)
        self._restoring_widths = False

    def _on_section_resized(self, logical_index, old_size, new_size):
        """Enforce minimum column widths then persist."""
        if getattr(self, '_restoring_widths', False) or not getattr(self, '_columns_ready', False):
            return
        hdr = self._files_table.horizontalHeader()
        minimums = {3: 70, 4: 110}
        min_w = minimums.get(logical_index, 0)
        if min_w and new_size < min_w:
            self._restoring_widths = True
            hdr.resizeSection(logical_index, min_w)
            self._restoring_widths = False
            return
        widths = [hdr.sectionSize(i) for i in range(hdr.count())]
        settings_manager.set_setting("files_table_column_widths", widths)

    def _save_sort_column(self, logical_index, order):
        """Persist sort column and order to settings."""
        if getattr(self, '_restoring_widths', False) or not getattr(self, '_columns_ready', False):
            return
        settings_manager.set_setting("files_table_sort", [logical_index, order.value])

    def _restore_sort_column(self):
        """Restore sort column and order from settings."""
        data = settings_manager.get_setting("files_table_sort")
        if not data or len(data) != 2:
            return
        col, order = data
        if 0 <= col < self._files_table.columnCount():
            self._restoring_widths = True
            hdr = self._files_table.horizontalHeader()
            hdr.setSortIndicator(col, Qt.SortOrder(order))
            self._restoring_widths = False
