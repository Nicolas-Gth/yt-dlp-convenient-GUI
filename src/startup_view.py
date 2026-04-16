"""
Startup splash dialog — shows dependency checks, updates, and installations
directly in the GUI so the user never needs to see a terminal window.
"""
import os
import sys
from typing import Optional

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QIcon, QFont
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QMessageBox,
    QApplication,
    QGridLayout,
)

from config import APP_NAME, ICON_PATH
from utils.i18n_utils import t
from utils import startup_utils


class _CheckWorker(QThread):
    """Runs startup checks in a background thread."""
    progress = Signal(str)
    step_done = Signal(str, bool)
    finished_signal = Signal(object)

    def run(self):
        self.progress.emit(t("startup.checking_deps"))
        report = startup_utils.run_all_checks()
        for comp in report.components:
            self.step_done.emit(comp.name, comp.ok)
        self.finished_signal.emit(report)


class _InstallWorker(QThread):
    """Installs missing components in a background thread."""
    progress = Signal(str)
    finished_signal = Signal(bool)

    def __init__(self, missing: list, parent=None):
        super().__init__(parent)
        self._missing = missing

    def run(self):
        all_ok = True
        for name in self._missing:
            if name == "ffmpeg":
                ok = startup_utils.install_ffmpeg(on_progress=lambda msg: self.progress.emit(msg))
            elif name == "deno":
                ok = startup_utils.install_deno(on_progress=lambda msg: self.progress.emit(msg))
            elif name == "yt-dlp":
                ok = startup_utils.install_requirements(on_progress=lambda msg: self.progress.emit(msg))
            else:
                ok = False
            if not ok:
                all_ok = False
        self.finished_signal.emit(all_ok)


class _UpdateWorker(QThread):
    """Checks for and optionally applies Git updates."""
    progress = Signal(str)
    update_info = Signal(int, str)
    finished_signal = Signal(bool)

    def __init__(self, apply: bool = False, remote_branch: str = "", parent=None):
        super().__init__(parent)
        self._apply = apply
        self._remote_branch = remote_branch

    def run(self):
        if self._apply and self._remote_branch:
            self.progress.emit(t("startup.applying_update"))
            ok = startup_utils.apply_git_update(self._remote_branch)
            self.finished_signal.emit(ok)
        else:
            self.progress.emit(t("startup.checking_updates"))
            behind, branch = startup_utils.check_git_updates()
            self.update_info.emit(behind, branch or "")
            self.finished_signal.emit(False)


class _YtdlpUpdateWorker(QThread):
    """Upgrades yt-dlp in background."""
    progress = Signal(str)
    finished_signal = Signal(bool)

    def run(self):
        self.progress.emit(t("startup.updating_ytdlp"))
        ok = startup_utils.update_ytdlp(on_progress=lambda msg: self.progress.emit(msg))
        self.finished_signal.emit(ok)


