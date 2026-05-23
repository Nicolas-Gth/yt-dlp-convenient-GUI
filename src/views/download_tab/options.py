from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QGroupBox, QCheckBox, QLabel, QLineEdit, QPushButton, QMessageBox
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt, QSize

from config import INFO_ICON_PATH
from utils.i18n_utils import t


class DownloadOptionsMixin:
    """Mixin that creates options widgets (normalize, enrich, prevent sleep)."""

    def create_options_selection(self):
        """Create options fieldset with normalize, enrich and prevent-sleep checkboxes."""
        self.options_box = QGroupBox(t("extras.group_title"))
        options_layout = QVBoxLayout(self.options_box)

        # Normalize volume
        self.normalize_layout = QHBoxLayout()

        self.normalize_check = QCheckBox(t("options.normalize_volume"))
        self.normalize_check.setCursor(Qt.PointingHandCursor)
        self.normalize_check.setChecked(self._normalize_var)
        self.normalize_check.toggled.connect(self._on_normalize_toggled)
        self.normalize_layout.addWidget(self.normalize_check)

        # Normalize target widgets (hidden by default)
        self.normalize_target_label = QLabel(t("options.normalize_target"))
        self.normalize_layout.addWidget(self.normalize_target_label)

        self.normalize_target_entry = QLineEdit()
        self.normalize_target_entry.setFixedWidth(50)
        self.normalize_target_entry.setText(str(self._normalize_target_var))
        self.normalize_layout.addWidget(self.normalize_target_entry)

        self.normalize_info_btn = QPushButton()
        self.normalize_info_btn.setIcon(QIcon(INFO_ICON_PATH))
        self.normalize_info_btn.setIconSize(QSize(14, 14))
        self.normalize_info_btn.setFlat(True)
        self.normalize_info_btn.setCursor(Qt.PointingHandCursor)
        self.normalize_info_btn.setFixedSize(20, 20)
        self.normalize_info_btn.clicked.connect(
            lambda: QMessageBox.information(self, t("options.normalize_volume"), t("options.normalize_tooltip"))
        )
        self.normalize_layout.addWidget(self.normalize_info_btn)
        self.normalize_layout.addStretch()

        options_layout.addLayout(self.normalize_layout)

        # Set initial visibility
        visible = self._normalize_var
        self.normalize_target_label.setVisible(visible)
        self.normalize_target_entry.setVisible(visible)

        # Enrich metadata
        enrich_layout = QHBoxLayout()

        self.enrich_check = QCheckBox(t("options.enrich_metadata"))
        self.enrich_check.setCursor(Qt.PointingHandCursor)
        self.enrich_check.setChecked(self._enrich_var)
        self.enrich_check.toggled.connect(self._on_enrich_toggled)
        enrich_layout.addWidget(self.enrich_check)

        self.enrich_info_btn = QPushButton()
        self.enrich_info_btn.setIcon(QIcon(INFO_ICON_PATH))
        self.enrich_info_btn.setIconSize(QSize(14, 14))
        self.enrich_info_btn.setFlat(True)
        self.enrich_info_btn.setCursor(Qt.PointingHandCursor)
        self.enrich_info_btn.setFixedSize(20, 20)
        self.enrich_info_btn.clicked.connect(
            lambda: QMessageBox.information(self, t("options.enrich_metadata"), t("options.enrich_tooltip"))
        )
        enrich_layout.addWidget(self.enrich_info_btn)
        enrich_layout.addStretch()

        options_layout.addLayout(enrich_layout)

        options_wrapper = QHBoxLayout()
        options_wrapper.setContentsMargins(5, 0, 5, 0)
        options_wrapper.addWidget(self.options_box)

        self.settings_layout.addLayout(options_wrapper)

    def show_normalize_input(self):
        """Show the normalize target LUFS input."""
        self.normalize_target_label.setVisible(True)
        self.normalize_target_entry.setVisible(True)

    def hide_normalize_input(self):
        """Hide the normalize target LUFS input."""
        self.normalize_target_label.setVisible(False)
        self.normalize_target_entry.setVisible(False)
