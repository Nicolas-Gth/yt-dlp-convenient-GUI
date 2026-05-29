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


def _extract_template_info(filepath):
    """Extract metadata needed for folder-structure templates.

    Returns a dict with keys: artist, title, album, tracknumber.
    Missing values fallback to sensible defaults (same as download tab).
    """
    from mutagen.mp4 import MP4
    from mutagen.oggopus import OggOpus
    info = {"artist": "", "title": "", "album": "", "tracknumber": ""}
    audio = _load_audio(filepath)
    if audio is None or audio.tags is None:
        pass
    else:
        tags = audio.tags
        try:
            if isinstance(audio, OggOpus):
                info["artist"] = "; ".join(tags.get('artist', []) or []).strip()
                info["title"] = "; ".join(tags.get('title', []) or []).strip()
                info["album"] = "; ".join(tags.get('album', []) or []).strip()
                info["tracknumber"] = "; ".join(tags.get('tracknumber', []) or []).strip()
            elif isinstance(audio, MP4):
                info["artist"] = (tags.get('\xa9ART', [None])[0] or "").strip()
                info["title"] = (tags.get('\xa9nam', [None])[0] or "").strip()
                info["album"] = (tags.get('\xa9alb', [None])[0] or "").strip()
                trkn = tags.get('trkn')
                if trkn and trkn[0]:
                    info["tracknumber"] = str(trkn[0][0])
            else:  # MP3
                info["artist"] = "; ".join(tags.get('TPE1') or []).strip()
                info["title"] = "; ".join(tags.get('TIT2') or []).strip()
                info["album"] = "; ".join(tags.get('TALB') or []).strip()
                trck = tags.get('TRCK')
                if trck:
                    info["tracknumber"] = str(trck).split('/')[0].strip()
        except Exception:
            pass
    # Fallbacks matching the download tab logic
    if not info["artist"]:
        info["artist"] = "Unknown Artist"
    if not info["album"]:
        info["album"] = "Unknown Album"
    if not info["title"]:
        info["title"] = os.path.splitext(os.path.basename(filepath))[0]
    if not info["tracknumber"]:
        info["tracknumber"] = "0"
    return info


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
            if re.search(r'^\[\d{2}:\d{2}[.:]\d{2}\]', text, re.MULTILINE):
                return 'LRC', 'lrc'
            return 'Txt', 'txt'
    except Exception:
        pass
    return t("table.none"), ''


