"""
Metadata enrichment using MusicBrainz + Cover Art Archive + lyrics providers.

- Looks up the track on MusicBrainz by artist + title.
- If a confident match is found (exact album), fetches the high-quality
  album cover from Cover Art Archive (usually 1200×1200 or larger).
  Tries release-group cover first (aggregates all editions), then individual releases.
- Fetches synced or plain lyrics from LRCLIB, Genius (scraping), and lyrics.ovh.
- Embeds everything into the audio file via mutagen.

All network calls have generous timeouts and will never crash the app;
they degrade gracefully to the existing YouTube thumbnail / no lyrics.
"""
import html
import json
import re
import urllib.request
import urllib.parse
import urllib.error
from io import BytesIO
from typing import Optional, Dict, Tuple, List
from dataclasses import dataclass

# User-Agent required by MusicBrainz API policy
_USER_AGENT = "yt-dlp-convenient-GUI/2.1.0 (https://github.com/Nicolas-music/yt-dlp-convenient-GUI)"
_MB_BASE = "https://musicbrainz.org/ws/2"
_CA_BASE = "https://coverartarchive.org"
_LRCLIB_BASE = "https://lrclib.net/api"
_GENIUS_BASE = "https://genius.com"
_LYRICS_OVH_BASE = "https://api.lyrics.ovh/v1"
_ITUNES_BASE = "https://itunes.apple.com"
_TIMEOUT = 10  # seconds
_itunes_last_genre: Optional[str] = None  # Set by fetch_cover_art_itunes


@dataclass
class EnrichedMetadata:
    """Result of metadata enrichment."""
    album: Optional[str] = None
    album_artist: Optional[str] = None
    track_number: Optional[str] = None
    total_tracks: Optional[str] = None
    date: Optional[str] = None          # Release year (4 digits)
    full_date: Optional[str] = None     # Full release date (YYYY-MM-DD)
    genre: Optional[str] = None
    cover_data: Optional[bytes] = None  # JPEG bytes (HD album cover)
    cover_mime: str = "image/jpeg"
    lyrics: Optional[str] = None        # Plain or synced lyrics
    synced_lyrics: Optional[str] = None # LRC format synced lyrics
    mb_release_id: Optional[str] = None
    mb_release_group_id: Optional[str] = None
    mb_recording_id: Optional[str] = None
    confidence: float = 0.0             # 0-100 match score


def _request(url: str, timeout: int = _TIMEOUT) -> Optional[bytes]:
    """Make a GET request with proper User-Agent. Returns body bytes or None."""
    req = urllib.request.Request(url)
    req.add_header("User-Agent", _USER_AGENT)
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError:
        # 404s etc. are expected (cover art not available for this release)
        return None
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        print(f"[metadata] Network error: {e}")
        return None


def _normalize(text: str) -> str:
    """Normalize a string for fuzzy comparison."""
    text = text.lower().strip()
    # Remove common suffixes like (Official Video), [Lyrics], (2011 Remaster), etc.
    # The optional (\d{4}\s+)? handles year prefixes like "(2011 Remaster)"
    text = re.sub(
        r'\s*[\(\[]'
        r'(\d{4}\s+)?'
        r'(official\s*(music\s*)?video|lyrics?|audio|visualizer|hd|hq'
        r'|remaster(ed)?|deluxe(\s*edition)?|expanded(\s*edition)?'
        r'|anniversary(\s*edition)?|special\s*edition|bonus\s*track(s)?'
        r'|feat\.?[^\)\]]*|ft\.?[^\)\]]*|live)'
        r'[\)\]]',
        '', text, flags=re.IGNORECASE
    )
    # Remove punctuation
    text = re.sub(r'[^\w\s]', '', text)
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _similarity(a: str, b: str) -> float:
    """Simple word-overlap similarity ratio (0.0 to 1.0)."""
    words_a = set(_normalize(a).split())
    words_b = set(_normalize(b).split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)


def _parse_artist_title_from_video(video_title: str, uploader: str) -> Tuple[str, str]:
    """
    Try to extract artist and track title from a YouTube video title.
    
    Common patterns:
      "Artist - Title (Official Video)"
      "Artist - Title ft. Other (Lyrics)"
      "Title" with uploader as artist
    """
    # Clean common suffixes first
    cleaned = re.sub(
        r'\s*[\(\[](official\s*(music\s*)?video|official\s*audio|lyrics?|lyric\s*video|'
        r'audio|visualizer|hd|hq|remaster(ed)?|live|mv|m/v|clip\s*officiel)[\)\]]',
        '', video_title, flags=re.IGNORECASE
    ).strip()
    
    # Try "Artist - Title" pattern
    separators = [' - ', ' – ', ' — ', ' | ']
    for sep in separators:
        if sep in cleaned:
            parts = cleaned.split(sep, 1)
            artist = parts[0].strip()
            title = parts[1].strip()
            # Remove feat/ft from title (keep in artist if needed)
            title = re.sub(r'\s*(feat\.?|ft\.?)\s*.+$', '', title, flags=re.IGNORECASE).strip()
            if artist and title:
                return artist, title
    
    # Fallback: use uploader as artist, cleaned title as track
    artist = uploader.replace(' - Topic', '').strip() if uploader else ''
    title = re.sub(r'\s*(feat\.?|ft\.?)\s*.+$', '', cleaned, flags=re.IGNORECASE).strip()
    return artist, title


