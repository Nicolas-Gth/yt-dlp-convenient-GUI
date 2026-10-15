import os
import shutil
import time

from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox, QProgressDialog, QTableWidgetItem, QApplication
)

from utils.i18n_utils import t
from utils.settings_utils import settings_manager
from utils.soulseek_utils import (
    SlskdClient, get_server, is_slskd_installed, download_slskd,
    slskd_downloads_dir,
)

from .constants import _RESULT_COLUMNS, _TRANSFER_COLUMNS

_TERMINAL_STATES = (
    "Completed, Succeeded",
    "Completed, Cancelled",
    "Completed, Errored",
    "Completed, Rejected",
)


def _human_size(num: int) -> str:
    num = float(num or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num < 1024 or unit == "TB":
            return f"{num:.0f} {unit}" if unit == "B" else f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} TB"


def _human_seconds(sec: int) -> str:
    sec = int(sec or 0)
    m, s = divmod(sec, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


class _DownloadWorker(QThread):
    progress = Signal(int, int)
    done = Signal(bool, str)

    def run(self):
        try:
            download_slskd(lambda cur, total: self.progress.emit(cur, total))
            self.done.emit(True, "")
        except Exception as e:
            self.done.emit(False, str(e))


class _SearchWorker(QThread):
    new_files = Signal(list)
    state_changed = Signal(str)
    error = Signal(str)

    def __init__(self, base_url: str, query: str, parent=None):
        super().__init__(parent)
        self.base_url = base_url
        self.query = query

    def run(self):
        client = SlskdClient(self.base_url)
        # slskd rejects searches until it is logged in to the Soulseek network
        # (HTTP 409 "Connected, LoggingIn"), so wait for the logged-in state.
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if self.isInterruptionRequested():
                return
            state = client.server_state(quiet=True) or {}
            if state.get("isLoggedIn"):
                break
            time.sleep(1)
        # Start the search, retrying a couple of times in case the login
        # handshake is still finishing.
        search = None
        for _attempt in range(3):
            if self.isInterruptionRequested():
                return
            search = client.start_search(self.query)
            if search and search.get("id"):
                break
            time.sleep(2)
        if not search or not search.get("id"):
            self.error.emit(t("soulseek.search_failed"))
            return
        search_id = search["id"]
        current = None
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            if self.isInterruptionRequested():
                return
            current = client.get_search(search_id)
            if current is None:
                time.sleep(1)
                continue
            if client.is_search_complete(current):
                break
            time.sleep(1)
        files = client.flatten_files(current) if current is not None else []
        self.new_files.emit(files)


class SoulseekHandlersMixin:
    """Mixin that wires the Soulseek tab logic (search, download, status)."""

    # ── Tab lifecycle ───────────────────────────────────────────────────
    def _on_soulseek_tab_changed(self, index):
        if self.tabs.widget(index) is not self._soulseek_tab:
            return
        if not settings_manager.get_setting("soulseek_disclaimer_accepted", False):
            if self._show_soulseek_disclaimer():
                settings_manager.set_setting("soulseek_disclaimer_accepted", True)
            else:
                return
        self._start_transfers_polling()
        self._refresh_soulseek_status()
        if not self._soulseek_connected:
            self._ensure_soulseek_running()

    def _show_soulseek_disclaimer(self) -> bool:
        result = QMessageBox.information(
            self,
            t("soulseek.disclaimer_title"),
            t("soulseek.disclaimer_text"),
            QMessageBox.Ok | QMessageBox.Cancel,
            QMessageBox.Ok,
        )
        return result == QMessageBox.Ok

    # ── Connection / setup ──────────────────────────────────────────────
    def _on_soulseek_connect(self):
        creds = self._prompt_soulseek_credentials()
        if creds is None:
            return
        username, password = creds
        settings_manager.set_setting("soulseek_username", username)
        settings_manager.set_setting("soulseek_password", password)
        self._restart_soulseek(username, password)

    def _prompt_soulseek_credentials(self):
        username = settings_manager.get_setting("soulseek_username", "")
        password = settings_manager.get_setting("soulseek_password", "")
        dlg = QDialog(self)
        dlg.setWindowTitle(t("soulseek.credentials_title"))
        dlg.setMinimumWidth(360)
        layout = QVBoxLayout(dlg)
        layout.setSpacing(8)

        layout.addWidget(QLabel(t("soulseek.credentials_info")))
        user_edit = QLineEdit(username)
        user_edit.setPlaceholderText(t("soulseek.username"))
        layout.addWidget(user_edit)
        pass_edit = QLineEdit(password)
        pass_edit.setEchoMode(QLineEdit.Password)
        pass_edit.setPlaceholderText(t("soulseek.password"))
        layout.addWidget(pass_edit)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel = QPushButton(t("button.cancel"))
        cancel.clicked.connect(dlg.reject)
        ok = QPushButton(t("button.save"))
        ok.setDefault(True)
        ok.clicked.connect(dlg.accept)
        btn_row.addWidget(cancel)
        btn_row.addWidget(ok)
        layout.addLayout(btn_row)

        if dlg.exec() != QDialog.Accepted:
            return None
        u = user_edit.text().strip()
        p = pass_edit.text()
        if not u or not p:
            QMessageBox.warning(self, t("soulseek.credentials_title"), t("soulseek.credentials_missing"))
            return None
        return u, p

    def _ensure_soulseek_running(self) -> bool:
        if self._slskd_client is not None and get_server().running:
            return True

        if not is_slskd_installed():
            if not self._download_slskd_blocking():
                return False

        username = settings_manager.get_setting("soulseek_username", "")
        password = settings_manager.get_setting("soulseek_password", "")
        if not username or not password:
            creds = self._prompt_soulseek_credentials()
            if creds is None:
                return False
            username, password = creds
            settings_manager.set_setting("soulseek_username", username)
            settings_manager.set_setting("soulseek_password", password)

        self._restart_soulseek(username, password)
        return self._soulseek_connected

    def _restart_soulseek(self, username: str, password: str):
        self._soulseek_status.setText(t("soulseek.status_starting"))
        QApplication.processEvents()
        try:
            base_url = get_server().start(username, password)
        except Exception as e:
            self._soulseek_status.setText(t("soulseek.status_error", error=str(e)))
            return
        self._slskd_client = SlskdClient(base_url)
        if self._wait_until_ready():
            self._soulseek_connected = True
            self._refresh_soulseek_status()
        else:
            self._soulseek_connected = False
            self._soulseek_status.setText(t("soulseek.status_error", error=t("soulseek.status_unreachable")))

    def _wait_until_ready(self, timeout: float = 30.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            QApplication.processEvents()
            if self._slskd_client is not None and self._slskd_client.server_state(quiet=True) is not None:
                return True
            time.sleep(0.5)
        return self._slskd_client is not None and self._slskd_client.server_state(quiet=True) is not None

    def _download_slskd_blocking(self) -> bool:
        from PySide6.QtCore import QEventLoop
        worker = _DownloadWorker()
        progress = QProgressDialog(t("soulseek.downloading"), "", 0, 100, self)
        progress.setWindowTitle(t("soulseek.download_title"))
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.setCancelButton(None)
        progress.setValue(0)

        loop = QEventLoop()
        result = {}

        def on_progress(cur, total):
            if total > 0:
                progress.setValue(int(cur * 100 / total))

        def on_done(ok, err):
            result["ok"] = ok
            result["err"] = err
            loop.quit()

        worker.progress.connect(on_progress)
        worker.done.connect(on_done)
        worker.start()
        progress.show()
        loop.exec()
        worker.wait(2000)
        progress.close()

        if not result.get("ok"):
            self._soulseek_status.setText(t("soulseek.status_error", error=result.get("err", "?")))
            QMessageBox.warning(self, t("soulseek.download_title"), t("soulseek.download_failed", error=result.get("err", "")))
            return False
        return True

    # ── Status ──────────────────────────────────────────────────────────
    def _refresh_soulseek_status(self):
        if self._slskd_client is None:
            self._soulseek_status.setText(t("soulseek.status_idle"))
            return
        state = self._slskd_client.server_state(quiet=True)
        if state is None:
            self._soulseek_status.setText(t("soulseek.status_unreachable"))
            return
        connected = bool(state.get("isLoggedIn", state.get("isConnected", False)))
        username = state.get("username", "") or settings_manager.get_setting("soulseek_username", "")
        if connected:
            self._soulseek_status.setText(t("soulseek.status_connected", username=username))
        else:
            self._soulseek_status.setText(t("soulseek.status_disconnected"))
        self._soulseek_connected = connected

    # ── Search ──────────────────────────────────────────────────────────
    def _on_soulseek_search(self):
        query = self._soulseek_search.text().strip()
        if not query:
            return
        if not self._ensure_soulseek_running():
            return
        base_url = get_server().base_url
        if not base_url:
            return
        old = self._soulseek_search_worker
        if old is not None:
            self._soulseek_search_worker = None
            try:
                if old.isRunning():
                    old.requestInterruption()
                    old.wait(1000)
            except RuntimeError:
                # Underlying C++ object already deleted (deleteLater after finish)
                pass
        self._soulseek_results_table.setRowCount(0)
        self._soulseek_status.setText(t("soulseek.status_searching"))
        worker = _SearchWorker(base_url, query, self)
        self._soulseek_search_worker = worker
        worker.new_files.connect(self._on_soulseek_results)
        worker.state_changed.connect(lambda s: self._soulseek_status.setText(s))
        worker.error.connect(lambda msg: self._soulseek_status.setText(msg))
        worker.finished.connect(worker.deleteLater)
        worker.finished.connect(lambda w=worker: self._clear_search_worker(w))
        worker.start()

    def _clear_search_worker(self, worker):
        """Drop the stored reference once a search worker has finished."""
        if self._soulseek_search_worker is worker:
            self._soulseek_search_worker = None

    def _on_soulseek_results(self, files):
        self._soulseek_results_table.setSortingEnabled(False)
        self._soulseek_results_table.setRowCount(0)
        self._soulseek_results_table.setRowCount(len(files))
        for row, f in enumerate(files):
            filename = f.get("filename", "")
            size = int(f.get("size", 0))
            bitrate = f.get("bitRate")
            length = f.get("length")
            upload = f.get("_uploadSpeed")
            queue = f.get("_queueLength")
            cells = [
                filename,
                f.get("_username", ""),
                _human_size(size),
                f"{bitrate} kbps" if bitrate else "",
                _human_seconds(length) if length else "",
                f"{upload} KB/s" if upload else "",
                str(queue) if queue is not None else "",
            ]
            for col, text in enumerate(cells):
                item = QTableWidgetItem(text)
                if col == 0:
                    item.setData(Qt.UserRole, {"filename": filename, "size": size, "username": f.get("_username", "")})
                self._soulseek_results_table.setItem(row, col, item)
        self._soulseek_results_table.setSortingEnabled(True)
        if files:
            self._refresh_soulseek_status()
        else:
            # Some artist names are blocked by the Soulseek server, so a
            # well-formed search can legitimately return nothing.
            self._soulseek_status.setText(t("soulseek.no_results"))

    # ── Downloads ───────────────────────────────────────────────────────
    def _on_soulseek_download(self):
        if not self._ensure_soulseek_running():
            return
        selected = self._soulseek_results_table.selectionModel().selectedRows()
        if not selected:
            QMessageBox.information(self, t("soulseek.results_group"), t("soulseek.nothing_selected"))
            return
        # Group selected files by username (slskd enqueues per-username).
        by_user = {}
        for idx in selected:
            item = self._soulseek_results_table.item(idx.row(), 0)
            data = item.data(Qt.UserRole)
            if not data:
                continue
            by_user.setdefault(data["username"], []).append(data)

        client = self._slskd_client
        enqueued = 0
        for username, files in by_user.items():
            if client.enqueue(username, files):
                enqueued += len(files)
        if enqueued:
            self._start_transfers_polling()
        else:
            QMessageBox.warning(self, t("soulseek.results_group"), t("soulseek.enqueue_failed"))

    def _on_soulseek_clear_completed(self):
        if self._slskd_client is not None:
            self._slskd_client.clear_completed_downloads()
        self._poll_transfers()

    # ── Transfers polling ───────────────────────────────────────────────
    def _start_transfers_polling(self):
        if self._soulseek_transfers_timer is None:
            self._soulseek_transfers_timer = QTimer(self)
            self._soulseek_transfers_timer.setInterval(2000)
            self._soulseek_transfers_timer.timeout.connect(self._poll_transfers)
            self._soulseek_transfers_timer.start()

    def _poll_transfers(self):
        if self._slskd_client is None or not get_server().running:
            return
        transfers = self._slskd_client.get_downloads(quiet=True)
        self._render_transfers(transfers)
        self._move_completed_downloads(transfers)

    def _render_transfers(self, transfers):
        self._soulseek_transfers_table.setSortingEnabled(False)
        self._soulseek_transfers_table.setRowCount(len(transfers))
        for row, tr in enumerate(transfers):
            size = int(tr.get("size", 0))
            pct = tr.get("percentComplete", 0) or 0
            cells = [
                tr.get("filename", ""),
                tr.get("_username", tr.get("username", "")),
                _human_size(size),
                f"{pct:.0f}%",
                tr.get("state", ""),
            ]
            for col, text in enumerate(cells):
                self._soulseek_transfers_table.setItem(row, col, QTableWidgetItem(text))
        self._soulseek_transfers_table.setSortingEnabled(True)

    def _move_completed_downloads(self, transfers):
        dest_dir = self.path_entry.text().strip() if hasattr(self, "path_entry") else ""
        if not dest_dir or not os.path.isdir(dest_dir):
            return
        moved_ids = getattr(self, "_soulseek_moved_ids", set())
        for tr in transfers:
            tid = tr.get("id")
            state = tr.get("state", "")
            if tid in moved_ids or state not in _TERMINAL_STATES:
                continue
            if "Succeeded" not in state:
                # Nothing to move; remember it so we don't revisit it.
                moved_ids.add(tid)
                continue
            src = self._find_staged_file(tr)
            if not src:
                # slskd may still be finalizing the file; retry on the next poll.
                continue
            preferred = self._remote_basename(tr.get("filename", "")) or os.path.basename(src)
            if self._move_into_download_folder(src, dest_dir, preferred):
                moved_ids.add(tid)
        self._soulseek_moved_ids = moved_ids

    @staticmethod
    def _remote_basename(remote_path: str) -> str:
        """Return the file name from a remote path.

        Soulseek peers report Windows-style paths (``dir\\file.flac``), so the
        separator is normalised before taking the basename.
        """
        return os.path.basename((remote_path or "").replace("\\", "/"))

    def _find_staged_file(self, tr):
        """Locate the downloaded file for *tr* inside the slskd staging dir.

        slskd keeps the remote folder layout and may append a suffix to the
        local file name, so match on file size plus name similarity instead of
        an exact path.
        """
        basename = self._remote_basename(tr.get("filename", ""))
        stem, ext = os.path.splitext(basename)
        size = int(tr.get("size", 0))
        root = slskd_downloads_dir()
        size_match = None
        for dirpath, _dirs, filenames in os.walk(root):
            for fname in filenames:
                full = os.path.join(dirpath, fname)
                try:
                    if os.path.getsize(full) != size:
                        continue
                except OSError:
                    continue
                fstem, fext = os.path.splitext(fname)
                if ext and fext.lower() != ext.lower():
                    continue
                if fstem == stem or (stem and fstem.startswith(stem + "_")) or (stem and stem in fname):
                    return full
                if size_match is None:
                    size_match = full
        return size_match

    def _get_output_template(self):
        """Return the configured output template, or '' when none is set."""
        try:
            template = self.template_entry.text().strip()
        except Exception:
            template = ""
        if not template:
            try:
                from utils.settings_utils import settings_manager
                template = settings_manager.get_setting("last_output_template", "") or ""
            except Exception:
                template = ""
        return template

    def _move_into_download_folder(self, src: str, dest_dir: str, preferred_name: str = None):
        try:
            name = preferred_name or os.path.basename(src)
            rel = None
            template = self._get_output_template()
            if template and hasattr(self, "_resolve_file_template"):
                try:
                    rel = self._resolve_file_template(src, template)
                except Exception:
                    rel = None
            if rel:
                rel = rel.strip("/\\")
                # Preserve the source extension if the template doesn't set one.
                orig_ext = os.path.splitext(name)[1]
                if os.path.splitext(rel)[1].lower() != orig_ext.lower():
                    rel += orig_ext
            else:
                rel = name

            dest = os.path.join(dest_dir, rel)
            base, ext = os.path.splitext(dest)
            counter = 1
            while os.path.exists(dest):
                dest = f"{base} ({counter}){ext}"
                counter += 1
            target_dir = os.path.dirname(dest)
            if target_dir:
                os.makedirs(target_dir, exist_ok=True)
            # shutil.move handles cross-device moves (staging dir may be on a
            # different filesystem than the download folder).
            shutil.move(src, dest)
            self._files_pending_refresh = True
            if hasattr(self, "refresh_files_list") and self.tabs.currentWidget() is getattr(self, "_files_tab", None):
                self.refresh_files_list()
            return True
        except Exception as e:
            print(f"[soulseek] failed to move {src}: {e}")
            return False
