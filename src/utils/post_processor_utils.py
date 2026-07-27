"""
Custom yt-dlp post-processor for handling metadata, file renaming, and album covers.
"""
import json
import os
import re
import subprocess
import sys
import unicodedata
from typing import Optional, Dict, Callable

import yt_dlp
from mutagen.id3 import ID3, APIC, TDRC, TCON
from mutagen.mp3 import MP3


def _no_window_kwargs():
    """Return subprocess kwargs that prevent console windows on Windows."""
    if sys.platform != 'win32':
        return {}
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return {'startupinfo': si, 'creationflags': subprocess.CREATE_NO_WINDOW}
from mutagen.easyid3 import EasyID3
from mutagen.oggopus import OggOpus
from mutagen.flac import Picture

from models import DownloadConfig
from utils import crop_album_cover, enrich_metadata, apply_enriched_metadata_mp3, apply_enriched_metadata_opus


def _build_flac_picture(image_data: bytes, mime: str = 'image/jpeg') -> Picture:
    """Build a FLAC Picture block for embedding in Ogg containers."""
    pic = Picture()
    pic.type = 3  # Front cover
    pic.mime = mime
    pic.desc = 'Cover'
    pic.data = image_data
    return pic


class CustomPostProcessor(yt_dlp.postprocessor.PostProcessor):
    """Custom post-processor for handling metadata and file organization."""

    # Patterns stripped from video titles for clean filenames/tags
    _TITLE_NOISE_RE = re.compile(
        r'\s*[\(\[]'
        r'(official\s*(music\s*)?video|official\s*audio|official\s*lyric\s*video'
        r'|lyrics?|lyric\s*video|audio|visualizer|hd|hq|4k'
        r'|clip\s*officiel|video\s*oficial|videoclip'
        r'|mv|m/v|music\s*video|live)'
        r'[\)\]]',
        re.IGNORECASE
    )

    @staticmethod
    def _clean_title(title: str) -> str:
        """Strip noise like (Official Video), [Lyrics], etc. from a video title."""
        cleaned = CustomPostProcessor._TITLE_NOISE_RE.sub('', title).strip()
        # Also strip trailing whitespace/dashes left over
        cleaned = re.sub(r'[\s\-]+$', '', cleaned)
        return cleaned if cleaned else title

    def __init__(self, download_config: DownloadConfig, normalize_callback: Optional[Callable] = None):
        super().__init__()
        self.config = download_config
        self.normalize_callback = normalize_callback

    def run(self, video_infos):
        """Process downloaded file: add metadata, rename, and set album cover."""
        file_format = self.config.file_format
        # Use yt-dlp's actual filepath — the title may contain characters
        # (/ ? : ~ etc.) that yt-dlp sanitises when writing to disk,
        # so reconstructing the path from the raw title would fail.
        file_path = video_infos.get('filepath',
                                    f"{self.config.output_directory}/{video_infos['title']}.{file_format}")

        # Check if the file actually exists
        if not os.path.exists(file_path):
            print(f"Warning: File {file_path} not found. Conversion may have failed.")
            return [], video_infos

        # For opus: yt-dlp downloads opus audio inside a .webm container.
        # We remux to a proper .opus (Ogg) file here using the 'ogg' muxer,
        # because the 'opus' muxer is broken in some ffmpeg builds.
        if file_format == "opus" and not file_path.endswith('.opus'):
            file_path = self._remux_to_opus(file_path, video_infos)
            if file_path is None:
                return [], video_infos

        # For mp3: convert with bitrate capping (source bitrate as ceiling).
        # We handle conversion here instead of FFmpegExtractAudio so we can
        # probe the source and avoid inflating files above their original bitrate.
        if file_format == "mp3" and not file_path.endswith('.mp3'):
            file_path = self._convert_to_mp3(file_path, video_infos)
            if file_path is None:
                return [], video_infos

        # --- Collect all info for this track's summary line ---
        track_info = {
            'type': 'track_summary',
            'volume': None,
            'metadata_found': False,
            'lyrics_found': False,
            'lyrics_type': 'No',
            'cover_found': False,
            'duration': video_infos.get('duration', 0) or 0,
        }

        # Determine artist name
        try:
            artist_name = video_infos.get('artists', [video_infos.get('uploader', '').replace(" - Topic", "")])[0]
        except (KeyError, IndexError):
            artist_name = video_infos.get('uploader', '').replace(" - Topic", "")

        # Determine display name: "Artist - Track" for music, "Video Title" otherwise
        track_name = video_infos.get('track')  # Only set on YT Music
        if track_name and artist_name:
            track_info['display_name'] = f"{artist_name} - {track_name}"
        else:
            track_info['display_name'] = video_infos.get('title', 'Unknown')

        track_info['artist'] = artist_name or ''
        track_info['title'] = track_name or video_infos.get('title', 'Unknown')

        # Analyze loudness after normalization if enabled
        if self.config.normalize_volume:
            track_info['volume'] = self._analyze_loudness(file_path)

        # Add metadata to the file
        if file_format == "mp3":
            self._add_mp3_metadata(file_path, video_infos, artist_name)
        elif file_format == "opus":
            self._add_opus_metadata(file_path, video_infos, artist_name)
        elif file_format == "mp4":
            self._add_mp4_metadata(file_path, video_infos, artist_name)

        # Rename and sanitize the file name
        new_file_path = self._sanitize_and_rename_file(file_path, video_infos, artist_name, file_format)

        # Add album cover for audio/video files
        if file_format == "mp3" and os.path.exists(new_file_path):
            self._add_album_cover(new_file_path, video_infos, track_info)
        elif file_format == "opus" and os.path.exists(new_file_path):
            self._add_opus_album_cover(new_file_path, video_infos, track_info)
        elif file_format == "mp4" and os.path.exists(new_file_path):
            self._add_mp4_album_cover(new_file_path, video_infos, track_info)

        # Send combined summary line to UI
        if self.normalize_callback:
            self.normalize_callback(track_info)

        return [], video_infos

    # ------------------------------------------------------------------
    # Opus remux (WebM → Ogg Opus)
    # ------------------------------------------------------------------

    def _remux_to_opus(self, file_path: str, video_infos: Dict) -> str:
        """Remux a WebM file containing opus audio to a proper .opus (Ogg) file.

        Uses the 'ogg' muxer instead of the 'opus' muxer to avoid the
        "Function not implemented" error on some ffmpeg builds.
        Returns the new file path, or None on failure.
        """
        from config import get_ffmpeg_path
        ffmpeg_dir = get_ffmpeg_path()
        if ffmpeg_dir:
            ffmpeg_bin = os.path.join(ffmpeg_dir, 'ffmpeg')
            if not os.path.exists(ffmpeg_bin):
                ffmpeg_bin = 'ffmpeg'
        else:
            ffmpeg_bin = 'ffmpeg'

        opus_path = os.path.splitext(file_path)[0] + '.opus'

        # Probe source bitrate to avoid useless re-encoding
        source_bitrate = self._probe_audio_bitrate(file_path, ffmpeg_dir)

        # Determine if we need to re-encode
        needs_reencode = False
        target_bitrate = None

        if self.config.bitrate and self.config.bitrate.lower() != 'best':
            target_bitrate = int(self.config.bitrate)
            # Only re-encode if the source bitrate is above the target (cap)
            if source_bitrate and source_bitrate > target_bitrate:
                needs_reencode = True

        # Build ffmpeg command
        cmd = [ffmpeg_bin, '-y', '-i', file_path]

        if self.config.normalize_volume:
            target = self.config.normalize_target
            # Normalization always requires re-encoding
            bitrate_args = []
            if target_bitrate and needs_reencode:
                bitrate_args = ['-b:a', f'{target_bitrate}k']
            elif source_bitrate:
                # Preserve original bitrate during normalization
                bitrate_args = ['-b:a', f'{source_bitrate}k']
            cmd += ['-c:a', 'libopus'] + bitrate_args + ['-af', f'loudnorm=I={target}:TP=-1.5:LRA=11']
        elif needs_reencode:
            cmd += ['-c:a', 'libopus', '-b:a', f'{target_bitrate}k']
        else:
            cmd += ['-c:a', 'copy']

        cmd += ['-f', 'ogg', opus_path]

        print(f"[opus remux] source={source_bitrate}kbps, target={target_bitrate or 'best'}, reencode={needs_reencode}, cmd: {' '.join(cmd)}")

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, **_no_window_kwargs())
            if result.returncode != 0:
                print(f"Warning: Opus remux failed: {result.stderr.strip()}")
                return None
            # Remove the original webm file
            try:
                os.remove(file_path)
            except OSError:
                pass
            # Update video_infos so downstream code uses the new path
            video_infos['filepath'] = opus_path
            return opus_path
        except Exception as e:
            print(f"Warning: Opus remux failed: {e}")
            return None

    # ------------------------------------------------------------------
    # MP3 conversion (any audio → MP3 with bitrate capping)
    # ------------------------------------------------------------------

    def _convert_to_mp3(self, file_path: str, video_infos: Dict) -> str:
        """Convert an audio file to MP3 with bitrate capping.

        Probes the source bitrate and uses it as a ceiling: if the user
        selected a target bitrate higher than the source, we encode at the
        source bitrate to avoid inflation.  "Best" uses LAME VBR quality 0.
        Returns the new file path, or None on failure.
        """
        from config import get_ffmpeg_path
        ffmpeg_dir = get_ffmpeg_path()
        if ffmpeg_dir:
            ffmpeg_bin = os.path.join(ffmpeg_dir, 'ffmpeg')
            if not os.path.exists(ffmpeg_bin):
                ffmpeg_bin = 'ffmpeg'
        else:
            ffmpeg_bin = 'ffmpeg'

        mp3_path = os.path.splitext(file_path)[0] + '.mp3'

        # Probe source bitrate to avoid inflating beyond the original
        source_bitrate = self._probe_audio_bitrate(file_path, ffmpeg_dir)

        # Determine effective bitrate (cap logic)
        effective_bitrate = None
        if self.config.bitrate and self.config.bitrate.lower() != 'best':
            target_bitrate = int(self.config.bitrate)
            if source_bitrate and source_bitrate < target_bitrate:
                effective_bitrate = source_bitrate
            else:
                effective_bitrate = target_bitrate

        # Build ffmpeg command
        cmd = [ffmpeg_bin, '-y', '-i', file_path]

        if self.config.normalize_volume:
            target = self.config.normalize_target
            if effective_bitrate:
                bitrate_args = ['-b:a', f'{effective_bitrate}k']
            elif source_bitrate:
                bitrate_args = ['-b:a', f'{source_bitrate}k']
            else:
                bitrate_args = ['-q:a', '0']
            cmd += ['-c:a', 'libmp3lame'] + bitrate_args + ['-af', f'loudnorm=I={target}:TP=-1.5:LRA=11']
        elif effective_bitrate:
            cmd += ['-c:a', 'libmp3lame', '-b:a', f'{effective_bitrate}k']
        else:
            # "Best" — LAME VBR highest quality
            cmd += ['-c:a', 'libmp3lame', '-q:a', '0']

        cmd += [mp3_path]

        print(f"[mp3 convert] source={source_bitrate}kbps, target={self.config.bitrate}, effective={effective_bitrate}, cmd: {' '.join(cmd)}")

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, **_no_window_kwargs())
            if result.returncode != 0:
                print(f"Warning: MP3 conversion failed: {result.stderr.strip()}")
                return None
            # Remove the original file
            try:
                os.remove(file_path)
            except OSError:
                pass
            # Update video_infos so downstream code uses the new path
            video_infos['filepath'] = mp3_path
            return mp3_path
        except Exception as e:
            print(f"Warning: MP3 conversion failed: {e}")
            return None

    @staticmethod
    def _probe_audio_bitrate(file_path: str, ffmpeg_dir: str = None) -> int:
        """Probe the audio bitrate of a file in kbps using ffprobe.
        Returns the bitrate as int (kbps), or None if detection fails.

        Tries stream-level bit_rate first, then falls back to container-level
        bit_rate (useful for WebM/opus where the stream field is often "N/A").
        """
        if ffmpeg_dir:
            ffprobe_bin = os.path.join(ffmpeg_dir, 'ffprobe')
            if not os.path.exists(ffprobe_bin):
                ffprobe_bin = 'ffprobe'
        else:
            ffprobe_bin = 'ffprobe'

        # Try stream-level bitrate first
        try:
            result = subprocess.run(
                [ffprobe_bin, '-v', 'quiet', '-select_streams', 'a:0',
                 '-show_entries', 'stream=bit_rate',
                 '-of', 'default=noprint_wrappers=1:nokey=1', file_path],
                capture_output=True, text=True, timeout=10,
                **_no_window_kwargs(),
            )
            if result.returncode == 0 and result.stdout.strip():
                val = result.stdout.strip()
                if val != 'N/A':
                    bps = int(val)
                    return bps // 1000  # Convert to kbps
        except Exception:
            pass

        # Fallback: container-level bitrate (works for WebM/opus)
        try:
            result = subprocess.run(
                [ffprobe_bin, '-v', 'quiet',
                 '-show_entries', 'format=bit_rate',
                 '-of', 'default=noprint_wrappers=1:nokey=1', file_path],
                capture_output=True, text=True, timeout=10,
                **_no_window_kwargs(),
            )
            if result.returncode == 0 and result.stdout.strip():
                val = result.stdout.strip()
                if val != 'N/A':
                    bps = int(val)
                    return bps // 1000
        except Exception:
            pass

        return None

    # ------------------------------------------------------------------
    # MP4 metadata
    # ------------------------------------------------------------------

    def _add_mp4_metadata(self, file_path: str, video_infos: Dict, artist_name: str):
        """Add metadata to MP4 file using mutagen."""
        try:
            from mutagen.mp4 import MP4
            audio = MP4(file_path)

            audio.tags['\xa9ART'] = [artist_name]

            track_name = video_infos.get('track')
            if not track_name:
                track_name = self._clean_title(video_infos.get('title', ''))
            audio.tags['\xa9nam'] = [track_name]

            album_name = video_infos.get('album')
            if album_name:
                audio.tags['\xa9alb'] = [album_name]

            release_year = video_infos.get('release_year')
            if release_year:
                audio.tags['\xa9day'] = [str(release_year)]
            elif video_infos.get('upload_date'):
                audio.tags['\xa9day'] = [video_infos['upload_date'][:4]]

            audio.save()
        except Exception as e:
            print(f"Warning: Could not add metadata to MP4 file: {e}")

    # ------------------------------------------------------------------
    # MP3 metadata
    # ------------------------------------------------------------------

    def _add_mp3_metadata(self, file_path: str, video_infos: Dict, artist_name: str):
        """Add metadata to MP3 file."""
        try:
            metadatas = MP3(file_path, ID3=EasyID3)
            metadatas['artist'] = artist_name

            # Use clean track name as title tag
            track_name = video_infos.get('track')  # YT Music: already clean
            if not track_name:
                track_name = self._clean_title(video_infos.get('title', ''))
            metadatas['title'] = track_name

            album_name = video_infos.get('album')
            if album_name:
                metadatas['album'] = album_name

            metadatas.save()
        except Exception as e:
            print(f"Warning: Could not add metadata to MP3 file: {e}")

        # Fix year tag: FFmpegMetadata writes upload_date (YYYYMMDD) into TDRC.
        # We want only the 4-digit year, and prefer yt-dlp's release_year
        # (original release) over the upload date.
        try:
            audio = ID3(file_path)
            release_year = video_infos.get('release_year')
            if release_year:
                audio.delall("TDRC")
                audio["TDRC"] = TDRC(encoding=3, text=[str(release_year)])
            else:
                existing_tdrc = audio.get("TDRC")
                if existing_tdrc:
                    existing_text = str(existing_tdrc)
                    if len(existing_text) > 4 and existing_text[:4].isdigit():
                        audio.delall("TDRC")
                        audio["TDRC"] = TDRC(encoding=3, text=[existing_text[:4]])
            audio.save()
        except Exception as e:
            print(f"Warning: Could not fix year tag: {e}")

        # Remove generic YouTube categories ("Music", "Entertainment", etc.)
        # but keep useful genre tags from other sources (e.g. SoundCloud).
        _GENERIC_CATEGORIES = {
            "music", "entertainment", "people & blogs", "education", "gaming",
            "comedy", "film & animation", "science & technology",
            "news & politics", "sports", "howto & style",
            "travel & events", "autos & vehicles", "pets & animals",
            "nonprofits & activism",
        }
        try:
            audio = ID3(file_path)
            tcon = audio.get("TCON")
            if tcon:
                genre_text = str(tcon).strip()
                if genre_text.lower() in _GENERIC_CATEGORIES:
                    audio.delall("TCON")
                    audio.save()
        except Exception as e:
            print(f"Warning: Could not clean genre tag: {e}")

    # ------------------------------------------------------------------
    # Opus metadata
    # ------------------------------------------------------------------

    def _add_opus_metadata(self, file_path: str, video_infos: Dict, artist_name: str):
        """Add metadata to Opus file using Vorbis comments."""
        try:
            from mutagen import File as MutagenFile
            audio = MutagenFile(file_path)
            if audio is None:
                print(f"Warning: Could not detect audio format for {file_path}")
                return
            audio['artist'] = artist_name

            track_name = video_infos.get('track')
            if not track_name:
                track_name = self._clean_title(video_infos.get('title', ''))
            audio['title'] = track_name

            album_name = video_infos.get('album')
            if album_name:
                audio['album'] = album_name

            # Year/date
            release_year = video_infos.get('release_year')
            if release_year:
                audio['date'] = str(release_year)
            elif video_infos.get('upload_date'):
                audio['date'] = video_infos['upload_date'][:4]

            audio.save()
        except Exception as e:
            print(f"Warning: Could not add metadata to Opus file: {e}")

    # ------------------------------------------------------------------
    # Loudness analysis
    # ------------------------------------------------------------------

    def _analyze_loudness(self, file_path: str) -> dict:
        """Analyze the file loudness using ffmpeg. Returns loudness info dict or None."""
        try:
            from config import get_ffmpeg_path
            ffmpeg_dir = get_ffmpeg_path()
            if ffmpeg_dir:
                ffmpeg_bin = os.path.join(ffmpeg_dir, 'ffmpeg')
                if not os.path.exists(ffmpeg_bin):
                    ffmpeg_bin = 'ffmpeg'
            else:
                ffmpeg_bin = 'ffmpeg'

            result = subprocess.run(
                [ffmpeg_bin, '-i', file_path, '-af', 'loudnorm=print_format=json', '-f', 'null', '-'],
                capture_output=True, text=True, timeout=60,
                **_no_window_kwargs(),
            )

            # Parse the loudnorm JSON output from stderr
            stderr = result.stderr
            json_start = stderr.rfind('{')
            json_end = stderr.rfind('}') + 1

            if json_start != -1 and json_end > json_start:
                loudness_data = json.loads(stderr[json_start:json_end])
                input_i = float(loudness_data.get('input_i', 0))
                target = self.config.normalize_target
                print(f"[normalize] Measured at {input_i:.1f} LUFS (target: {target:.1f} LUFS)")
                return {'measured': input_i, 'target': target}
        except Exception as e:
            print(f"Warning: Could not analyze loudness: {e}")
        return None

    _TEMPLATE_VAR_RE = re.compile(r'\{(\w+)\}')

    _DATE_TOKENS = ('Y', 'y', 'm', 'd', 'H', 'M', 'S', 'B', 'b')

    @classmethod
    def _resolve_template(cls, template: str, video_infos: dict, file_format: str) -> str:
        """Resolve a filename template using video metadata.

        Content variables:   {title}  {artist}  {album}  {tracknumber}
        Date/time tokens:    {Y} {y} {m} {d} {B} {b} {H} {M} {S}
        """
        import datetime

        # Precompute date/time token values from epoch
        epoch = video_infos.get('epoch')
        dt = None
        if epoch:
            try:
                dt = datetime.datetime.fromtimestamp(epoch)
            except (OSError, ValueError):
                dt = None

        tokens = {t: '' for t in cls._DATE_TOKENS}
        if dt:
            for t in cls._DATE_TOKENS:
                try:
                    tokens[t] = dt.strftime(f'%{t}')
                except (ValueError, OSError):
                    tokens[t] = ''
        else:
            # Fallback: extract from upload_date (YYYYMMDD)
            upload_date = video_infos.get('upload_date', '')
            if len(upload_date) == 8:
                tokens['Y'] = upload_date[:4]
                tokens['y'] = upload_date[2:4]
                tokens['m'] = upload_date[4:6]
                tokens['d'] = upload_date[6:8]

        # Content variables
        clean_title = video_infos.get('track') or cls._clean_title(
            video_infos.get('title', ''))
        artist = video_infos.get('artists', [video_infos.get('uploader', '')])[0] if video_infos.get('artists') else video_infos.get('uploader', '')
        artist = artist.replace(" - Topic", "")
        album = video_infos.get('album') or 'Unknown Album'
        tracknumber = str(video_infos.get('playlist_index') or '1')

        def replace_var(m):
            name = m.group(1)
            if name in tokens:
                return tokens[name].replace('/', '_').replace('\\', '_')
            if name == 'title':
                return clean_title.replace('/', '_').replace('\\', '_')
            if name == 'artist':
                return artist.replace('/', '_').replace('\\', '_')
            if name == 'album':
                return album.replace('/', '_').replace('\\', '_')
            if name == 'tracknumber':
                return tracknumber.replace('/', '_').replace('\\', '_')
            return m.group(0)

        return cls._TEMPLATE_VAR_RE.sub(replace_var, template)

    # ------------------------------------------------------------------
    # File renaming
    # ------------------------------------------------------------------

    _FILENAME_ILLEGAL_RE = re.compile(r'[!?:#%&{}<>|*$@~/\\]')

    @staticmethod
    def _sanitize_path_component(component: str) -> str:
        """Strip characters that are illegal in file/directory names."""
        sanitized = CustomPostProcessor._FILENAME_ILLEGAL_RE.sub('', component)
        s = sanitized.strip()
        if not s or s in ('.', '..'):
            return '_'
        while len(s.encode('utf-8')) > 200:
            s = s[:-1]
        return s

    def _sanitize_and_rename_file(self, file_path: str, video_infos: Dict, artist_name: str, file_format: str) -> str:
        """Sanitize filename and rename the file."""
        if self.config.output_template:
            raw_name = self._resolve_template(self.config.output_template, video_infos, file_format)
        else:
            title = video_infos.get('track') or self._clean_title(video_infos.get('title', ''))
            raw_name = f"{artist_name} - {title}"

        # Split on '/' to handle subdirectories, sanitize each component
        parts = raw_name.split('/')
        sanitized_parts = [self._sanitize_path_component(p) for p in parts]
        sanitized_parts = [p for p in sanitized_parts if p]
        if not sanitized_parts:
            sanitized_parts = [f"{artist_name} - {title}"]

        relative_path = '/'.join(sanitized_parts)
        new_file_path = os.path.join(self.config.output_directory, f"{relative_path}.{file_format}")
        new_file_path = unicodedata.normalize('NFC', new_file_path)

        # Create intermediate directories if needed
        new_dir = os.path.dirname(new_file_path)
        if new_dir:
            try:
                os.makedirs(new_dir, exist_ok=True)
            except OSError as e:
                print(f"Warning: Could not create directory {new_dir}: {e}")

        try:
            os.rename(file_path, new_file_path)
            return new_file_path
        except Exception as e:
            print(f"Warning: Could not rename file: {e}")
            return file_path

    # ------------------------------------------------------------------
    # Album cover
    # ------------------------------------------------------------------

    def _add_album_cover(self, file_path: str, video_infos: Dict, track_info: dict = None):
        """Add album cover to MP3 file, with optional metadata enrichment."""
        thumbnail_url = video_infos.get('thumbnail', '')

        # Prepare the YouTube thumbnail as fallback cover
        fallback_cover = None
        if thumbnail_url:
            try:
                fallback_cover = crop_album_cover(thumbnail_url)
            except Exception as e:
                print(f"Warning: Could not crop YouTube thumbnail: {e}")

        # Try metadata enrichment if enabled
        if self.config.enrich_metadata:
            enriched = enrich_metadata(video_infos)

            if enriched:
                if enriched.cover_data:
                    print(f"[metadata] HD album cover")
                if enriched.synced_lyrics:
                    print(f"[metadata] Synced lyrics (LRC) embedded")
                elif enriched.lyrics:
                    print(f"[metadata] Lyrics embedded")

                if not enriched.cover_data and fallback_cover:
                    print(f"[metadata] No HD cover found, using YouTube thumbnail")

                # Update track_info for the combined summary
                if track_info is not None:
                    track_info['cover_found'] = bool(enriched.cover_data)
                    track_info['lyrics_found'] = bool(enriched.synced_lyrics or enriched.lyrics)
                    if enriched.synced_lyrics:
                        track_info['lyrics_type'] = 'LRC'
                    elif enriched.lyrics:
                        track_info['lyrics_type'] = 'Txt'
                    track_info['metadata_found'] = bool(
                        enriched.cover_data or enriched.lyrics or enriched.synced_lyrics or enriched.album
                    )

                apply_enriched_metadata_mp3(file_path, enriched, fallback_cover)
                return

        # Fallback: just embed the YouTube thumbnail
        if fallback_cover:
            try:
                audio = ID3(file_path)
                audio['APIC'] = APIC(
                    encoding=0,
                    mime='image/jpeg',
                    type=3,
                    desc=u'Cover',
                    data=fallback_cover
                )
                audio.save()
            except Exception as e:
                print(f"Warning: Could not add album cover to MP3: {e}")

    def _add_opus_album_cover(self, file_path: str, video_infos: Dict, track_info: dict = None):
        """Add album cover to Opus file, with optional metadata enrichment."""
        import base64
        thumbnail_url = video_infos.get('thumbnail', '')

        fallback_cover = None
        if thumbnail_url:
            try:
                fallback_cover = crop_album_cover(thumbnail_url)
            except Exception as e:
                print(f"Warning: Could not crop YouTube thumbnail: {e}")

        if self.config.enrich_metadata:
            enriched = enrich_metadata(video_infos)

            if enriched:
                if enriched.cover_data:
                    print(f"[metadata] HD album cover")
                if enriched.synced_lyrics:
                    print(f"[metadata] Synced lyrics (LRC) embedded")
                elif enriched.lyrics:
                    print(f"[metadata] Lyrics embedded")

                if not enriched.cover_data and fallback_cover:
                    print(f"[metadata] No HD cover found, using YouTube thumbnail")

                if track_info is not None:
                    track_info['cover_found'] = bool(enriched.cover_data)
                    track_info['lyrics_found'] = bool(enriched.synced_lyrics or enriched.lyrics)
                    if enriched.synced_lyrics:
                        track_info['lyrics_type'] = 'LRC'
                    elif enriched.lyrics:
                        track_info['lyrics_type'] = 'TXT'
                    track_info['metadata_found'] = bool(
                        enriched.cover_data or enriched.lyrics or enriched.synced_lyrics or enriched.album
                    )

                apply_enriched_metadata_opus(file_path, enriched, fallback_cover)
                return

        # Fallback: just embed the YouTube thumbnail
        if fallback_cover:
            try:
                from mutagen import File as MutagenFile
                audio = MutagenFile(file_path)
                if audio is not None:
                    picture = _build_flac_picture(fallback_cover, 'image/jpeg')
                    audio['metadata_block_picture'] = [base64.b64encode(picture.write()).decode('ascii')]
                    audio.save()
            except Exception as e:
                print(f"Warning: Could not add album cover to Opus: {e}")

    def _add_mp4_album_cover(self, file_path: str, video_infos: Dict, track_info: dict = None):
        """Add album cover to MP4 file using mutagen.

        Uses the YouTube thumbnail as fallback.  HD cover from enrichment
        is also supported when the user enables metadata enrichment.
        """
        thumbnail_url = video_infos.get('thumbnail', '')

        # For MP4 (video), keep the original 16:9 thumbnail ratio
        fallback_cover = None
        if thumbnail_url:
            try:
                fallback_cover = crop_album_cover(thumbnail_url, force_square=False)
            except Exception as e:
                print(f"Warning: Could not crop YouTube thumbnail: {e}")

        if self.config.enrich_metadata:
            enriched = enrich_metadata(video_infos)

            if enriched:
                if enriched.cover_data:
                    print(f"[metadata] HD album cover")
                if enriched.synced_lyrics:
                    print(f"[metadata] Synced lyrics (LRC) embedded")
                elif enriched.lyrics:
                    print(f"[metadata] Lyrics embedded")

                if not enriched.cover_data and fallback_cover:
                    print(f"[metadata] No HD cover found, using YouTube thumbnail")

                if track_info is not None:
                    track_info['cover_found'] = bool(enriched.cover_data)
                    track_info['lyrics_found'] = bool(enriched.synced_lyrics or enriched.lyrics)
                    if enriched.synced_lyrics:
                        track_info['lyrics_type'] = 'LRC'
                    elif enriched.lyrics:
                        track_info['lyrics_type'] = 'Txt'
                    track_info['metadata_found'] = bool(
                        enriched.cover_data or enriched.lyrics or enriched.synced_lyrics or enriched.album
                    )

                cover_to_use = enriched.cover_data or fallback_cover
                if cover_to_use:
                    try:
                        from mutagen.mp4 import MP4
                        audio = MP4(file_path)
                        audio.tags['covr'] = [cover_to_use]
                        audio.save()
                    except Exception as e:
                        print(f"Warning: Could not add album cover to MP4: {e}")
                return

        # Fallback: embed the YouTube thumbnail
        if fallback_cover:
            try:
                from mutagen.mp4 import MP4
                audio = MP4(file_path)
                audio.tags['covr'] = [fallback_cover]
                audio.save()
            except Exception as e:
                print(f"Warning: Could not add album cover to MP4: {e}")