def search_musicbrainz(artist: str, title: str, album: str) -> Optional[Dict]:
    """
    Search MusicBrainz for a recording matching artist + title + album.
    
    The album parameter is REQUIRED — it must come from yt-dlp's metadata
    (i.e. YouTube Music auto-generated tracks). We use it both in the search
    query and to verify the match, so we only return covers we're sure about.
    
    Returns the best matching recording dict with release info, or None.
    """
    # Build the Lucene query — include album for precision
    query_parts = []
    if artist:
        query_parts.append(f'artist:"{artist}"')
    if title:
        query_parts.append(f'recording:"{title}"')
    if album:
        query_parts.append(f'release:"{album}"')
    
    query = " AND ".join(query_parts)
    params = urllib.parse.urlencode({
        "query": query,
        "fmt": "json",
        "limit": "5"
    })
    
    url = f"{_MB_BASE}/recording?{params}"
    print(f"[metadata] Searching MusicBrainz: artist=\"{artist}\", title=\"{title}\", album=\"{album}\"")
    
    data = _request(url)
    if not data:
        return None
    
    try:
        result = json.loads(data)
    except json.JSONDecodeError:
        return None
    
    recordings = result.get("recordings", [])
    if not recordings:
        print("[metadata] No recordings found on MusicBrainz")
        return None
    
    # Score each recording — album match is mandatory
    best_match = None
    best_score = 0.0
    
    for rec in recordings:
        rec_title = rec.get("title", "")
        title_sim = _similarity(title, rec_title)
        
        # Check artist match
        artist_sim = 0.0
        for credit in rec.get("artist-credit", []):
            credit_name = credit.get("name", "") or credit.get("artist", {}).get("name", "")
            sim = _similarity(artist, credit_name)
            artist_sim = max(artist_sim, sim)
        
        # Check album match — must match one of the releases
        album_sim = 0.0
        for release in rec.get("releases", []):
            rel_title = release.get("title", "")
            sim = _similarity(album, rel_title)
            album_sim = max(album_sim, sim)
        
        # Album must match well (>= 0.6) — this is our safety check
        if album_sim < 0.6:
            continue
        
        # Overall score: title + artist + album
        score = (title_sim * 0.35 + artist_sim * 0.35 + album_sim * 0.30) * 100
        
        # Bonus from MusicBrainz's own relevance score
        mb_score = rec.get("score", 0)
        score = score * 0.7 + mb_score * 0.3
        
        if score > best_score:
            best_score = score
            best_match = rec
    
    if best_match and best_score >= 60:
        print(f"[metadata] Best match: \"{best_match.get('title', '')}\" (score: {best_score:.1f})")
        best_match["_match_score"] = best_score
        return best_match
    else:
        print(f"[metadata] No confident match (best score: {best_score:.1f})")
        return None


def _pick_best_release(recording: Dict, album_from_yt: str) -> Optional[Dict]:
    """
    Pick the release from MusicBrainz that matches the album name from YouTube.
    
    Since album_from_yt comes directly from yt-dlp (YouTube Music metadata),
    we strongly prioritize releases whose title matches it.
    """
    releases = recording.get("releases", [])
    if not releases:
        return None
    
    best = None
    best_priority = -100
    
    for release in releases:
        priority = 0
        release_group = release.get("release-group", {})
        primary_type = (release_group.get("primary-type") or "").lower()
        secondary_types = [t.lower() for t in release_group.get("secondary-types", [])]
        
        # Album name match is the primary criterion
        album_sim = _similarity(album_from_yt, release.get("title", ""))
        if album_sim >= 0.8:
            priority += 30  # Strong match
        elif album_sim >= 0.6:
            priority += 15  # Partial match
        else:
            priority -= 20  # Wrong album — heavily penalize
        
        # Prefer albums over singles/compilations
        if primary_type == "album":
            priority += 10
        elif primary_type == "ep":
            priority += 7
        elif primary_type == "single":
            priority += 5
        
        if "compilation" in secondary_types:
            priority -= 5
        
        # Prefer releases with a date and country (more complete data)
        if release.get("date"):
            priority += 2
        if release.get("country"):
            priority += 1
        
        # When priorities are equal, prefer the oldest release (original)
        # over reissues/remasters which have later dates
        release_date = release.get("date", "9999")
        if priority > best_priority or (
            priority == best_priority
            and release_date < (best.get("date", "9999") if best else "9999")
        ):
            best_priority = priority
            best = release
    
    # Only return if the best release actually matches the album
    if best and best_priority >= 10:
        return best
    return None


