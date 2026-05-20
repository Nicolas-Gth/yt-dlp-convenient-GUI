from PySide6.QtCore import QTimer

from utils.i18n_utils import t


class ProgressETAMixin:
    """Mixin that manages ETA display."""

    def set_eta_callback(self, callback):
        """Set the callback used to compute the ETA string."""
        self._eta_callback = callback

    def _update_eta_timer(self):
        """Refresh the ETA labels every second."""
        if hasattr(self, 'eta_elapsed_label') and self.eta_elapsed_label is not None:
            if callable(getattr(self, '_eta_callback', None)):
                result = self._eta_callback()
                if isinstance(result, tuple):
                    self.eta_elapsed_label.setText(result[0])
                    self.eta_remaining_label.setText(result[1])
                else:
                    self.eta_elapsed_label.setText(result)
                    self.eta_remaining_label.setText("")

    def _stop_eta_timer(self):
        """Stop the ETA refresh timer."""
        if hasattr(self, '_eta_timer') and self._eta_timer is not None:
            self._eta_timer.stop()

    def update_eta(self, eta_text: str):
        """Update the estimated remaining time labels."""
        if hasattr(self, 'eta_elapsed_label') and self.eta_elapsed_label is not None:
            if isinstance(eta_text, tuple):
                self.eta_elapsed_label.setText(eta_text[0])
                self.eta_remaining_label.setText(eta_text[1])
            else:
                self.eta_elapsed_label.setText(eta_text)
                self.eta_remaining_label.setText("")
