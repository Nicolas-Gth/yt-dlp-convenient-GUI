"""
User-facing error messages for common download failures.
"""
from config import COOKIES_DIR
from utils.i18n_utils import t


def _get_instructions() -> str:
    """Return the translated cookie export instructions."""
    return t("cookies.instructions", cookies_dir=COOKIES_DIR)


def cookie_error_message() -> str:
    """Return a user-friendly error message for cookie / bot-check errors."""
    return t("error.cookie_message", instructions=_get_instructions())


def age_restricted_error_message(entries: list) -> str:
    """Return a user-friendly popup message when videos were skipped due to age restriction."""
    count = len(entries)
    return t("error.age_restricted", count=count, instructions=_get_instructions())