def _extract_genres(data: dict, skip: set, limit: int = 3) -> List[str]:
    """
    Extract genre names from a MusicBrainz entity response (genres + tags).
    Returns up to `limit` genre names, de-duplicated, title-cased.
    """
    seen = set()
    results = []
    
    # Priority 1: official genres (curated by MusicBrainz editors)
    genres = sorted(data.get("genres", []), key=lambda g: g.get("count", 0), reverse=True)
    for g in genres:
        name = g.get("name", "").strip().lower()
        if name and name not in skip and name not in seen:
            seen.add(name)
            results.append(name.title())
            if len(results) >= limit:
                return results
    
    # Priority 2: community tags
    tags = sorted(data.get("tags", []), key=lambda t: t.get("count", 0), reverse=True)
    for t in tags:
        name = t.get("name", "").strip().lower()
        if name and name not in skip and name not in seen:
            seen.add(name)
            results.append(name.title())
            if len(results) >= limit:
                return results
    
    return results


def fetch_genre_musicbrainz(recording_id: str = "", release_group_id: str = "") -> Optional[str]:
    """
    Fetch genre(s) from MusicBrainz, combining recording-level (track) and
    release-group-level (album) tags.
    
    Recording tags are more specific (e.g. "rock" for a rock track on an
    electronic album), so they take priority.
    
    Returns a semicolon-separated genre string (e.g. "Rock; Alternative Rock")
    or None.
    """
    skip = {"music", "seen live", "favorites", "favourite", "favorite"}
    all_genres = []
    seen = set()
    
    # Priority 1: recording-level tags (per track — most specific)
    if recording_id:
        url = f"{_MB_BASE}/recording/{recording_id}?inc=genres+tags&fmt=json"
        data = _request(url)
        if data:
            try:
                result = json.loads(data)
                for g in _extract_genres(result, skip, limit=2):
                    if g.lower() not in seen:
                        seen.add(g.lower())
                        all_genres.append(g)
            except json.JSONDecodeError:
                pass
    
    # Priority 2: release-group-level tags (album — broader)
    if release_group_id and len(all_genres) < 2:
        url = f"{_MB_BASE}/release-group/{release_group_id}?inc=genres+tags&fmt=json"
        data = _request(url)
        if data:
            try:
                result = json.loads(data)
                for g in _extract_genres(result, skip, limit=2):
                    if g.lower() not in seen:
                        seen.add(g.lower())
                        all_genres.append(g)
            except json.JSONDecodeError:
                pass
    
    if all_genres:
        return "; ".join(all_genres[:3])
    return None


def fetch_cover_art(release_id: str, release_group_id: str = "", 
                    fallback_release_ids: Optional[List[str]] = None) -> Optional[bytes]:
    """
    Fetch high-quality front cover from Cover Art Archive.
    
    Strategy:
    1. Try the release-group endpoint first (aggregates covers from all editions)
    2. Try the specific release
    3. Try other releases of the same album
    
    Returns JPEG/PNG bytes or None.
    """
    urls_to_try = []

    # Priority 1: the specific release matched (most accurate cover)
    urls_to_try.append(f"{_CA_BASE}/release/{release_id}/front-1200")
    urls_to_try.append(f"{_CA_BASE}/release/{release_id}/front")

    # Priority 2: release-group (aggregates all editions of the album)
    if release_group_id:
        urls_to_try.append(f"{_CA_BASE}/release-group/{release_group_id}/front-1200")
        urls_to_try.append(f"{_CA_BASE}/release-group/{release_group_id}/front")

    # Priority 3: other releases of the same album
    for rid in (fallback_release_ids or []):
        if rid != release_id:
            urls_to_try.append(f"{_CA_BASE}/release/{rid}/front-1200")
    
    for url in urls_to_try:
        data = _request(url, timeout=15)
        if data and len(data) > 1000:  # Sanity check: a real image should be > 1KB
            print(f"[metadata] Got HD cover: {len(data)} bytes")
            return data
    
    print("[metadata] No cover art found on Cover Art Archive")
    return None


