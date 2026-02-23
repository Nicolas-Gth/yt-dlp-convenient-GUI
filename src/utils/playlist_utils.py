"""
YouTube playlist utilities for yt-dlp Convenient GUI.

Provides helpers that use the YouTube innertube API to resolve
the *displayed* playlist order (which may differ from the API order
when videos are deleted, private, or region-restricted) and to
compute the offset between the two numberings.
"""
import http.cookiejar
import json
import os
import re
import urllib.request
from typing import Any, Dict, List, Optional

from config import COOKIES_PATH


# ------------------------------------------------------------------
# URL helpers
# ------------------------------------------------------------------

def normalize_playlist_url(url: str) -> str:
    """Convert a watch?v=…&list=… URL into a clean playlist URL.

    When the user pastes a URL like
    https://www.youtube.com/watch?v=XXX&list=PLyyy&index=N
    yt-dlp may treat it as a single-video extraction instead of a
    playlist, which causes playlist slicing / interval to be ignored.
    Stripping the video parameters ensures yt-dlp always sees a pure
    playlist URL.
    """
    m = re.search(r'[?&]list=([^&]+)', url)
    if not m:
        return url  # No playlist ID found, return as-is
    playlist_id = m.group(1)
    # Determine base domain (youtube.com vs music.youtube.com)
    if 'music.youtube.com' in url:
        return f"https://music.youtube.com/playlist?list={playlist_id}"
    return f"https://www.youtube.com/playlist?list={playlist_id}"


def extract_playlist_id(url: str) -> Optional[str]:
    """Extract the playlist ID (PLxxx…) from a YouTube / YT Music URL."""
    m = re.search(r'[?&]list=([^&]+)', url)
    return m.group(1) if m else None


# ------------------------------------------------------------------
# Innertube low-level helpers
# ------------------------------------------------------------------

def innertube_browse(playlist_id: str, continuation: Optional[str] = None) -> Optional[Dict]:
    """Single innertube browse request. Returns raw JSON or None.

    When a cookies.txt file is available, the cookies are sent along
    so that the innertube API sees the same entries as yt-dlp
    (including age-restricted or membership-only videos).
    """
    body: Dict[str, Any] = {
        "context": {
            "client": {
                "clientName": "WEB",
                "clientVersion": "2.20250201.00.00",
            }
        }
    }
    if continuation:
        body["continuation"] = continuation
    else:
        body["browseId"] = f"VL{playlist_id}"

    data = json.dumps(body).encode()
    req = urllib.request.Request(
        "https://www.youtube.com/youtubei/v1/browse",
        data=data,
        headers={"Content-Type": "application/json",
                 "User-Agent": "Mozilla/5.0"},
    )

    # Build an opener that includes cookies when available
    handlers: list = []
    if os.path.isfile(COOKIES_PATH):
        try:
            cj = http.cookiejar.MozillaCookieJar(COOKIES_PATH)
            cj.load(ignore_discard=True, ignore_expires=True)
            handlers.append(urllib.request.HTTPCookieProcessor(cj))
        except Exception as exc:
            print(f"  [innertube] Could not load cookies: {exc}")

    opener = urllib.request.build_opener(*handlers)

    try:
        with opener.open(req, timeout=20) as resp:
            return json.loads(resp.read())
    except Exception as exc:
        print(f"  [innertube] Request failed: {exc}")
        return None


def parse_innertube_items(result: Dict, is_continuation: bool) -> list:
    """Extract the list of renderer items from an innertube response."""
    try:
        if is_continuation:
            for action in result.get("onResponseReceivedActions", []):
                items = (action
                         .get("appendContinuationItemsAction", {})
                         .get("continuationItems", []))
                if items:
                    return items
            return []
        else:
            tabs = (result.get("contents", {})
                          .get("twoColumnBrowseResultsRenderer", {})
                          .get("tabs", []))
            if not tabs:
                return []
            section = (tabs[0]
                       .get("tabRenderer", {})
                       .get("content", {})
                       .get("sectionListRenderer", {})
                       .get("contents", [{}])[0])
            playlist_renderer = (section
                                 .get("itemSectionRenderer", {})
                                 .get("contents", [{}])[0]
                                 .get("playlistVideoListRenderer", {}))
            return playlist_renderer.get("contents", [])
    except (KeyError, IndexError, TypeError):
        return []


# ------------------------------------------------------------------
# High-level playlist helpers
# ------------------------------------------------------------------

