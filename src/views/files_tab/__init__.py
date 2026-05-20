import os

# Suppress ffmpeg backend noise from QMediaPlayer
if 'AV_LOG_LEVEL' not in os.environ:
    os.environ['AV_LOG_LEVEL'] = 'quiet'
if 'QT_LOGGING_RULES' not in os.environ:
    os.environ['QT_LOGGING_RULES'] = 'qt.multimedia.ffmpeg.debug=false;qt.multimedia.ffmpeg.info=false'

from .metadata import _tag_label, _load_audio, _extract_title_artist, _check_lyrics, _extract_artwork, _extract_all_metadata, _extract_lyrics_text
from .widgets import _ArtworkLabel, _SeekSlider, _ArtworkWrapper
from .setup import FilesSetupMixin
from .player import FilesPlayerMixin
from .file_list import FilesListMixin
from .detail import FilesDetailMixin
from .editor import FilesEditorMixin
from .i18n import FilesI18nMixin


class FilesMixin(FilesSetupMixin, FilesPlayerMixin, FilesListMixin,
                 FilesDetailMixin, FilesEditorMixin, FilesI18nMixin):
    """Mixin that provides the 'Download folder' tab."""
    pass