def fetch_cover_art_itunes(artist: str, album: str, title: str = "") -> Optional[bytes]:
    """
    Fetch album cover from iTunes Search API (fallback when Cover Art Archive has nothing).
    
    iTunes has near-universal coverage and provides artwork up to 1200x1200.
    No API key required.
    
    Strategy:
      1. Search by album (entity=album, term="artist album") — fast, direct.
      2. If no match, search by song (entity=song, term="artist title") — more
         reliable for ambiguous album/artist names, since iTunes can cross-reference
         artist + track name.
    
    Returns JPEG bytes or None.
    Also stores the genre in _itunes_last_genre (module-level) for the caller.
    """
    global _itunes_last_genre
    _itunes_last_genre = None
    best_url = None
    
    # --- Strategy 1: search by album (for cover art) ---
    if album:
        query = f"{artist} {album}"
        params = urllib.parse.urlencode({
            "term": query,
            "media": "music",
            "entity": "album",
            "limit": "5",
            "country": "US"
        })
        url = f"{_ITUNES_BASE}/search?{params}"
        data = _request(url)
        if data:
            try:
                results = json.loads(data).get("results", [])
                best_sim = 0.0
                for item in results:
                    item_album = item.get("collectionName", "")
                    item_artist = item.get("artistName", "")
                    album_sim = _similarity(album, item_album)
                    artist_sim = _similarity(artist, item_artist)
                    combined = album_sim * 0.6 + artist_sim * 0.4
                    if combined > best_sim and album_sim >= 0.5:
                        best_sim = combined
                        best_url = item.get("artworkUrl100", "")
            except (json.JSONDecodeError, KeyError):
                pass
    
    # --- Strategy 2: search by song ---
    # Always run this to get the per-track genre (more accurate than album genre).
    # Also used as cover fallback if Strategy 1 didn't find a cover.
    if title:
        query = f"{artist} {title}"
        params = urllib.parse.urlencode({
            "term": query,
            "media": "music",
            "entity": "song",
            "limit": "10",
            "country": "US"
        })
        url = f"{_ITUNES_BASE}/search?{params}"
        data = _request(url)
        if data:
            try:
                results = json.loads(data).get("results", [])
                best_song_sim = 0.0
                for item in results:
                    item_artist = item.get("artistName", "")
                    item_track = item.get("trackName", "")
                    artist_sim = _similarity(artist, item_artist)
                    track_sim = _similarity(title, item_track)
                    combined = artist_sim * 0.5 + track_sim * 0.5
                    if combined > best_song_sim and artist_sim >= 0.4 and track_sim >= 0.4:
                        # When we know the album, verify the result comes from
                        # the correct album to avoid compilation covers
                        if album:
                            item_album = item.get("collectionName", "")
                            if _similarity(album, item_album) < 0.4:
                                continue
                        best_song_sim = combined
                        # Per-track genre is more accurate than album genre
                        _itunes_last_genre = item.get("primaryGenreName")
                        if not best_url:
                            best_url = item.get("artworkUrl100", "")
            except (json.JSONDecodeError, KeyError):
                pass
    
    if not best_url:
        return None
    
    # iTunes returns 100x100 by default — request 1200x1200
    hd_url = best_url.replace("100x100bb", "1200x1200bb")
    
    cover_data = _request(hd_url, timeout=15)
    if cover_data and len(cover_data) > 1000:
        print(f"[metadata] Got HD cover from iTunes: {len(cover_data)} bytes")
        return cover_data
    
    return None


def _fetch_lyrics_lrclib(artist: str, title: str, album: str = "", duration_sec: int = 0) -> Tuple[Optional[str], Optional[str]]:
    """
    Fetch lyrics from LRCLIB.
    Returns (plain_lyrics, synced_lyrics_lrc) — either or both may be None.
    """
    params = {
        "artist_name": artist,
        "track_name": title,
    }
    if album:
        params["album_name"] = album
    if duration_sec > 0:
        params["duration"] = str(duration_sec)
    
    query = urllib.parse.urlencode(params)
    url = f"{_LRCLIB_BASE}/get?{query}"
    
    data = _request(url)
    if not data:
        # Try without album (broader search)
        if album:
            params.pop("album_name", None)
            query = urllib.parse.urlencode(params)
            url = f"{_LRCLIB_BASE}/get?{query}"
            data = _request(url)
        
        if not data:
            return None, None
    
    try:
        result = json.loads(data)
    except json.JSONDecodeError:
        return None, None
    
    plain = result.get("plainLyrics")
    synced = result.get("syncedLyrics")
    return plain, synced


