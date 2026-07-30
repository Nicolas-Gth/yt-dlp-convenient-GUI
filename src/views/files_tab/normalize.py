import json
import os
import subprocess
import sys

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox, QDialogButtonBox, QProgressBar
)
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt, QSize

from config import DEFAULT_NORMALIZE_TARGET, INFO_ICON_PATH
from utils.i18n_utils import t


_SUPPORTED_ENCODERS = {
    '.mp3': 'libmp3lame',
    '.opus': 'libopus',
    '.ogg': 'libopus',
    '.m4a': 'aac',
    '.aac': 'aac',
    '.flac': 'flac',
    '.wav': 'pcm_s16le',
    '.wma': 'wmav2',
    '.mp4': 'aac',
    '.mkv': 'aac',
    '.webm': 'libopus',
    '.mov': 'aac',
    '.avi': 'aac',
}

_VIDEO_CONTAINERS = {'.mp4', '.mkv', '.webm', '.mov', '.avi'}


def _no_window_kwargs():
    if sys.platform != 'win32':
        return {}
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return {'startupinfo': si, 'creationflags': subprocess.CREATE_NO_WINDOW}


def _normalize_audio_file(file_path, target_lufs):
    from config import get_ffmpeg_path

    ext = os.path.splitext(file_path)[1].lower()
    encoder = _SUPPORTED_ENCODERS.get(ext)
    if not encoder:
        return False, f"Unsupported format: {ext}"

    ffmpeg_dir = get_ffmpeg_path()
    if ffmpeg_dir:
        ffmpeg_bin = os.path.join(ffmpeg_dir, 'ffmpeg')
        if not os.path.exists(ffmpeg_bin):
            ffmpeg_bin = 'ffmpeg'
    else:
        ffmpeg_bin = 'ffmpeg'

    base, ext_ = os.path.splitext(file_path)
    tmp_path = f"{base}.normalizing{ext_}"

    cmd = [
        ffmpeg_bin, '-y', '-i', file_path,
        '-af', f'loudnorm=I={target_lufs}:TP=-1.5:LRA=11',
    ]

    if ext in _VIDEO_CONTAINERS:
        cmd += ['-c:v', 'copy']

    cmd += ['-c:a', encoder, tmp_path]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, **_no_window_kwargs())
        if result.returncode != 0:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
            return False, result.stderr.strip()[-500:]
        os.replace(tmp_path, file_path)
        return True, None
    except Exception as e:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        return False, str(e)


def _measure_loudness(file_path):
    from config import get_ffmpeg_path

    ffmpeg_dir = get_ffmpeg_path()
    if ffmpeg_dir:
        ffmpeg_bin = os.path.join(ffmpeg_dir, 'ffmpeg')
        if not os.path.exists(ffmpeg_bin):
            ffmpeg_bin = 'ffmpeg'
    else:
        ffmpeg_bin = 'ffmpeg'

    try:
        result = subprocess.run(
            [ffmpeg_bin, '-i', file_path, '-af', 'loudnorm=print_format=json', '-f', 'null', '-'],
            capture_output=True, text=True, timeout=60, **_no_window_kwargs(),
        )
        stderr = result.stderr
        json_start = stderr.rfind('{')
        json_end = stderr.rfind('}') + 1
        if json_start != -1 and json_end > json_start:
            data = json.loads(stderr[json_start:json_end])
            return float(data.get('input_i', 0))
    except Exception:
        pass
    return None


