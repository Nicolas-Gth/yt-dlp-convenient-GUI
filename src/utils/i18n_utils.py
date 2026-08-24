"""
Internationalization (i18n) utility for the yt-dlp GUI application.

Loads translations from JSON files in the locales/ directory.
Usage:
    from utils.i18n_utils import t
    label = t("button.download")
    label = t("download.single", title="My Video")

Community contributions:
    To add a new language, copy locales/en.json to locales/<code>.json
    and translate the values. Then add the language code and label to
    AVAILABLE_LANGUAGES below.
"""
import json
import locale
import os
import sys
from pathlib import Path
from typing import Dict, Optional

# Map of language codes to display labels (shown in the Language menu).
# To add a new language, add an entry here and create the matching JSON file.
AVAILABLE_LANGUAGES = {
    "en": "English",
    "fr": "Français",
    "es": "Español",
    "de": "Deutsch",
    "it": "Italiano",
    "nl": "Nederlands",
}

# Ordered list of (code, display_label) for the Language menu.
# "system" uses t() for its label; the rest use their native name.
MENU_LANGUAGES = [
    ("system", "menu.language.system"),
] + [(code, label) for code, label in AVAILABLE_LANGUAGES.items()]

_LOCALES_DIR = Path(__file__).resolve().parent.parent.parent / "locales"

_current_language: str = "system"
_translations: Dict[str, str] = {}
_fallback: Dict[str, str] = {}
_qt_translators: list = []


def _find_qt_translation_files(code: str) -> list[Path]:
    """Find PySide6 Qt translation files for the given language code.

    Returns ``qt_{code}.qm`` (full Qt widgets) and ``qtbase_{code}.qm``
    (core strings), whichever exist.
    """
    try:
        import PySide6
    except ImportError:
        return []
    qt_translations_dir = Path(PySide6.__file__).parent / "Qt" / "translations"
    files = []
    for name in (f"qt_{code}.qm", f"qtbase_{code}.qm"):
        path = qt_translations_dir / name
        if path.exists():
            files.append(path)
    return files


def _install_qt_translator(code: str):
    """Install (or remove) Qt translators matching the active language."""
    global _qt_translators
    try:
        from PySide6.QtCore import QTranslator, QCoreApplication
    except ImportError:
        return
    app = QCoreApplication.instance()
    for translator in _qt_translators:
        if app:
            app.removeTranslator(translator)
    _qt_translators = []

    if code == "en":
        return  # English is built-in; nothing to load.

    for qm_path in _find_qt_translation_files(code):
        translator = QTranslator()
        if translator.load(str(qm_path)):
            if app:
                app.installTranslator(translator)
            _qt_translators.append(translator)


def _detect_system_language() -> str:
    """Detect the system language and return a supported locale code.

    On macOS, reads the ``AppleLanguages`` user default which reflects
    the actual System Settings language (the POSIX locale often stays
    ``en_US`` regardless of the UI language).  Falls back to
    ``locale.getdefaultlocale()`` on other platforms.

    Returns ``"en"`` when the detected language is not among the
    available translations.
    """
    lang_code = ""
    if sys.platform == "darwin":
        try:
            import subprocess
            r = subprocess.run(
                ["defaults", "read", "-g", "AppleLanguages"],
                capture_output=True, text=True, timeout=5,
            )
            if r.returncode == 0:
                # Output looks like: (\n    "fr-BE",\n    "en-US"\n)
                for line in r.stdout.splitlines():
                    line = line.strip().strip('"').strip(",").strip('"')
                    if line and line not in ("(", ")"):
                        lang_code = line
                        break
        except Exception:
            pass
    if not lang_code:
        try:
            lang_code = locale.getdefaultlocale()[0] or ""
        except ValueError:
            lang_code = ""
    # lang_code may be "fr-BE", "fr_FR", "en_US", "de" etc.
    short = lang_code.replace("-", "_").split("_")[0].lower()
    if short in AVAILABLE_LANGUAGES:
        return short
    return "en"


def _load_locale(code: str) -> Dict[str, str]:
    """Load a locale JSON file and return the flat key→string mapping."""
    path = _LOCALES_DIR / f"{code}.json"
    if not path.exists():
        print(f"Warning: locale file not found: {path}")
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Strip the _meta key
    data.pop("_meta", None)
    return data


def init(language: str = "system"):
    """Initialize the i18n system. Must be called once at startup."""
    global _current_language, _translations, _fallback
    _fallback = _load_locale("en")
    _current_language = language
    resolved = _detect_system_language() if language == "system" else language
    if resolved == "en":
        _translations = _fallback
    else:
        _translations = _load_locale(resolved)
    _install_qt_translator(resolved)


def set_language(code: str):
    """Switch the active language at runtime."""
    global _current_language, _translations
    _current_language = code
    resolved = _detect_system_language() if code == "system" else code
    if resolved == "en":
        _translations = _fallback
    else:
        _translations = _load_locale(resolved)
    _install_qt_translator(resolved)


def get_language() -> str:
    """Return the current language code."""
    return _current_language


_PLURAL_SUFFIX_RULES = {
    "en": lambda n: "" if n == 1 else "s",
    "fr": lambda n: "" if n <= 1 else "s",
    "es": lambda n: "" if n == 1 else "s",
    "de": lambda n: "" if n == 1 else "en",
    "it": lambda n: "",
    "nl": lambda n: "" if n == 1 else "en",
}


def plural_suffix(count: int) -> str:
    """Return the plural suffix for *count* in the active language.

    Designed for translation templates such as ``"{count} file{count_s}"``,
    yielding e.g. ``1 file`` / ``2 files`` (or ``1 Datei`` / ``2 Dateien``).
    """
    resolved = _detect_system_language() if _current_language == "system" else _current_language
    rule = _PLURAL_SUFFIX_RULES.get(resolved, _PLURAL_SUFFIX_RULES["en"])
    return rule(count)


def t(key: str, **kwargs) -> str:
    """Translate *key*, interpolating any ``{name}`` placeholders with *kwargs*.

    Falls back to English if the key is missing in the active locale,
    and returns the raw key if it is missing everywhere.
    """
    text = _translations.get(key) or _fallback.get(key) or key
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError):
            pass
    return text


# Auto-init with system language so that imports of ``t`` work immediately.
init("system")