def _slugify_genius(text: str) -> str:
    """Convert text to a Genius-compatible URL slug."""
    # Remove content in parentheses/brackets
    text = re.sub(r'\s*[\(\[].*?[\)\]]', '', text)
    # Replace & with "and"
    text = text.replace('&', 'and')
    # Remove accents/diacritics — simple ASCII transliteration
    import unicodedata
    text = unicodedata.normalize('NFD', text)
    text = text.encode('ascii', 'ignore').decode('ascii')
    # Keep only alphanumeric and spaces
    text = re.sub(r'[^\w\s-]', '', text)
    # Replace whitespace with hyphens
    text = re.sub(r'\s+', '-', text.strip())
    # Remove consecutive hyphens
    text = re.sub(r'-+', '-', text)
    return text


def _fetch_lyrics_genius(artist: str, title: str) -> Optional[str]:
    """
    Scrape lyrics from Genius by constructing the URL and parsing HTML.
    Similar approach to Tauon Music Box.
    Returns plain lyrics text or None.
    """
    slug_artist = _slugify_genius(artist)
    slug_title = _slugify_genius(title)
    url = f"{_GENIUS_BASE}/{slug_artist}-{slug_title}-lyrics"
    
    req = urllib.request.Request(url)
    req.add_header("User-Agent", _USER_AGENT)
    req.add_header("Accept", "text/html")
    
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            html_bytes = resp.read()
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, TimeoutError):
        return None
    
    try:
        html_text = html_bytes.decode("utf-8", errors="replace")
    except Exception:
        return None
    
    # Extract lyrics from the Genius HTML
    # Genius stores lyrics in <div data-lyrics-container="true">...</div> blocks
    lyrics_parts = []
    pattern = re.compile(r'<div[^>]*data-lyrics-container="true"[^>]*>(.*?)</div>', re.DOTALL)
    matches = pattern.findall(html_text)
    
    if not matches:
        return None
    
    for block in matches:
        # Replace <br/> with newlines
        text = re.sub(r'<br\s*/?>', '\n', block)
        # Remove all remaining HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        # Unescape HTML entities
        text = html.unescape(text)
        lyrics_parts.append(text.strip())
    
    lyrics = '\n'.join(lyrics_parts).strip()
    
    # Skip if it looks like we got an error page or instrumental marker
    if not lyrics or len(lyrics) < 20:
        return None
    
    # Clean up: remove Genius artifacts
    skip_markers = ["Contributors", "Translations", "Embed", "URLCopyEmbedCopy"]
    for marker in skip_markers:
        if lyrics.endswith(marker):
            lyrics = lyrics[:-len(marker)].rstrip()
    
    # Remove trailing numbers (Genius embed IDs)
    lyrics = re.sub(r'\d+$', '', lyrics).rstrip()
    
    return lyrics


def _fetch_lyrics_ovh(artist: str, title: str) -> Optional[str]:
    """
    Fetch lyrics from lyrics.ovh API.
    Returns plain lyrics text or None.
    """
    encoded_artist = urllib.parse.quote(artist, safe='')
    encoded_title = urllib.parse.quote(title, safe='')
    url = f"{_LYRICS_OVH_BASE}/{encoded_artist}/{encoded_title}"
    
    data = _request(url)
    if not data:
        return None
    
    try:
        result = json.loads(data)
    except json.JSONDecodeError:
        return None
    
    lyrics = result.get("lyrics")
    if lyrics and len(lyrics.strip()) > 20:
        return lyrics.strip()
    return None


def fetch_lyrics(artist: str, title: str, album: str = "", duration_sec: int = 0) -> Tuple[Optional[str], Optional[str]]:
    """
    Fetch lyrics from multiple sources with fallback chain:
    1. LRCLIB (provides synced + plain lyrics)
    2. Genius (plain lyrics via scraping)
    3. lyrics.ovh (plain lyrics via API)
    
    Returns (plain_lyrics, synced_lyrics_lrc) — either or both may be None.
    """
    print(f"[metadata] Searching lyrics for: {artist} - {title}")
    
    # Source 1: LRCLIB (best — provides synced lyrics)
    plain, synced = _fetch_lyrics_lrclib(artist, title, album, duration_sec)
    if plain or synced:
        source = "LRCLIB"
        if synced:
            source += " (synced)"
        print(f"[metadata] Lyrics found via {source}")
        return plain, synced
    
    # Source 2: Genius (scraping — large catalog)
    genius_lyrics = _fetch_lyrics_genius(artist, title)
    if genius_lyrics:
        print(f"[metadata] Lyrics found via Genius")
        return genius_lyrics, None
    
    # Source 3: lyrics.ovh (simple API fallback)
    ovh_lyrics = _fetch_lyrics_ovh(artist, title)
    if ovh_lyrics:
        print(f"[metadata] Lyrics found via lyrics.ovh")
        return ovh_lyrics, None
    
    print(f"[metadata] No lyrics found from any source")
    return None, None


