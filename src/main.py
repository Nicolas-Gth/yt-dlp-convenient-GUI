"""
Main entry point for the yt-dlp Convenient GUI application.

This application provides a user-friendly graphical interface for downloading
videos and audio from YouTube using yt-dlp.

Architecture:
- main.py: Entry point
- config.py: Configuration and constants
- models/: Data models and structures
- views/: GUI components and layouts
- controllers/: Business logic and coordination
- utils/: Utility functions and helpers

Author: Nicolas-Gth
"""

import sys
import os

# Add the src directory to the Python path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    """Main entry point for the application.

    The startup dialog only depends on PySide6 + lightweight utils so it can
    run *before* heavy third-party packages (Pillow, mutagen, yt-dlp) are
    available.  ApplicationController is imported lazily, after the dialog
    has confirmed (and possibly installed) all dependencies.
    """
    from PySide6.QtWidgets import QApplication
    from utils.i18n_utils import init as i18n_init
    from utils.settings_utils import settings_manager
    from utils.theme_utils import apply_theme
    from startup_view import StartupDialog

    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setDesktopFileName('yt-dlp-gui')

    # Apply saved theme & language so the startup dialog is translated
    saved_theme = settings_manager.get_setting('theme', 'system')
    apply_theme(app, saved_theme)
    saved_language = settings_manager.get_setting('language', 'system')
    i18n_init(saved_language)

    # Show startup dialog (dependency checks, updates)
    startup = StartupDialog()
    if startup.exec() != StartupDialog.Accepted:
        sys.exit(0)

    # Now that all deps are guaranteed, import the full controller
    from controllers import ApplicationController
    controller = ApplicationController()
    controller.run()

if __name__ == "__main__":
    main()
