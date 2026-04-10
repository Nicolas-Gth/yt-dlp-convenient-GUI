"""
Custom yt-dlp post-processor for handling metadata, file renaming, and album covers.
"""
import json
import os
import re
import subprocess
from typing import Optional, Dict, Callable

import yt_dlp
from mutagen.id3 import ID3, APIC, TDRC, TCON
from mutagen.mp3 import MP3
from mutagen.easyid3 import EasyID3

from models import DownloadConfig
from utils import crop_album_cover, enrich_metadata, apply_enriched_metadata_mp3


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

        # --- Collect all info for this track's summary line ---
        track_info = {
            'type': 'track_summary',
            'volume': None,
            'metadata_found': False,
            'lyrics_found': False,
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

        # Analyze loudness after normalization if enabled
        if self.config.normalize_volume:
            track_info['volume'] = self._analyze_loudness(file_path)

        # Add metadata to the file
        if file_format == "mp3":
            self._add_mp3_metadata(file_path, video_infos, artist_name)

        # Rename and sanitize the file name
        new_file_path = self._sanitize_and_rename_file(file_path, video_infos, artist_name, file_format)

        # Add album cover for MP3 files
        if file_format == "mp3" and os.path.exists(new_file_path):
            self._add_album_cover(new_file_path, video_infos, track_info)

        # Send combined summary line to UI
        if self.normalize_callback:
            self.normalize_callback(track_info)

        return [], video_infos

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
                capture_output=True, text=True, timeout=60
            )

            # Parse the loudnorm JSON output from stderr
            stderr = result.stderr
            json_start = stderr.rfind('{')
            json_end = stderr.rfind('}') + 1

            if json_start != -1 and json_end > json_start:
                loudness_data = json.loads(stderr[json_start:json_end])
                input_i = float(loudness_data.get('input_i', 0))
                target = self.config.normalize_target
                print(f"Normalization: measured at {input_i:.1f} LUFS (target: {target:.1f} LUFS)")
                return {'measured': input_i, 'target': target}
        except Exception as e:
            print(f"Warning: Could not analyze loudness: {e}")
        return None

    # ------------------------------------------------------------------
    # File renaming
    # ------------------------------------------------------------------

    def _sanitize_and_rename_file(self, file_path: str, video_infos: Dict, artist_name: str, file_format: str) -> str:
        """Sanitize filename and rename the file."""
        # Prefer clean track name from YT Music, otherwise clean the video title
        title = video_infos.get('track') or self._clean_title(video_infos.get('title', ''))
        sanitized_artist = re.sub(r'[!?:#%&{}<>|*/$@~]', '', artist_name)
        sanitized_title = re.sub(r'[!?:#%&{}<>|*/$@~]', '', title)

        new_file_path = f"{self.config.output_directory}/{sanitized_artist} - {sanitized_title}.{file_format}"

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
                    print(f"  [metadata] ✓ HD album cover")
                if enriched.synced_lyrics:
                    print(f"  [metadata] ✓ Synced lyrics (LRC) embedded")
                elif enriched.lyrics:
                    print(f"  [metadata] ✓ Lyrics embedded")

                if not enriched.cover_data and fallback_cover:
                    print(f"  [metadata] No HD cover found, using YouTube thumbnail")

                # Update track_info for the combined summary
                if track_info is not None:
                    track_info['cover_found'] = bool(enriched.cover_data)
                    track_info['lyrics_found'] = bool(enriched.synced_lyrics or enriched.lyrics)
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
