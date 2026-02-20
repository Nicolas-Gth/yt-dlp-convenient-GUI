"""
Cookies validation utilities for yt-dlp Convenient GUI.

Validates the cookies.txt file format, expiration dates, and
performs a live check against YouTube to detect revoked cookies.
"""
import http.cookiejar
import os
import time
import urllib.request
from typing import Optional

from config import COOKIES_PATH


def validate_cookies_file() -> Optional[str]:
    """Check cookies.txt validity and return a warning message, or None if OK.

    Performs three levels of validation:
    1. Format check – the file must contain valid Netscape cookie lines.
    2. Expiration check – non-session cookies must not all be expired.
    3. Live check – actually test the cookies against YouTube to see
       if they are accepted (catches tampered / revoked cookies).
    """
    if not os.path.isfile(COOKIES_PATH):
        return None  # No cookies file, nothing to validate

    try:
        with open(COOKIES_PATH, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception:
        return None  # Can't read the file, skip validation

    # --- 1. Format & expiration check ---
    has_valid_cookie = False
    has_expired = False
    now = time.time()

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue

        fields = stripped.split('\t')
        if len(fields) < 7:
            continue

        has_valid_cookie = True
        try:
            expiration = int(fields[4])
        except ValueError:
            continue

        if expiration != 0 and expiration < now:
            has_expired = True

    if not has_valid_cookie:
        return (
            "The cookies.txt file is present but does not contain any valid cookies.\n\n"
            "This may cause the download to fail.\n\n"
            "Please update it with fresh cookies from your browser, "
            "or delete it if you don't need it."
        )
    if has_expired:
        return (
            "Some cookies in cookies.txt have expired.\n\n"
            "This may cause YouTube downloads to fail "
            "(bot detection, age-restricted content, etc.).\n\n"
            "Please update the file with fresh cookies from your browser, "
            "or delete it if you don't need it."
        )

    # --- 2. Live validation against YouTube ---
    try:
        jar = http.cookiejar.MozillaCookieJar(COOKIES_PATH)
        jar.load(ignore_discard=True, ignore_expires=True)

        opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(jar)
        )
        req = urllib.request.Request(
            "https://www.youtube.com/",
            headers={"User-Agent": "Mozilla/5.0"}
        )
        response = opener.open(req, timeout=10)
        body = response.read().decode("utf-8", errors="replace")

        # YouTube embeds a LOGGED_IN flag in its page source
        if '"LOGGED_IN":false' in body:
            return (
                "The cookies in cookies.txt are not valid or have been revoked "
                "by YouTube.\n\n"
                "This may cause downloads to fail "
                "(bot detection, age-restricted content, etc.).\n\n"
                "Please update the file with fresh cookies from your browser, "
                "or delete it if you don't need it."
            )
    except Exception:
        # Network error or parsing issue – don't block the user
        pass

    return None