def _extract_scan_metadata(filepath):
    """Extract all metadata needed by the file scanner in a single file open.
    Returns (artist, title, album, genre, year, tracknumber, lyrics, lyr_type).
    """
    from mutagen.mp4 import MP4
    from mutagen.oggopus import OggOpus

    artist = ""
    title = ""
    album = ""
    genre = ""
    year = ""
    tracknumber = ""
    lyrics = t("table.none")
    lyr_type = ""

    # --- sidecar lyrics (no mutagen needed) ---
    base = os.path.splitext(filepath)[0]
    if os.path.exists(base + '.lrc'):
        lyrics, lyr_type = 'LRC', 'lrc'
    elif os.path.exists(base + '.txt'):
        lyrics, lyr_type = 'Txt', 'txt'

    audio = _load_audio(filepath)
    if audio is not None and audio.tags is not None:
        tags = audio.tags
        try:
            if isinstance(audio, OggOpus):
                artist = "; ".join(tags.get('artist', []) or []).strip()
                title = "; ".join(tags.get('title', []) or []).strip()
                album = "; ".join(tags.get('album', []) or []).strip()
                genre = "; ".join(tags.get('genre', []) or []).strip()
                year = "; ".join(tags.get('date', []) or []).strip()
                tracknumber = "; ".join(tags.get('tracknumber', []) or []).strip()
                # embedded lyrics
                if not lyr_type:
                    val = tags.get('lyrics')
                    text = val[0] if val else None
                    if text:
                        lyrics, lyr_type = ('LRC', 'lrc') if re.search(r'^\[\d{2}:\d{2}[.:]\d{2}\]', text, re.MULTILINE) else ('Txt', 'txt')
            elif isinstance(audio, MP4):
                artist = (tags.get('\xa9ART', [None])[0] or "").strip()
                title = (tags.get('\xa9nam', [None])[0] or "").strip()
                album = (tags.get('\xa9alb', [None])[0] or "").strip()
                genre = (tags.get('\xa9gen', [None])[0] or "").strip()
                year = (tags.get('\xa9day', [None])[0] or "").strip()
                trkn = tags.get('trkn')
                if trkn and trkn[0]:
                    tracknumber = str(trkn[0][0])
                # embedded lyrics
                if not lyr_type:
                    val = tags.get('\xa9lyr')
                    text = val[0] if val else None
                    if text:
                        lyrics, lyr_type = ('LRC', 'lrc') if re.search(r'^\[\d{2}:\d{2}[.:]\d{2}\]', text, re.MULTILINE) else ('Txt', 'txt')
            else:  # MP3
                artist = "; ".join(tags.get('TPE1') or []).strip()
                title = "; ".join(tags.get('TIT2') or []).strip()
                album = "; ".join(tags.get('TALB') or []).strip()
                genre = "; ".join(tags.get('TCON') or []).strip()
                year = (tags.get('TDRC') or [None])[0]
                if year and hasattr(year, 'text'):
                    year = str(year.text[0] if year.text else '')
                elif year:
                    year = str(year)
                else:
                    year = ""
                year = str(year).strip()
                trck = tags.get('TRCK')
                if trck:
                    tracknumber = str(trck).split('/')[0].strip()
                # embedded lyrics
                if not lyr_type:
                    for tag in tags.values():
                        if tag.FrameID == 'USLT':
                            text = str(tag)
                            lyrics, lyr_type = ('LRC', 'lrc') if re.search(r'^\[\d{2}:\d{2}[.:]\d{2}\]', text, re.MULTILINE) else ('Txt', 'txt')
                            break
        except Exception:
            pass

    return artist, title, album, genre, year, tracknumber, lyrics, lyr_type
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


def _embed_artwork(filepath: str, image_data: bytes, mime: str = "image/jpeg", audio_obj=None) -> bool:
    """Embed *image_data* as front cover into *filepath*.

    If *audio_obj* is provided it will be mutated in-place instead of reloading
    the file from disk (prevents overwriting text tags that were just edited).

    Returns True on success, False on failure.
    """
    ext = os.path.splitext(filepath)[1].lower()
    try:
        if ext == '.mp3':
            from mutagen.id3 import APIC
            if audio_obj is not None and audio_obj.tags is not None:
                audio_obj.tags.delall("APIC")
                audio_obj.tags["APIC"] = APIC(
                    encoding=0, mime=mime, type=3, desc="Cover", data=image_data
                )
                return True
            from mutagen.id3 import ID3
            try:
                audio = ID3(filepath)
            except Exception:
                audio = ID3()
            audio.delall("APIC")
            audio["APIC"] = APIC(
                encoding=0, mime=mime, type=3, desc="Cover", data=image_data
            )
            audio.save(filepath)
            return True

        elif ext == '.mp4':
            if audio_obj is not None and audio_obj.tags is not None:
                audio_obj.tags['covr'] = [image_data]
                return True
            from mutagen.mp4 import MP4
            audio = MP4(filepath)
            audio.tags['covr'] = [image_data]
            audio.save()
            return True

        elif ext == '.opus':
            import base64
            from mutagen.flac import Picture
            if audio_obj is not None:
                pic = Picture()
                pic.type = 3
                pic.mime = mime
                pic.desc = "Cover"
                pic.data = image_data
                audio_obj['metadata_block_picture'] = [
                    base64.b64encode(pic.write()).decode('ascii')
                ]
                return True
            from mutagen import File as MutagenFile
            audio = MutagenFile(filepath)
            if audio is None:
                return False
            pic = Picture()
            pic.type = 3
            pic.mime = mime
            pic.desc = "Cover"
            pic.data = image_data
            audio['metadata_block_picture'] = [
                base64.b64encode(pic.write()).decode('ascii')
            ]
            audio.save()
            return True
    except Exception as e:
        print(f"[embed_artwork] Failed to embed cover: {e}")
    return False
