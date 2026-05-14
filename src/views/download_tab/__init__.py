from .setup import DownloadSetupMixin
from .url import DownloadURLMixin
from .path import DownloadPathMixin
from .format import DownloadFormatMixin
from .playlist import DownloadPlaylistMixin
from .options import DownloadOptionsMixin
from .button import DownloadButtonMixin
from .disclaimer import DownloadDisclaimerMixin


class DownloadTabMixin(DownloadSetupMixin, DownloadURLMixin, DownloadPathMixin,
                       DownloadFormatMixin, DownloadPlaylistMixin,
                       DownloadOptionsMixin, DownloadButtonMixin,
                       DownloadDisclaimerMixin):
    """Mixin that provides all download-tab widgets for MainApplicationView."""
    pass
