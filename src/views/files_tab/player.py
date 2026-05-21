from PySide6.QtCore import Qt, QUrl, QSize
from PySide6.QtGui import QIcon
from PySide6.QtMultimedia import QMediaPlayer

from utils.i18n_utils import t
from utils.theme_utils import is_dark_mode


class FilesPlayerMixin:
    """Mixin that provides the audio player for the files tab."""

    def _on_play_clicked(self):
        if not self._current_detail_filepath:
            return
        state = self._media_player.playbackState()
        if state == QMediaPlayer.PlayingState:
            self._media_player.pause()
        elif state == QMediaPlayer.PausedState:
            self._media_player.play()
        else:
            current_url = QUrl.fromLocalFile(self._current_detail_filepath)
            if self._media_player.source() != current_url:
                self._media_player.setSource(current_url)
            self._media_player.play()

    def _update_play_icon(self, is_playing: bool):
        """Update play/pause icon based on current state and theme."""
        dark = is_dark_mode()
        if is_playing:
            icon_path = "assets/ui/pause-icon-light.svg" if dark else "assets/ui/pause-icon-dark.svg"
        else:
            icon_path = "assets/ui/play-icon-light.svg" if dark else "assets/ui/play-icon-dark.svg"
        self._play_btn.setIcon(QIcon(icon_path))
        self._play_btn.setIconSize(QSize(16, 16))

    def _on_playback_state_changed(self, state):
        self._update_play_icon(is_playing=(state == QMediaPlayer.PlayingState))

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
