import os
import re
from typing import Optional, List, Tuple

from PySide6.QtGui import QPixmap, QImage

from utils.i18n_utils import t

from .constants import _TAG_LABELS


def _tag_label(key: str) -> str:
    """Return a translated label for *key*, falling back to the raw key."""
    name = _TAG_LABELS.get(key, key)
    return t(name) if name != key else key


def _load_audio(filepath):
    """Return a mutagen audio object for *filepath*, or None."""
    ext = os.path.splitext(filepath)[1].lower()
    try:
        if ext == '.mp3':
            from mutagen.mp3 import MP3
            return MP3(filepath)
        elif ext == '.mp4':
            from mutagen.mp4 import MP4
            return MP4(filepath)
        elif ext == '.opus':
            from mutagen.oggopus import OggOpus
            return OggOpus(filepath)
    except Exception:
        pass
    return None


def _extract_title_artist(filepath):
    """Extract (title, artist) from an audio/video file using mutagen."""
    from mutagen.mp4 import MP4
    from mutagen.oggopus import OggOpus
    audio = _load_audio(filepath)
    if audio is None or audio.tags is None:
        return "", ""
    artist = ""
    title = ""
    tags = audio.tags
    try:
        if isinstance(audio, OggOpus):
            artist = "; ".join(tags.get('artist', []) or [])
            title = "; ".join(tags.get('title', []) or [])
        elif isinstance(audio, MP4):
            artist = tags.get('\xa9ART', [None])[0] or ""
            title = tags.get('\xa9nam', [None])[0] or ""
        else:  # MP3
            artist = "; ".join(tags.get('TPE1') or [])
            title = "; ".join(tags.get('TIT2') or [])
    except Exception:
        pass
    return artist.strip(), title.strip()


def _check_lyrics(filepath):
    """Check for lyrics: sidecar .lrc/.txt files or embedded metadata.
    Returns (display_text, type_key) where type_key is 'lrc'|'txt'|''.
    """
    base = os.path.splitext(filepath)[0]
    if os.path.exists(base + '.lrc'):
        return 'LRC', 'lrc'
    if os.path.exists(base + '.txt'):
        return 'Txt', 'txt'

    audio = _load_audio(filepath)
    if audio is None or audio.tags is None:
        return t("table.none"), ''
    try:
        from mutagen.mp4 import MP4
        from mutagen.oggopus import OggOpus
        text = None
        if isinstance(audio, OggOpus):
            val = audio.tags.get('lyrics')
            text = val[0] if val else None
        elif isinstance(audio, MP4):
            val = audio.tags.get('\xa9lyr')
            text = val[0] if val else None
        else:
            for tag in audio.tags.values():
                if tag.FrameID == 'USLT':
                    text = str(tag)
                    break
        if text:
            # Detect LRC: lines starting with [mm:ss.xx]
            if re.search(r'^\[\d{2}:\d{2}[.:]\d{2}\]', text, re.MULTILINE):
                return 'LRC', 'lrc'
            return 'Txt', 'txt'
    except Exception:
        pass
    return t("table.none"), ''


def _extract_artwork(audio) -> Optional[QPixmap]:
    """Extract embedded cover art from a mutagen audio object."""
    try:
        from mutagen.mp4 import MP4
        from mutagen.oggopus import OggOpus

        if isinstance(audio, OggOpus):
            pics = audio.tags.get('metadata_block_picture', []) if audio.tags else []
            if pics:
                import base64
                data = base64.b64decode(pics[0])
                idx = data.find(b'\xff\xd8')
                if idx < 0:
                    idx = data.find(b'\x89PNG')
                if idx >= 0:
                    qimg = QImage()
                    qimg.loadFromData(data[idx:])
                    return QPixmap.fromImage(qimg)
            return None

        elif isinstance(audio, MP4):
            covr = audio.tags.get('covr', []) if audio.tags else []
            if covr:
                data = covr[0]
                qimg = QImage()
                qimg.loadFromData(data)
                return QPixmap.fromImage(qimg)
            return None

        else:
            if audio.tags is None:
                return None
            for tag in audio.tags.values():
                if tag.FrameID == 'APIC':
                    qimg = QImage()
                    qimg.loadFromData(tag.data)
                    return QPixmap.fromImage(qimg)
    except Exception:
        pass
    return None


def _extract_all_metadata(audio) -> List[Tuple[str, str]]:
    """Return a list of (key, value) pairs for all tags in *audio*."""
    rows = []
    if audio is None or audio.tags is None:
        return rows
    try:
        from mutagen.mp4 import MP4
        from mutagen.oggopus import OggOpus

        if isinstance(audio, OggOpus):
            for key, values in (audio.tags or {}).items():
                if key.startswith('metadata_block_picture') or key in ('cover', 'lyrics'):
                    continue
                rows.append((key, "; ".join(values)))
            rows.sort(key=lambda r: r[0])
        elif isinstance(audio, MP4):
            for key in sorted(audio.tags.keys()):
                if key in ('covr', '\xa9lyr'):
                    continue
                rows.append((key, "; ".join(str(v) for v in (audio.tags[key] or []))))
        else:  # MP3 ID3
            for tag in sorted(audio.tags.values(), key=lambda t: t.FrameID):
                if tag.FrameID in ('APIC', 'USLT'):
                    continue
                rows.append((tag.FrameID, "; ".join(str(v) for v in tag.text) if hasattr(tag, 'text') else str(tag)))
    except Exception:
        pass
    return rows


def _extract_lyrics_text(audio) -> Optional[str]:
    """Return the full embedded lyrics text, or None."""
    if audio is None or audio.tags is None:
        return None
    try:
        from mutagen.mp4 import MP4
        from mutagen.oggopus import OggOpus
        if isinstance(audio, OggOpus):
            val = audio.tags.get('lyrics')
            return val[0] if val else None
        elif isinstance(audio, MP4):
            val = audio.tags.get('\xa9lyr')
            return val[0] if val else None
        else:
            for tag in audio.tags.values():
                if tag.FrameID == 'USLT':
                    return str(tag)
    except Exception:
        pass
    return None