def enrich_metadata(video_infos: Dict) -> Optional[EnrichedMetadata]:
    """
    Main entry point: enrich metadata using yt-dlp's extracted info.
    
    HD album cover is ONLY fetched when yt-dlp provides an 'album' field
    (i.e. YouTube Music auto-generated tracks from "- Topic" channels).
    This ensures we never guess the wrong album.
    
    Lyrics are always attempted using the best artist/title we can extract.
    
    Args:
        video_infos: The full info dict from yt-dlp
    
    Returns:
        EnrichedMetadata with whatever could be found, or None on total failure.
    """
    # --- Extract artist and title from yt-dlp metadata ---
    # Priority 1: structured fields (YouTube Music auto-generated tracks)
    yt_artist = None
    try:
        artists_list = video_infos.get('artists')
        if artists_list and len(artists_list) > 0:
            yt_artist = artists_list[0]
    except (KeyError, IndexError, TypeError):
        pass
    
    if not yt_artist:
        # Use 'artist' field if available
        yt_artist = video_infos.get('artist')
    
    yt_track = video_infos.get('track')  # Only set on YT Music auto-generated
    yt_album = video_infos.get('album', '')  # Only set on YT Music auto-generated
    yt_release_year = video_infos.get('release_year')  # Year from yt-dlp (YT Music)
    duration = video_infos.get('duration', 0)
    uploader = video_infos.get('uploader', '')
    video_title = video_infos.get('title', '')
    
    # Priority 2: parse from video title ("Artist - Title (Official Video)")
    if yt_artist and yt_track:
        artist = yt_artist
        title = yt_track
        print(f"[metadata] Using YouTube Music metadata: {artist} - {title} [{yt_album}]")
    else:
        artist, title = _parse_artist_title_from_video(video_title, uploader)
        print(f"[metadata] Parsed from video title: {artist} - {title}")
    
    if not artist or not title:
        print("[metadata] Skipping enrichment: could not determine artist or title")
        return None
    
    enriched = EnrichedMetadata()
    
    # --- Step 1: HD album cover (ONLY if YouTube provides album info) ---
    if yt_album:
        print(f"[metadata] Album from YouTube: \"{yt_album}\" — searching MusicBrainz for HD cover")
        recording = search_musicbrainz(artist, title, yt_album)
        
        if recording:
            enriched.confidence = recording.get("_match_score", 0)
            enriched.mb_recording_id = recording.get("id", "")
            release = _pick_best_release(recording, yt_album)
            
            if release:
                enriched.mb_release_id = release.get("id")
                enriched.album = release.get("title")
                # Store full date for TDRL and year-only for TDRC
                raw_date = release.get("date", "")
                if raw_date and len(raw_date) >= 4 and raw_date[:4].isdigit():
                    enriched.date = raw_date[:4]
                    if len(raw_date) > 4:
                        enriched.full_date = raw_date
                else:
                    enriched.date = raw_date
                
                # Get release-group ID for cover art fallback
                release_group = release.get("release-group", {})
                release_group_id = release_group.get("id", "")
                enriched.mb_release_group_id = release_group_id
                
                # Collect other release IDs as fallback for cover art
                # ONLY include releases from the same release-group
                # (= same album, different editions) to avoid getting
                # covers from compilations or other unrelated albums
                fallback_release_ids = [
                    r.get("id") for r in recording.get("releases", [])
                    if r.get("id") and r.get("id") != enriched.mb_release_id
                    and r.get("release-group", {}).get("id") == release_group_id
                ]
                
                # Get track number from the release media
                for medium in release.get("media", []):
                    track_offset = medium.get("track-offset", 0)
                    track_count = medium.get("track-count", 0)
                    if track_count > 0:
                        enriched.track_number = str(track_offset + 1)
                        enriched.total_tracks = str(track_count)
                
                # Get album artist
                if release_group:
                    for credit in release_group.get("artist-credit", []):
                        enriched.album_artist = credit.get("name", "") or credit.get("artist", {}).get("name", "")
                        break
                
                # Fetch genre: iTunes first (curated), MusicBrainz as fallback
                # (iTunes genre is fetched later, after cover art)
                
                # Fetch HD cover art (release-group → release → fallback releases)
                if enriched.mb_release_id:
                    print(f"[metadata] Fetching HD cover from Cover Art Archive...")
                    cover_data = fetch_cover_art(
                        enriched.mb_release_id,
                        release_group_id=release_group_id,
                        fallback_release_ids=fallback_release_ids
                    )
                    if cover_data:
                        enriched.cover_data = cover_data
                        if cover_data[:4] == b'\x89PNG':
                            enriched.cover_mime = "image/png"
                        else:
                            enriched.cover_mime = "image/jpeg"
                    else:
                        # Fallback: try iTunes Search API
                        print(f"[metadata] Trying iTunes as fallback...")
                        itunes_cover = fetch_cover_art_itunes(artist, yt_album, title)
                        if itunes_cover:
                            enriched.cover_data = itunes_cover
                            enriched.cover_mime = "image/jpeg"

            else:
                print(f"[metadata] No matching release for album \"{yt_album}\"")
                # Fallback: try iTunes even without a MusicBrainz release match
                print(f"[metadata] Trying iTunes as fallback...")
                itunes_cover = fetch_cover_art_itunes(artist, yt_album, title)
                if itunes_cover:
                    enriched.cover_data = itunes_cover
                    enriched.cover_mime = "image/jpeg"
                    enriched.album = yt_album

        else:
            print(f"[metadata] MusicBrainz search returned no match for album \"{yt_album}\"")
            # Fallback: try iTunes directly (doesn't need MusicBrainz)
            print(f"[metadata] Trying iTunes as fallback...")
            itunes_cover = fetch_cover_art_itunes(artist, yt_album, title)
            if itunes_cover:
                enriched.cover_data = itunes_cover
                enriched.cover_mime = "image/jpeg"
                enriched.album = yt_album

    else:
        print(f"[metadata] No album info from YouTube — skipping cover art lookup")
    
    # --- Year: yt-dlp's release_year is authoritative (from YouTube Music) ---
    # It reflects the original release year, while MusicBrainz may return a
    # reissue/remaster date. Use yt-dlp year as override when available.
    if yt_release_year:
        yt_year = str(yt_release_year)
        if enriched.date and enriched.date != yt_year:
            print(f"[metadata] Overriding MusicBrainz year ({enriched.date}) with yt-dlp release year ({yt_year})")
        enriched.date = yt_year

    # --- Step 2: Lyrics (always attempted, independent of album) ---
    album_for_lyrics = yt_album or enriched.album or ""
    plain_lyrics, synced_lyrics = fetch_lyrics(artist, title, album_for_lyrics, duration)
    enriched.lyrics = plain_lyrics
    enriched.synced_lyrics = synced_lyrics
    
    # --- Step 3: Genre ---
    # Priority 1: iTunes per-song genre (curated, standardized classification)
    # Always call iTunes for this specific track — don't reuse _itunes_last_genre
    # from an earlier track in the same playlist session (it would be wrong).
    if not enriched.genre:
        fetch_cover_art_itunes(artist, yt_album or "", title)
        if _itunes_last_genre:
            enriched.genre = _itunes_last_genre
            print(f"[metadata] \u2713 Genre (iTunes): {enriched.genre}")
    
    # Priority 2: MusicBrainz recording + release-group tags (more detailed)
    if not enriched.genre:
        mb_genre = fetch_genre_musicbrainz(
            recording_id=enriched.mb_recording_id or "",
            release_group_id=enriched.mb_release_group_id or ""
        )
        if mb_genre:
            enriched.genre = mb_genre
            print(f"[metadata] \u2713 Genre (MusicBrainz): {enriched.genre}")
    
    # Priority 3: Use the genre from yt-dlp (e.g. SoundCloud uploader-set genre).
    # Exclude generic YouTube categories which are not real music genres.
    if not enriched.genre:
        _YOUTUBE_CATEGORIES = {
            "music", "entertainment", "people & blogs", "education", "gaming",
            "comedy", "film & animation", "science & technology", "news & politics",
            "sports", "howto & style", "travel & events", "autos & vehicles",
            "pets & animals", "nonprofits & activism",
        }
        source_genre = video_infos.get('genre', '').strip()
        if source_genre and source_genre.lower() not in _YOUTUBE_CATEGORIES:
            enriched.genre = source_genre
            print(f"[metadata] Genre (source): {enriched.genre}")

    # Only return if we actually found something useful
    if enriched.cover_data or enriched.lyrics or enriched.synced_lyrics or enriched.genre:
        return enriched
    
    print("[metadata] No enrichment data found")
    return None


