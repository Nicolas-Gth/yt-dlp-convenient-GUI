"""
User-facing error messages for common download failures.
"""
from config import COOKIES_INSTRUCTIONS


def cookie_error_message() -> str:
    """Return a user-friendly error message for cookie / bot-check errors."""
    return (
        "YouTube is asking you to prove you're not a bot.\n\n"
        "To fix this, you need to provide your browser cookies:\n\n"
        + COOKIES_INSTRUCTIONS
    )


def age_restricted_error_message(entries: list) -> str:
    """Return a user-friendly popup message when videos were skipped due to age restriction."""
    count = len(entries)
    plural = 's' if count > 1 else ''
    them = 'them' if count > 1 else 'it'

    return (
        f"{count} video{plural} could not be downloaded because "
        f"{'they require' if count > 1 else 'it requires'} age verification.\n\n"
        f"To download {them}, you need to provide your browser cookies:\n\n"
        + COOKIES_INSTRUCTIONS
    )
