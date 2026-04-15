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


def _detect_system_language() -> str:
    """Detect the system language and return a supported locale code.

    Falls back to ``"en"`` when the system locale is not among the
    available translations.
    """
    try:
        lang_code = locale.getdefaultlocale()[0] or ""
    except ValueError:
        lang_code = ""
    # lang_code is e.g. "fr_FR", "en_US", "de_DE" – take the prefix
    short = lang_code.split("_")[0].lower()
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


def set_language(code: str):
    """Switch the active language at runtime."""
    global _current_language, _translations
    _current_language = code
    resolved = _detect_system_language() if code == "system" else code
    if resolved == "en":
        _translations = _fallback
    else:
        _translations = _load_locale(resolved)


def get_language() -> str:
    """Return the current language code."""
    return _current_language


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
