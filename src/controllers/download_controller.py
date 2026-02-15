"""
Download controller handling yt-dlp operations and metadata processing.
"""
import os
import re
import io
import json
import shutil
import subprocess
import threading
from typing import Optional, Dict, Any, Callable
import yt_dlp
from config import (ICON_PATH)
    
from mutagen.id3 import ID3, APIC
from mutagen.mp3 import MP3
from mutagen.easyid3 import EasyID3

from models import DownloadConfig, VideoInfo, PlaylistInfo, DownloadProgress
from utils import crop_album_cover, enrich_metadata, apply_enriched_metadata_mp3
from config import get_ffmpeg_path, FILE_FORMATS


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


class DownloadController:
    """Main controller for download operations."""
    
    def __init__(self):
        self.progress = DownloadProgress()
        self.ffmpeg_path = get_ffmpeg_path()
        self.progress_callback: Optional[Callable] = None
        self.completion_callback: Optional[Callable] = None
        self.normalize_callback: Optional[Callable] = None
        self.cancel_callback: Optional[Callable] = None
        self.video_infos: Optional[Dict] = None
        self._cancelled = False
        self._current_config: Optional[DownloadConfig] = None
        self._ydl_instance: Optional[yt_dlp.YoutubeDL] = None
        self._playlist_urls: list = []
        self._current_playlist_index: int = 0
        self._playlist_total_count: int = 0
        self._hidden_entries: list = []  # Entries in API but hidden on YouTube
    
    # ------------------------------------------------------------------
    # YouTube innertube helpers – resolve displayed playlist positions
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_playlist_id(url: str) -> Optional[str]:
        """Extract the playlist ID (PLxxx…) from a YouTube / YT Music URL."""
        import re as _re
        m = _re.search(r'[?&]list=([^&]+)', url)
        return m.group(1) if m else None

    @staticmethod
    def _innertube_browse(playlist_id: str, continuation: Optional[str] = None) -> Optional[Dict]:
        """Single innertube browse request. Returns raw JSON or None."""
        import urllib.request
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
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read())
        except Exception as exc:
            print(f"  [innertube] Request failed: {exc}")
            return None

    @staticmethod
    def _parse_innertube_items(result: Dict, is_continuation: bool) -> list:
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

    def _get_youtube_visible_ids(self, playlist_id: str, count: int) -> list:
        """Return the first *count* visible video IDs as displayed on youtube.com.

        Uses the innertube browse API, which returns **only entries that
        YouTube displays** to the user (skipping deleted / private /
        region-blocked videos).  This list therefore matches the numbering
        the user sees on the website.
        """
        video_ids: list = []
        continuation: Optional[str] = None

        for page in range(max(1, count // 100 + 5)):
            result = self._innertube_browse(playlist_id, continuation)
            if not result:
                break

            items = self._parse_innertube_items(result, continuation is not None)
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

    def _compute_playlist_offset(self, url: str, target_pos: int,
                                  flat_entries: list) -> int:
        """Compare YouTube's displayed numbering with the flat-extracted list.

        Returns the offset to ADD to the user's position to obtain the
        correct index in *flat_entries*.  Returns 0 when no offset is
        detected or the probe fails.
        """
        playlist_id = self._extract_playlist_id(url)
        if not playlist_id:
            return 0

        print(f"  [playlist] Probing YouTube for displayed position {target_pos}…")
        yt_ids = self._get_youtube_visible_ids(playlist_id, target_pos)

        if len(yt_ids) < target_pos:
            print(f"  [playlist] Probe returned only {len(yt_ids)} IDs "
                  f"(need {target_pos}), skipping offset detection")
            return 0

        target_id = yt_ids[target_pos - 1]

        # Locate that video ID in the flat-extracted list
        api_idx_found = None
        for api_idx, entry in enumerate(flat_entries):
            if entry and isinstance(entry, dict) and entry.get("id") == target_id:
                api_idx_found = api_idx
                break

        if api_idx_found is None:
            print(f"  [playlist] Target ID {target_id} not found in flat list")
            return 0

        offset = api_idx_found - (target_pos - 1)
        if offset != 0:
            print(f"  [playlist] Offset detected: {offset}  "
                  f"(YouTube #{target_pos} \"{flat_entries[api_idx_found].get('title', '?')}\" "
                  f"→ API index {api_idx_found + 1})")

            # Identify which entries the API has that YouTube hides.
            # Walk both lists in parallel up to the target position.
            yt_id_set = set(yt_ids[:target_pos])
            hidden = []
            for i in range(api_idx_found + 1):
                e = flat_entries[i]
                if not e or not isinstance(e, dict):
                    hidden.append({'title': '<Unknown>', 'channel': '', 'id': ''})
                    continue
                eid = e.get('id', '')
                if eid not in yt_id_set:
                    hidden.append({
                        'title': e.get('title', '<Unknown>'),
                        'channel': (e.get('channel') or e.get('uploader') or ''),
                        'id': eid,
                    })

            self._hidden_entries = hidden
        else:
            print(f"  [playlist] No offset — positions match")
            self._hidden_entries = []

        return offset
        
    def set_progress_callback(self, callback: Callable):
        """Set the callback function for progress updates."""
        self.progress_callback = callback
    
    def set_completion_callback(self, callback: Callable):
        """Set the callback function for download completion."""
        self.completion_callback = callback
    
    def set_normalize_callback(self, callback: Callable):
        """Set the callback function for normalization info."""
        self.normalize_callback = callback
    
    def set_cancel_callback(self, callback: Callable):
        """Set the callback function for when download is cancelled."""
        self.cancel_callback = callback
    
    def cancel_download(self):
        """Cancel the current download and clean up partial files."""
        self._cancelled = True
        print("Download cancellation requested...")
        
        # Abort the yt-dlp instance if running
        if self._ydl_instance:
            try:
                # yt-dlp checks this flag between downloads
                self._ydl_instance._download_retcode = 1
                # For the current file being downloaded, raise in progress hook
            except Exception:
                pass
        
        # Clean up partial files in output directory
        if self._current_config:
            self._cleanup_partial_files(self._current_config.output_directory)
    
    def _cleanup_partial_files(self, output_dir: str):
        """Remove .part, .ytdl, and other temporary download files."""
        if not output_dir or not os.path.isdir(output_dir):
            return
        try:
            for f in os.listdir(output_dir):
                fp = os.path.join(output_dir, f)
                if os.path.isfile(fp) and (f.endswith('.part') or f.endswith('.ytdl') or f.endswith('.temp')):
                    print(f"  Removing partial file: {f}")
                    os.remove(fp)
        except Exception as e:
            print(f"Warning: could not clean up partial files: {e}")
    
    def fetch_video_info(self, config: DownloadConfig, fetch_progress_callback: Optional[Callable] = None) -> tuple[Optional[Dict], Optional[str]]:
        """Fetch video information without downloading. Returns (info, error_message)."""
        self._playlist_urls = []
        ydl_opts = {
            'verbose': config.verbose,
            'quiet': True,
            'ignoreerrors': True,
            'extractor_args': {'youtubetab': {'skip': ['authcheck']}},
            'external_downloader_args': ['-loglevel', 'panic'],
            'simulate': True,
            'cachedir': False,
            'noplaylist': not config.is_playlist,
        }
        
        # For playlists, use extract_flat for much faster extraction
        # (no per-video HTTP request, just playlist API pagination)
        if config.is_playlist:
            ydl_opts['extract_flat'] = 'in_playlist'
        
        try:
            if config.is_playlist and fetch_progress_callback:
                # Two-step extraction with progress tracking:
                # 1) Get raw result without processing (entries stay as generator)
                # 2) Wrap entries generator to count progress, then process
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ie_result = ydl.extract_info(config.url, download=False, process=False)
                    
                    if ie_result and ie_result.get('_type') in ('playlist', 'multi_video') and 'entries' in ie_result:
                        total_hint = ie_result.get('playlist_count')  # May be None
                        original_entries = ie_result['entries']
                        
                        def counting_entries():
                            count = 0
                            for entry in original_entries:
                                count += 1
                                fetch_progress_callback(count, total_hint)
                                yield entry
                        
                        ie_result['entries'] = counting_entries()
                        self.video_infos = ydl.process_ie_result(ie_result, download=False)
                    else:
                        self.video_infos = ie_result
            else:
                self.video_infos = yt_dlp.YoutubeDL(ydl_opts).extract_info(config.url, download=False)
            
            # Check if video_infos is None or empty (which happens with ignoreerrors=True for DRM sites)
            if not self.video_infos:
                # Check if this is a known DRM-protected site
                if ("spotify.com" in config.url.lower() or 
                    "netflix.com" in config.url.lower() or
                    "disney" in config.url.lower() or
                    "hulu.com" in config.url.lower() or
                    "amazon" in config.url.lower()):
                    return None, "This content is protected by DRM and cannot be downloaded.\n\nDRM (Digital Rights Management) prevents downloading from services like Spotify, Netflix, etc."
                else:
                    return None, "Could not retrieve video information. Please check the URL."
            
            # For playlists, slice entries to the user's requested range.
            if config.is_playlist and self.video_infos and 'entries' in self.video_infos:
                all_entries = self.video_infos.get('entries', [])
                if isinstance(all_entries, list) and len(all_entries) > 0:
                    total_count = len(all_entries)
                    start_idx = max(0, config.playlist_start - 1)
                    end_idx = min(config.playlist_end, total_count)

                    # Detect numbering offset between YouTube's displayed
                    # positions and yt-dlp's flat-extracted list.
                    # YouTube may hide certain entries (deleted, private,
                    # region-restricted…) that the API still includes,
                    # causing the user-visible position N to differ from
                    # API index N.
                    if start_idx > 0:
                        offset = self._compute_playlist_offset(
                            config.url, config.playlist_start, all_entries)
                        start_idx += offset
                        end_idx += offset
                        # Clamp to valid range
                        start_idx = max(0, min(start_idx, total_count - 1))
                        end_idx = min(end_idx, total_count)

                    # Only use individual downloads if user specified a sub-range
                    if start_idx > 0 or end_idx < total_count:
                        sliced = all_entries[start_idx:end_idx]
                        # Filter only None/truly-broken entries from the slice
                        valid = [e for e in sliced if e and isinstance(e, dict) and e.get('id')]
                        self._playlist_urls = []
                        for entry in valid:
                            vid_id = entry.get('id') or entry.get('url')
                            url = entry.get('url', '')
                            if not url.startswith('http'):
                                url = f"https://www.youtube.com/watch?v={vid_id}"
                            self._playlist_urls.append(url)

                        self.video_infos['entries'] = valid
                        self.video_infos['playlist_count'] = len(valid)

            return self.video_infos, None
        except yt_dlp.utils.ExtractorError as error:
            error_message = str(error)
            
            # Handle ExtractorError specifically (includes DRM errors)
            if ("DRM protection" in error_message or "DRM protected" in error_message or 
                "use DRM protection" in error_message or "known to use DRM" in error_message):
                return None, "This content is protected by DRM and cannot be downloaded.\n\nDRM (Digital Rights Management) prevents downloading from services like Spotify, Netflix, etc."
            else:
                clean_error = error_message.replace("ERROR: ", "").strip()
                return None, f"Download failed: {clean_error}"
        except yt_dlp.utils.DownloadError as error:
            error_message = str(error)
            
            # Try to extract meaningful error messages
            if ("DRM protection" in error_message or "DRM protected" in error_message or 
                "use DRM protection" in error_message or "known to use DRM" in error_message):
                return None, "This content is protected by DRM and cannot be downloaded.\n\nDRM (Digital Rights Management) prevents downloading from services like Spotify, Netflix, etc."
            elif "Video unavailable" in error_message:
                return None, "This video is unavailable or has been removed."
            elif "Private video" in error_message:
                return None, "This video is private and cannot be downloaded."
            elif "This video is only available for Music Premium members" in error_message:
                return None, "This video requires YouTube Music Premium."
            elif "Video not found" in error_message or "does not exist" in error_message:
                return None, "Video not found. Please check the URL."
            elif "Unsupported URL" in error_message:
                return None, "Unsupported URL format. Please check the URL."
            elif "Sign in to confirm your age" in error_message:
                return None, "This video requires age verification and cannot be downloaded."
            elif "This video is not available" in error_message:
                return None, "This video is not available in your region or has been removed."
            else:
                # For other errors, show the actual yt-dlp error message
                clean_error = error_message.replace("ERROR: ", "").strip()
                return None, f"Download failed: {clean_error}"
        except Exception as e:
            return None, f"Unexpected error: {str(e)}"
    
    def start_download(self, config: DownloadConfig):
        """Start the download process in a separate thread."""
        self._cancelled = False
        self._current_config = config
        thread = threading.Thread(target=self._download_process, args=(config,))
        thread.daemon = True
        thread.start()
    
    def _download_process(self, config: DownloadConfig):
        """Main download process."""
        try:
            ydl_opts = self._build_ydl_options(config)
            
            if config.is_playlist and self._playlist_urls:
                # Download individual videos by URL to avoid playlist
                # indexing offset caused by deleted/unavailable entries.
                ydl_opts['noplaylist'] = True
                self._playlist_total_count = len(self._playlist_urls)
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    self._ydl_instance = ydl
                    ydl.add_post_processor(
                        CustomPostProcessor(config, normalize_callback=self.normalize_callback),
                        when='post_process'
                    )
                    for i, url in enumerate(self._playlist_urls, 1):
                        if self._cancelled:
                            break
                        self._current_playlist_index = i
                        ydl.download([url])
            else:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    self._ydl_instance = ydl
                    ydl.add_post_processor(
                        CustomPostProcessor(config, normalize_callback=self.normalize_callback),
                        when='post_process'
                    )
                    ydl.download([config.url])
            
            self._ydl_instance = None
            
            if self._cancelled:
                self._cleanup_partial_files(config.output_directory)
                print("Download cancelled.")
                if self.cancel_callback:
                    self.cancel_callback()
                return
            
            self._send_completion_notification(config)
            
            # Call completion callback to reset UI
            if self.completion_callback:
                self.completion_callback()
            
        except (yt_dlp.utils.ExistingVideoReached, yt_dlp.utils.RejectedVideoReached):
            # Raised by progress hook to abort the entire playlist immediately
            self._ydl_instance = None
            self._cleanup_partial_files(config.output_directory)
            print("Download cancelled.")
            if self.cancel_callback:
                self.cancel_callback()
        except yt_dlp.utils.DownloadError as error:
            self._ydl_instance = None
            if self._cancelled:
                self._cleanup_partial_files(config.output_directory)
                print("Download cancelled.")
                if self.cancel_callback:
                    self.cancel_callback()
                return
            print(f"Download error: {error}")
            self._retry_download(config)
    
    def _build_ydl_options(self, config: DownloadConfig) -> Dict[str, Any]:
        """Build yt-dlp options based on configuration."""
        base_opts = {
            'verbose': config.verbose,
            'no-part': True,
            'ignoreerrors': True,
            'quiet': True,
            'extractor_args': {'youtubetab': {'skip': ['authcheck']}},
            'external_downloader_args': ['-loglevel', 'panic'],
            'outtmpl': config.output_template,
            'noplaylist': not config.is_playlist,
            'progress_hooks': [self._progress_hook],
            'match_filter': self._cancel_filter,
        }
        
        if config.file_format == "mp3":
            return self._add_mp3_options(base_opts, config)
        elif config.file_format == "mp4":
            return self._add_mp4_options(base_opts, config)
        
        return base_opts
    
    def _add_mp3_options(self, opts: Dict, config: DownloadConfig) -> Dict:
        """Add MP3-specific options."""
        opts['format'] = 'bestaudio/best'
        
        if self.ffmpeg_path is not None:
            opts['ffmpeg_location'] = self.ffmpeg_path
            extract_audio_pp = {
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
            }
            # "Best" means no quality cap — let yt-dlp use the highest available
            if config.bitrate and config.bitrate.lower() != 'best':
                extract_audio_pp['preferredquality'] = config.bitrate
            else:
                extract_audio_pp['preferredquality'] = '0'  # 0 = best quality (VBR)
            opts['postprocessors'] = [
                extract_audio_pp,
                {'key': 'FFmpegMetadata', 'add_metadata': True}
            ]
            
            # Add volume normalization if enabled
            # Keys must be lowercase — yt-dlp's _configuration_args does .lower() lookups.
            if config.normalize_volume:
                target = config.normalize_target
                opts['postprocessor_args'] = {
                    'extractaudio': [
                        '-af', f'loudnorm=I={target}:TP=-1.5:LRA=11'
                    ]
                }
        else:
            print("Warning: MP3 conversion disabled - ffmpeg not found")
            opts['format'] = 'bestaudio'
        
        return opts
    
    def _add_mp4_options(self, opts: Dict, config: DownloadConfig) -> Dict:
        """Add MP4-specific options."""
        if config.quality and config.quality.lower() == 'best':
            format_string = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
        else:
            format_string = f'bestvideo[height<={config.quality}][vbr<=12000][ext=mp4]+bestaudio[ext=m4a]/best[vbr<=12000][ext=mp4]/best'
        opts['format'] = format_string
        
        if self.ffmpeg_path is not None:
            opts['ffmpeg_location'] = self.ffmpeg_path
            opts['postprocessors'] = [{'key': 'FFmpegVideoConvertor', 'preferedformat': 'mp4'}]
            
            # Add volume normalization if enabled
            # For MP4, apply loudnorm during the merge step.
            # We override the audio codec to re-encode audio with loudnorm
            # while keeping video as stream copy.
            # Key must be lowercase — yt-dlp's _configuration_args does .lower() lookups.
            if config.normalize_volume:
                target = config.normalize_target
                opts['postprocessor_args'] = {
                    'merger+ffmpeg_o': [
                        '-c:v', 'copy',
                        '-c:a', 'aac', '-b:a', '192k',
                        '-af', f'loudnorm=I={target}:TP=-1.5:LRA=11'
                    ]
                }
        else:
            print("Warning: MP4 conversion disabled - ffmpeg not found")
        
        return opts
    
    def _cancel_filter(self, info_dict, *, incomplete):
        """Match filter that rejects all entries once download is cancelled.
        
        This runs before yt-dlp starts extracting/downloading each entry,
        so it prevents wasted network requests after cancellation.
        Returning a string means 'reject this entry with this reason'.
        """
        if self._cancelled:
            raise yt_dlp.utils.ExistingVideoReached()
        return None

    def _progress_hook(self, d: Dict):
        """Handle progress updates from yt-dlp."""
        if self._cancelled:
            # Use ExistingVideoReached to make yt-dlp abort the entire
            # playlist loop immediately, instead of DownloadError which
            # is caught by ignoreerrors and moves to the next entry.
            raise yt_dlp.utils.ExistingVideoReached()
        # For individual-URL playlist downloads, inject playlist context
        # so the progress display works correctly.
        if self._playlist_urls and 'info_dict' in d:
            d['info_dict'].setdefault('playlist_autonumber', self._current_playlist_index)
            d['info_dict'].setdefault('n_entries', self._playlist_total_count)
        if self.progress_callback:
            self.progress_callback(d, self.video_infos, self.progress)
    
    def _retry_download(self, config: DownloadConfig):
        """Retry download on error."""
        print("There was a problem during the download, automatically restarting!")
        # Implementation for retry logic
        pass
    
    def _send_completion_notification(self, config: DownloadConfig):
        """Send completion notification."""
        if self.video_infos:
            if config.is_playlist:
                playlist_title = self.video_infos.get('title', 'Unknown Playlist')
                count = self.progress.current_song if self.progress else 0
                if count > 0:
                    message = f"{count} element{'s' if count > 1 else ''} downloaded from playlist {playlist_title}."
                else:
                    message = f"Playlist {playlist_title} downloaded."
            else:
                title = self.video_infos.get('title', 'Unknown')
                message = f"Video \"{title}\" has been downloaded."
            
            try:
                if shutil.which("notify-send"):
                    cmd = [
                        "notify-send",
                        "--app-name=yt-dlp GUI",
                        "--expire-time=5000",
                        "Download Complete!",
                        message,
                    ]
                    # Add icon if available
                    if ICON_PATH and os.path.isfile(ICON_PATH):
                        cmd.insert(1, f"--icon={ICON_PATH}")
                    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    print(f"Download Complete! {message}")
            except Exception:
                print(f"Download Complete! {message}")
