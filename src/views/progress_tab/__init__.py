from .layout import ProgressLayoutMixin
from .setup import ProgressSetupMixin
from .eta import ProgressETAMixin
from .updates import ProgressUpdatesMixin
from .fetching import ProgressFetchingMixin
from .tables import ProgressTablesMixin


class ProgressMixin(ProgressSetupMixin, ProgressETAMixin,
                   ProgressUpdatesMixin, ProgressFetchingMixin, ProgressTablesMixin):
    pass
