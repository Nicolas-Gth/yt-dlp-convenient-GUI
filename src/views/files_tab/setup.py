from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QFrame, QSplitter, QLabel,
    QSizePolicy, QGroupBox, QPushButton, QSlider, QTextEdit
)
from PySide6.QtCore import Qt, QTimer, QFileSystemWatcher
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

from utils.i18n_utils import t

from .widgets import _ArtworkLabel, _SeekSlider, _ArtworkWrapper


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

        files_group = QGroupBox(t("files.group_title"))
        self._files_group = files_group
        files_layout = QVBoxLayout(files_group)
        files_layout.setContentsMargins(5, 10, 5, 8)

        self._files_table = QTableWidget(0, 5)
        self._files_table.setHorizontalHeaderLabels([
            t("files.filename"),
            t("files.title"),
            t("files.artist"),
            t("files.lyrics"),
            t("files.modified"),
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
        hdr.setSectionResizeMode(4, QHeaderView.Interactive)
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

        # ── Watcher to avoid full rescans on every tab switch ──
        self._files_last_directory = None
        self._files_pending_refresh = True
        self._files_list_loaded = False
        self._file_watcher = QFileSystemWatcher(self)
        self._file_watcher.directoryChanged.connect(self._on_watcher_changed)
        self._file_watcher.fileChanged.connect(self._on_watcher_changed)
        self.path_entry.textChanged.connect(self._on_download_path_changed)
