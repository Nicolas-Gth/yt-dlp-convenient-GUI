from utils.i18n_utils import t

from .constants import _RESULT_COLUMNS, _TRANSFER_COLUMNS


class SoulseekI18nMixin:
    """Mixin that retranslates the Soulseek tab."""

    def retranslate_soulseek_tab(self):
        if not hasattr(self, "_soulseek_tab") or self._soulseek_tab is None:
            return
        idx = self.tabs.indexOf(self._soulseek_tab)
        if idx >= 0:
            self.tabs.setTabText(idx, t("tabs.soulseek"))
        if hasattr(self, "_soulseek_connect_btn") and self._soulseek_connect_btn is not None:
            self._soulseek_connect_btn.setText(t("soulseek.connect"))
        if hasattr(self, "_soulseek_search") and self._soulseek_search is not None:
            self._soulseek_search.setPlaceholderText(t("soulseek.search_placeholder"))
        if hasattr(self, "_soulseek_search_btn") and self._soulseek_search_btn is not None:
            self._soulseek_search_btn.setText(t("soulseek.search"))
        if hasattr(self, "_soulseek_results_group") and self._soulseek_results_group is not None:
            self._soulseek_results_group.setTitle(t("soulseek.results_group"))
        if hasattr(self, "_soulseek_transfers_group") and self._soulseek_transfers_group is not None:
            self._soulseek_transfers_group.setTitle(t("soulseek.transfers_group"))
        if hasattr(self, "_soulseek_download_btn") and self._soulseek_download_btn is not None:
            self._soulseek_download_btn.setText(t("soulseek.download_selected"))
        if hasattr(self, "_soulseek_clear_btn") and self._soulseek_clear_btn is not None:
            self._soulseek_clear_btn.setText(t("soulseek.clear_completed"))
        if hasattr(self, "_soulseek_results_table") and self._soulseek_results_table is not None:
            self._soulseek_results_table.setHorizontalHeaderLabels([t(k) for k, _ in _RESULT_COLUMNS])
        if hasattr(self, "_soulseek_transfers_table") and self._soulseek_transfers_table is not None:
            self._soulseek_transfers_table.setHorizontalHeaderLabels([t(k) for k in _TRANSFER_COLUMNS])