class StartupDialog(QDialog):
    ready = Signal()

    _STATUS_COLORS = {
        "checking": "gray",
        "installed": "#2ecc71",
        "missing": "#e74c3c",
        "outdated": "#f39c12",
        "installing": None,
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(APP_NAME)
        if os.path.isfile(ICON_PATH):
            self.setWindowIcon(QIcon(ICON_PATH))
        self.setFixedWidth(420)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self._remote_branch: str = ""
        self._current_step = 0
        self._total_steps = 5

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Status label
        self._status_label = QLabel(t("startup.initializing"))
        self._status_label.setAlignment(Qt.AlignCenter)
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        # Dependency table
        grid = QGridLayout()
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 0)
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(6)

        self._comp_names: dict[str, QLabel] = {}
        self._comp_statuses: dict[str, QLabel] = {}
        for row, name in enumerate(("ffmpeg", "deno", "yt-dlp")):
            name_lbl = QLabel(name)
            name_font = QFont()
            name_font.setPointSize(10)
            name_lbl.setFont(name_font)
            grid.addWidget(name_lbl, row, 0)

            status_lbl = QLabel("…")
            status_lbl.setStyleSheet(f"color: {self._STATUS_COLORS['checking']};")
            status_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            status_font = QFont()
            status_font.setPointSize(10)
            status_lbl.setFont(status_font)
            grid.addWidget(status_lbl, row, 1)

            self._comp_names[name] = name_lbl
            self._comp_statuses[name] = status_lbl

        layout.addLayout(grid)

        # Progress bar
        self._progress = QProgressBar()
        self._progress.setRange(0, self._total_steps)
        self._progress.setValue(0)
        layout.addWidget(self._progress)

        self._run_checks()

    # ------------------------------------------------------------------

    def _set_comp_status(self, name: str, status: str):
        """Update a component's status label. status: installed|missing|outdated|installing"""
        lbl = self._comp_statuses.get(name)
        if not lbl:
            return
        text_map = {
            "installed": t("startup.status_installed"),
            "missing": t("startup.status_missing"),
            "outdated": t("startup.status_outdated"),
            "installing": t("startup.status_installing"),
        }
        lbl.setText(text_map.get(status, status))
        color = self._STATUS_COLORS.get(status, "gray")
        if color:
            lbl.setStyleSheet(f"color: {color};")
        else:
            lbl.setStyleSheet("")

    def _run_checks(self):
        self._worker = _CheckWorker(self)
        self._worker.progress.connect(self._set_status)
        self._worker.step_done.connect(self._on_step_done)
        self._worker.finished_signal.connect(self._on_checks_done)
        self._worker.start()

    def _advance_progress(self):
        self._current_step = min(self._current_step + 1, self._total_steps)
        self._progress.setValue(self._current_step)

    def _on_step_done(self, name: str, ok: bool):
        self._set_comp_status(name, "installed" if ok else "missing")
        self._advance_progress()

    def _on_checks_done(self, report: startup_utils.StartupReport):
        if report.all_ok:
            self._check_updates()
        else:
            # Auto-install missing components
            for name in report.missing:
                self._set_comp_status(name, "installing")
            self._set_status(t("startup.installing"))
            # Switch to indeterminate (marquee) mode during install
            self._progress.setRange(0, 0)
            self._do_install(report.missing)

    def _do_install(self, missing: list):
        self._install_worker = _InstallWorker(missing, self)
        self._install_worker.progress.connect(self._set_status)
        self._install_worker.finished_signal.connect(self._on_install_done)
        self._install_worker.start()

    def _on_install_done(self, success: bool):
        # Restore determinate progress bar
        self._progress.setRange(0, self._total_steps)
        self._progress.setValue(self._current_step)
        if success:
            self._set_status(t("startup.install_ok"))
            self._run_checks()
        else:
            self._set_status(t("startup.install_failed"))
            QMessageBox.warning(
                self,
                APP_NAME,
                t("startup.install_failed_detail"),
            )
            self._check_updates()

    # ------------------------------------------------------------------
    # Git updates
    # ------------------------------------------------------------------

    def _check_updates(self):
        self._set_status(t("startup.checking_updates"))
        self._update_worker = _UpdateWorker(parent=self)
        self._update_worker.progress.connect(self._set_status)
        self._update_worker.update_info.connect(self._on_update_info)
        self._update_worker.finished_signal.connect(self._on_update_check_done)
        self._update_worker.start()
        self._advance_progress()

    def _on_update_info(self, behind: int, remote_branch: str):
        self._remote_branch = remote_branch
        if behind > 0:
            reply = QMessageBox.question(
                self,
                t("startup.update_title"),
                t("startup.update_prompt", count=behind),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if reply == QMessageBox.Yes:
                self._apply_update()
                return
        self._update_ytdlp()

    def _on_update_check_done(self, applied: bool):
        if applied:
            QMessageBox.information(
                self,
                t("startup.update_title"),
                t("startup.update_restart"),
            )
            QApplication.quit()
            return
        self._update_ytdlp()

    def _apply_update(self):
        self._set_status(t("startup.applying_update"))
        self._apply_worker = _UpdateWorker(apply=True, remote_branch=self._remote_branch, parent=self)
        self._apply_worker.progress.connect(self._set_status)
        self._apply_worker.finished_signal.connect(self._on_update_applied)
        self._apply_worker.start()

    def _on_update_applied(self, ok: bool):
        if ok:
            QMessageBox.information(
                self,
                t("startup.update_title"),
                t("startup.update_restart"),
            )
            QApplication.quit()
        else:
            self._set_status(t("startup.update_failed"))
            self._update_ytdlp()

    # ------------------------------------------------------------------
    # yt-dlp update
    # ------------------------------------------------------------------

    def _update_ytdlp(self):
        self._set_status(t("startup.updating_ytdlp"))
        self._ytdlp_worker = _YtdlpUpdateWorker(self)
        self._ytdlp_worker.progress.connect(self._set_status)
        self._ytdlp_worker.finished_signal.connect(self._on_ytdlp_done)
        self._ytdlp_worker.start()
        self._advance_progress()

    def _on_ytdlp_done(self, ok: bool):
        self._progress.setValue(self._total_steps)
        self._set_status(t("startup.ready"))
        self.ready.emit()
        self.accept()

    # ------------------------------------------------------------------

    def _set_status(self, text: str):
        self._status_label.setText(text)