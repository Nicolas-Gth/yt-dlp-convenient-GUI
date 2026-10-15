from .setup import SoulseekSetupMixin
from .handlers import SoulseekHandlersMixin
from .i18n import SoulseekI18nMixin


class SoulseekMixin(SoulseekSetupMixin, SoulseekHandlersMixin, SoulseekI18nMixin):
    """Mixin that provides the Soulseek search & download tab."""
    pass
