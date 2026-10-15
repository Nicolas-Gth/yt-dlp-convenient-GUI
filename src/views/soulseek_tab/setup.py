from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QWidget, QTableWidget,
    QHeaderView, QAbstractItemView, QFrame, QLabel, QGroupBox, QPushButton,
    QLineEdit,
)
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt, QSize

from utils.i18n_utils import t
from utils.theme_utils import is_dark_mode

from .constants import _RESULT_COLUMNS, _TRANSFER_COLUMNS


class SoulseekSetupMixin:
    """Mixin that builds the Soulseek tab UI."""

    def setup_soulseek_tab(self):
        self._soulseek_tab = QWidget()
        layout = QVBoxLayout(self._soulseek_tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # ── Status row ──
        status_row = QHBoxLayout()
        status_row.setSpacing(6)
        self._soulseek_status = QLabel(t("soulseek.status_idle"))
        self._soulseek_status.setWordWrap(True)
        status_row.addWidget(self._soulseek_status, 1)
        self._soulseek_connect_btn = QPushButton(t("soulseek.connect"))
        self._soulseek_connect_btn.setCursor(Qt.PointingHandCursor)
        self._soulseek_connect_btn.clicked.connect(self._on_soulseek_connect)
        status_row.addWidget(self._soulseek_connect_btn)
        layout.addLayout(status_row)

        # ── Search row ──
        search_row = QHBoxLayout()
        search_row.setSpacing(6)
        self._soulseek_search = QLineEdit()
        self._soulseek_search.setPlaceholderText(t("soulseek.search_placeholder"))
        self._soulseek_search.setClearButtonEnabled(True)
        self._soulseek_search.returnPressed.connect(self._on_soulseek_search)
        search_row.addWidget(self._soulseek_search, 1)
        self._soulseek_search_btn = QPushButton(t("soulseek.search"))
        self._soulseek_search_btn.setCursor(Qt.PointingHandCursor)
        self._soulseek_search_btn.setIcon(self._search_icon())
        self._soulseek_search_btn.setIconSize(QSize(16, 16))
        self._soulseek_search_btn.clicked.connect(self._on_soulseek_search)
        search_row.addWidget(self._soulseek_search_btn)
        layout.addLayout(search_row)

        # ── Results group ──
        results_group = QGroupBox(t("soulseek.results_group"))
        self._soulseek_results_group = results_group
        results_layout = QVBoxLayout(results_group)
        results_layout.setContentsMargins(5, 10, 5, 8)
        results_layout.setSpacing(6)

        self._soulseek_results_table = QTableWidget(0, len(_RESULT_COLUMNS))
        self._configure_table(self._soulseek_results_table)
        self._soulseek_results_table.setHorizontalHeaderLabels([t(k) for k, _ in _RESULT_COLUMNS])
        self._soulseek_results_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._soulseek_results_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._soulseek_results_table.setSortingEnabled(True)
        self._soulseek_results_table.horizontalHeader().setStretchLastSection(False)
        for i, (_k, stretch) in enumerate(_RESULT_COLUMNS):
            if stretch:
                self._soulseek_results_table.horizontalHeader().setSectionResizeMode(i, QHeaderView.Stretch)
        results_layout.addWidget(self._soulseek_results_table, 1)

        self._soulseek_download_btn = QPushButton(t("soulseek.download_selected"))
        self._soulseek_download_btn.setCursor(Qt.PointingHandCursor)
        self._soulseek_download_btn.clicked.connect(self._on_soulseek_download)
        results_layout.addWidget(self._soulseek_download_btn, alignment=Qt.AlignRight)

        layout.addWidget(results_group, 1)

        # ── Transfers group ──
        transfers_group = QGroupBox(t("soulseek.transfers_group"))
        self._soulseek_transfers_group = transfers_group
        transfers_layout = QVBoxLayout(transfers_group)
        transfers_layout.setContentsMargins(5, 10, 5, 8)
        transfers_layout.setSpacing(6)

        self._soulseek_transfers_table = QTableWidget(0, len(_TRANSFER_COLUMNS))
        self._configure_table(self._soulseek_transfers_table)
        self._soulseek_transfers_table.setHorizontalHeaderLabels([t(k) for k in _TRANSFER_COLUMNS])
        self._soulseek_transfers_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._soulseek_transfers_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._soulseek_transfers_table.horizontalHeader().setStretchLastSection(False)
        self._soulseek_transfers_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        transfers_layout.addWidget(self._soulseek_transfers_table, 1)

        clear_row = QHBoxLayout()
        clear_row.addStretch()
        self._soulseek_clear_btn = QPushButton(t("soulseek.clear_completed"))
        self._soulseek_clear_btn.setCursor(Qt.PointingHandCursor)
        self._soulseek_clear_btn.clicked.connect(self._on_soulseek_clear_completed)
        clear_row.addWidget(self._soulseek_clear_btn)
        transfers_layout.addLayout(clear_row)

        layout.addWidget(transfers_group, 1)

        self.tabs.addTab(self._soulseek_tab, t("tabs.soulseek"))
        self.tabs.currentChanged.connect(self._on_soulseek_tab_changed)

        # State
        self._slskd_client = None
        self._soulseek_connected = False
        self._soulseek_search_worker = None
        self._soulseek_transfers_timer = None

    def _configure_table(self, table: QTableWidget):
        table.verticalHeader().setVisible(False)
        table.setShowGrid(True)
        table.setFrameShape(QFrame.NoFrame)
        table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        table.setStyleSheet(
            "QTableWidget { border: none; background: palette(base); gridline-color: palette(mid); }"
            "QHeaderView { background: transparent; font-weight: normal; }"
            "QHeaderView::section { border: none; border-right: 1px solid palette(mid);"
            " border-bottom: 1px solid palette(mid); background: palette(window); font-weight: normal; }"
        )
        hdr = table.horizontalHeader()
        hdr.setMinimumSectionSize(60)
        hdr.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)

    def _search_icon(self) -> QIcon:
        return QIcon("assets/ui/search-icon-light.svg" if is_dark_mode() else "assets/ui/search-icon-dark.svg")