def get_youtube_visible_ids(playlist_id: str, count: int) -> List[str]:
    """Return the first *count* visible video IDs as displayed on youtube.com.

    Uses the innertube browse API, which returns **only entries that
    YouTube displays** to the user (skipping deleted / private /
    region-blocked videos).  This list therefore matches the numbering
    the user sees on the website.
    """
    video_ids: list = []
    continuation: Optional[str] = None

    for _page in range(max(1, count // 100 + 5)):
        result = innertube_browse(playlist_id, continuation)
        if not result:
            break

        items = parse_innertube_items(result, continuation is not None)
        continuation = None

        for item in items:
            if "playlistVideoRenderer" in item:
                vid = item["playlistVideoRenderer"].get("videoId", "")
                if vid:
                    video_ids.append(vid)
                    if len(video_ids) >= count:
                        return video_ids
            elif "continuationItemRenderer" in item:
                cir = item["continuationItemRenderer"]
                token = None
                # Path 1: continuationEndpoint → continuationCommand → token
                try:
                    token = cir["continuationEndpoint"]["continuationCommand"]["token"]
                except (KeyError, TypeError):
                    pass
                # Path 2: continuationEndpoint → commandExecutorCommand
                # (wraps multiple commands; the continuation token is
                #  inside one of the sub-commands)
                if not token:
                    try:
                        cmds = (cir["continuationEndpoint"]
                                   ["commandExecutorCommand"]
                                   ["commands"])
                        for cmd in cmds:
                            ct = (cmd.get("continuationCommand") or {}).get("token")
                            if ct:
                                token = ct
                                break
                    except (KeyError, TypeError):
                        pass
                # Path 3: button → buttonRenderer → command
                if not token:
                    try:
                        token = (cir["button"]["buttonRenderer"]["command"]
                                 ["continuationCommand"]["token"])
                    except (KeyError, TypeError):
                        pass
                if token:
                    continuation = token

        if not continuation:
            break

    return video_ids


def compute_playlist_offset(url: str, target_pos: int,
                            target_end: int,
                            flat_entries: list) -> tuple[int, list]:
    """Compare YouTube's displayed numbering with the flat-extracted list.

    Returns a tuple ``(offset, hidden_entries)`` where *offset* is the
    value to ADD to the user's position to obtain the correct index in
    *flat_entries*, and *hidden_entries* is a list of dicts describing
    entries that YouTube hides but the API still returns **within the
    user's requested range** (``target_pos`` to ``target_end``).

    Entries before the range are ignored — they only contribute to the
    offset.  Returns ``(0, [])`` when no offset is detected or the
    probe fails.
    """
    playlist_id = extract_playlist_id(url)
    if not playlist_id:
        return 0, []

    # Probe YouTube for displayed positions covering the full
    # requested range so we can also detect hidden entries inside it.
    probe_count = target_end
    print(f"  [playlist] Probing YouTube for displayed positions 1–{probe_count}…")
    yt_ids = get_youtube_visible_ids(playlist_id, probe_count)

    if len(yt_ids) < target_pos:
        print(f"  [playlist] Probe returned only {len(yt_ids)} IDs "
              f"(need {target_pos}), skipping offset detection")
        return 0, []

    target_id = yt_ids[target_pos - 1]

    # Locate that video ID in the flat-extracted list
    api_idx_found = None
    for api_idx, entry in enumerate(flat_entries):
        if entry and isinstance(entry, dict) and entry.get("id") == target_id:
            api_idx_found = api_idx
            break

    if api_idx_found is None:
        print(f"  [playlist] Target ID {target_id} not found in flat list")
        return 0, []

    offset = api_idx_found - (target_pos - 1)
    if offset != 0:
        print(f"  [playlist] Offset detected: {offset}  "
              f"(YouTube #{target_pos} \"{flat_entries[api_idx_found].get('title', '?')}\" "
              f"→ API index {api_idx_found + 1})")
    else:
        print(f"  [playlist] No offset — positions match")

    # Detect hidden entries only within the user's requested range.
    # YouTube visible IDs for positions [target_pos … target_end]:
    yt_range_end = min(target_end, len(yt_ids))
    yt_range_ids = set(yt_ids[target_pos - 1 : yt_range_end])

    range_start_api = target_pos - 1 + offset
    range_end_api = min(target_end + offset, len(flat_entries))

    hidden: list = []
    for i in range(range_start_api, range_end_api):
        e = flat_entries[i]
        if not e or not isinstance(e, dict):
            hidden.append({'title': '<Unknown>', 'channel': '', 'id': ''})
            continue
        eid = e.get('id', '')
        if eid and eid not in yt_range_ids:
            hidden.append({
                'title': e.get('title', '<Unknown>'),
                'channel': (e.get('channel') or e.get('uploader') or ''),
                'id': eid,
            })

    return offset, hidden