class NormalizeDialog(QDialog):
    def __init__(self, parent=None, filepaths=None):
        super().__init__(parent)
        self.setWindowTitle(t("files.normalize_title"))
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        input_layout = QHBoxLayout()
        input_layout.setSpacing(6)

        target_label = QLabel(t("options.normalize_target"))
        input_layout.addWidget(target_label)

        self.target_entry = QLineEdit()
        self.target_entry.setFixedWidth(60)
        self.target_entry.setText(str(DEFAULT_NORMALIZE_TARGET))
        self.target_entry.selectAll()
        input_layout.addWidget(self.target_entry)

        info_btn = QPushButton()
        info_btn.setIcon(QIcon(INFO_ICON_PATH))
        info_btn.setIconSize(QSize(14, 14))
        info_btn.setFlat(True)
        info_btn.setCursor(Qt.PointingHandCursor)
        info_btn.setFixedSize(20, 20)
        info_btn.clicked.connect(
            lambda: QMessageBox.information(self, t("options.normalize_volume"), t("options.normalize_tooltip"))
        )
        input_layout.addWidget(info_btn)
        input_layout.addStretch()

        layout.addLayout(input_layout)

        if filepaths:
            MAX_VISIBLE = 5
            remaining = len(filepaths) - MAX_VISIBLE
            names = [os.path.basename(fp) for fp in filepaths[:MAX_VISIBLE]]
            if remaining > 0:
                names.append(t("files.restructure_more_selected").format(n=remaining))
            files_label = QLabel("\n".join(f"  \u2022 {n}" for n in names))
            files_label.setWordWrap(True)
            layout.addWidget(files_label)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _validate_and_accept(self):
        try:
            float(self.target_entry.text())
        except ValueError:
            QMessageBox.warning(self, t("options.normalize_volume"), "Please enter a valid number.")
            return
        self.accept()

    def get_target(self):
        try:
            return float(self.target_entry.text())
        except ValueError:
            return DEFAULT_NORMALIZE_TARGET


class FilesNormalizeMixin:

    def _on_normalize_files(self):
        filepaths = []
        for r in range(self._files_table.rowCount()):
            item = self._files_table.item(r, 0)
            if item:
                fp = item.data(Qt.UserRole)
                if fp and os.path.isfile(fp):
                    filepaths.append(fp)
        if not filepaths:
            QMessageBox.information(self, t("files.normalize_title"), t("batch.no_files_in_dir"))
            return
        self._prompt_normalize_and_run(filepaths)

    def _on_normalize_selected(self, rows):
        filepaths = self._get_selected_filepaths(rows)
        if not filepaths:
            return
        self._prompt_normalize_and_run(filepaths)

    def _prompt_normalize_and_run(self, filepaths):
        from PySide6.QtWidgets import QProgressDialog, QApplication
        from PySide6.QtCore import QTimer, QEventLoop

        dlg = NormalizeDialog(self, filepaths=filepaths)

        def _on_finished(result):
            if result != QDialog.Accepted:
                return
            target = dlg.get_target()
            dlg.deleteLater()

            progress = QProgressDialog(
                t("files.normalize_progress"),
                t("button.cancel"), 0, len(filepaths), self
            )
            progress.setWindowTitle(t("files.normalize_title"))
            progress.setWindowModality(Qt.WindowModal)
            progress.setMinimumDuration(0)
            progress.setAutoClose(True)
            bar = progress.findChild(QProgressBar)
            if bar:
                bar.setFormat(t("files.normalize_counter"))
            progress.show()
            progress.repaint()
            QApplication.processEvents(QEventLoop.ExcludeUserInputEvents)

            QTimer.singleShot(50, lambda: self._run_normalize(filepaths, target, progress))

        dlg.finished.connect(_on_finished)
        dlg.open()

    def _run_normalize(self, filepaths, target, progress):
        from PySide6.QtWidgets import QApplication

        succeeded = 0
        failed = 0
        errors = []
        increased = 0
        decreased = 0
        unchanged = 0

        for i, fp in enumerate(filepaths):
            if progress.wasCanceled():
                break
            progress.setValue(i)
            progress.setLabelText(t("files.normalize_processing").format(file=os.path.basename(fp)))
            QApplication.processEvents()

            input_lufs = _measure_loudness(fp)
            ok, err = _normalize_audio_file(fp, target)
            if ok:
                succeeded += 1
                if input_lufs is not None:
                    delta = input_lufs - target
                    if delta < -0.5:
                        increased += 1
                    elif delta > 0.5:
                        decreased += 1
                    else:
                        unchanged += 1
            else:
                failed += 1
                errors.append(f"{os.path.basename(fp)}: {err}")

        progress.setValue(len(filepaths))

        if failed > 0 and errors:
            detail = "\n".join(errors[:5])
            if len(errors) > 5:
                detail += f"\n...and {len(errors) - 5} more"
            QMessageBox.warning(self, t("files.normalize_title"), f"{detail}")
        elif succeeded > 0:
            msg = t("files.normalize_done", count=succeeded, count_s="" if succeeded <= 1 else "s")
            msg += "\n\n" + t("files.normalize_summary",
                             increased=increased, decreased=decreased, unchanged=unchanged)
            QMessageBox.information(self, t("files.normalize_title"), msg)

        self.refresh_files_list()