def apply_enriched_metadata_mp3(file_path: str, enriched: EnrichedMetadata, 
                                  fallback_cover: Optional[bytes] = None):
    """
    Apply enriched metadata to an MP3 file.
    
    Args:
        file_path: Path to the MP3 file
        enriched: EnrichedMetadata from enrich_metadata()
        fallback_cover: If enriched has no HD cover, use this (YouTube thumbnail)
    """
    from mutagen.id3 import ID3, APIC, USLT, Encoding, TALB, TDRC, TDRL, TRCK, TPE2, TCON
    
    try:
        audio = ID3(file_path)
    except Exception:
        from mutagen.id3 import ID3
        audio = ID3()
    
    # Album
    if enriched.album:
        audio.delall("TALB")
        audio["TALB"] = TALB(encoding=3, text=[enriched.album])
    
    # Album artist
    if enriched.album_artist:
        audio.delall("TPE2")
        audio["TPE2"] = TPE2(encoding=3, text=[enriched.album_artist])
    
    # Track number
    if enriched.track_number:
        track_str = enriched.track_number
        if enriched.total_tracks:
            track_str = f"{enriched.track_number}/{enriched.total_tracks}"
        audio.delall("TRCK")
        audio["TRCK"] = TRCK(encoding=3, text=[track_str])
    
    # Date/Year — TDRC gets the 4-digit year (widely read by players),
    # TDRL gets the full release date (YYYY-MM-DD) when available.
    # FFmpegMetadata may have written a full upload_date (YYYYMMDD) which is
    # often the YouTube upload date, not the actual song release year.
    if enriched.date:
        # Extract only the year from whatever we have
        year = enriched.date[:4] if len(enriched.date) >= 4 else enriched.date
        audio.delall("TDRC")
        audio["TDRC"] = TDRC(encoding=3, text=[year])
    else:
        # No enriched date — clean up FFmpegMetadata's full upload_date to year only
        existing_tdrc = audio.get("TDRC")
        if existing_tdrc:
            existing_text = str(existing_tdrc)
            if len(existing_text) > 4 and existing_text[:4].isdigit():
                audio.delall("TDRC")
                audio["TDRC"] = TDRC(encoding=3, text=[existing_text[:4]])
    
    # Full release date in TDRL (Release time) — ISO 8601 format
    if enriched.full_date:
        audio.delall("TDRL")
        audio["TDRL"] = TDRL(encoding=3, text=[enriched.full_date])
    
    # Genre (replaces the generic "Music" from FFmpegMetadata)
    if enriched.genre:
        audio.delall("TCON")
        audio["TCON"] = TCON(encoding=3, text=[enriched.genre])
    
    # Lyrics — prefer synced (LRC) in USLT for maximum player compatibility
    # Most players (Tauon, foobar2000, etc.) read LRC-formatted text from USLT
    # and display synced lyrics. SYLT is rarely supported.
    lyrics_text = enriched.synced_lyrics or enriched.lyrics
    if lyrics_text:
        audio.delall("USLT")
        audio.delall("SYLT")  # Remove any stale SYLT tags
        audio["USLT::eng"] = USLT(
            encoding=Encoding.UTF8,
            lang="eng",
            desc="",
            text=lyrics_text
        )
    
    # HD Cover art (only replace if we have HD cover from Cover Art Archive)
    cover_to_use = enriched.cover_data or fallback_cover
    if cover_to_use:
        audio.delall("APIC")
        audio["APIC"] = APIC(
            encoding=0,
            mime=enriched.cover_mime if enriched.cover_data else "image/jpeg",
            type=3,  # Front cover
            desc="Cover",
            data=cover_to_use
        )
    
    audio.save(file_path)
    print(f"[metadata] Enriched metadata saved to: {file_path}")


