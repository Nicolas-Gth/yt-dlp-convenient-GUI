import os

from PySide6.QtWidgets import QTableWidgetItem
from PySide6.QtCore import Qt

from utils.i18n_utils import t

from .metadata import _load_audio
from .constants import _FIELD_KEYS


class FilesEditorMixin:
    """Mixin that handles metadata editing and saving."""

    def _on_lyrics_changed(self):
        self._edited = True
        self._edit_reset_btn.show()
        self._edit_save_btn.show()

    def _on_meta_item_changed(self, item):
        if item.column() == 1 and item.flags() & Qt.ItemIsEditable:
            self._modified_rows.add(item.row())
            self._edited = True
            self._edit_reset_btn.show()
            self._edit_save_btn.show()

    def _on_reset_metadata(self):
        if self._current_detail_filepath:
            self._files_meta.itemChanged.disconnect(self._on_meta_item_changed)
            self._show_file_detail(self._current_detail_filepath)

    def _on_save_metadata(self):
        if not self._current_detail_filepath:
            return
        self._files_meta.setCurrentCell(-1, -1)
        audio = _load_audio(self._current_detail_filepath)
        if audio is None or audio.tags is None:
            return
        try:
            from mutagen.mp4 import MP4
            from mutagen.oggopus import OggOpus
            tags = audio.tags
            new_filepath = self._current_detail_filepath
            # Handle lyrics (separate widget)
            lyrics_val = self._lyrics_edit.toPlainText()
            if lyrics_val.strip():
                if isinstance(audio, OggOpus):
                    tags['lyrics'] = [lyrics_val]
                elif isinstance(audio, MP4):
                    tags['\xa9lyr'] = [lyrics_val]
                else:
                    from mutagen.id3 import USLT
                    uslt = USLT(encoding=3, lang='eng', desc='', text=lyrics_val)
                    tags.delall('USLT')
                    tags.add(uslt)
            else:
                # Remove lyrics tag when text is empty
                if isinstance(audio, OggOpus):
                    try:
                        del tags['lyrics']
                    except KeyError:
                        pass
                elif isinstance(audio, MP4):
                    try:
                        del tags['\xa9lyr']
                    except KeyError:
                        pass
                else:
                    tags.delall('USLT')
            for row in range(self._files_meta.rowCount()):
                val_item = self._files_meta.item(row, 1)
                if not val_item:
                    continue
                key = val_item.data(Qt.UserRole)
                if key == '_filename_':
                    new_name = val_item.text().strip()
                    if new_name:
                        base, ext = os.path.splitext(new_name)
                        orig_ext = os.path.splitext(self._current_detail_filepath)[1]
                        if not ext:
                            ext = orig_ext
                        elif ext.lower() != orig_ext.lower():
                            ext = orig_ext
                        new_filepath = os.path.join(os.path.dirname(self._current_detail_filepath), base + ext)
                    continue
                if key in _FIELD_KEYS:
                    tag_key = _FIELD_KEYS[key][0]
                    if isinstance(audio, OggOpus):
                        tag_key = _FIELD_KEYS[key][2]  # 'album', 'title', etc.
                    elif isinstance(audio, MP4):
                        tag_key = _FIELD_KEYS[key][1]  # '\xa9alb', '\xa9nam', etc.
                    key = tag_key
                val = val_item.text()
                if isinstance(audio, OggOpus):
                    tags[key] = [val]
                elif isinstance(audio, MP4):
                    tags[key] = [val]
                else:
                    frame = tags.get(key)
                    if frame and hasattr(frame, 'text'):
                        frame.text = [val]
                    elif val:
                        try:
                            cls = type(tags).__module__
                            frame_cls = getattr(tags, '_ID3Tags__module', {}).get(key)
                            if frame_cls:
                                tags.add(frame_cls(encoding=3, text=[val]))
                        except (KeyError, AttributeError):
                            pass
            audio.save()
            if new_filepath != self._current_detail_filepath and os.path.exists(self._current_detail_filepath):
                os.rename(self._current_detail_filepath, new_filepath)
                self._current_detail_filepath = new_filepath
            self._modified_rows.clear()
            self._edited = False
            self._edit_reset_btn.hide()
            self._edit_save_btn.hide()
            self._files_saved_selection = new_filepath
            self.refresh_files_list()
        except Exception as e:
            print(f"Save metadata error: {e}")