def apply_enriched_metadata_opus(file_path: str, enriched: EnrichedMetadata,
                                  fallback_cover: Optional[bytes] = None):
    """
    Apply enriched metadata to an Opus file using Vorbis comments.
    """
    import base64
    from mutagen import File as MutagenFile
    from mutagen.flac import Picture

    try:
        audio = MutagenFile(file_path)
        if audio is None:
            print(f"Warning: Could not detect audio format for {file_path}")
            return
    except Exception as e:
        print(f"Warning: Could not open Opus file for metadata: {e}")
        return

    if enriched.album:
        audio['album'] = enriched.album

    if enriched.album_artist:
        audio['albumartist'] = enriched.album_artist

    if enriched.track_number:
        audio['tracknumber'] = str(enriched.track_number)
        if enriched.total_tracks:
            audio['tracktotal'] = str(enriched.total_tracks)

    if enriched.date:
        audio['date'] = enriched.date[:4]

    if enriched.full_date:
        audio['originaldate'] = enriched.full_date

    if enriched.genre:
        audio['genre'] = enriched.genre

    # Lyrics
    lyrics_text = enriched.synced_lyrics or enriched.lyrics
    if lyrics_text:
        audio['lyrics'] = lyrics_text

    # Cover art via METADATA_BLOCK_PICTURE
    cover_to_use = enriched.cover_data or fallback_cover
    if cover_to_use:
        pic = Picture()
        pic.type = 3  # Front cover
        pic.mime = enriched.cover_mime if enriched.cover_data else 'image/jpeg'
        pic.desc = 'Cover'
        pic.data = cover_to_use
        audio['metadata_block_picture'] = [base64.b64encode(pic.write()).decode('ascii')]

    audio.save()
    print(f"[metadata] Enriched metadata saved to: {file_path}")
