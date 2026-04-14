"""
yt-dlp options builder for different download configurations.
"""
import os
from typing import Dict, Any, Optional

from config import COOKIES_PATH
from models import DownloadConfig


def build_ydl_options(config: DownloadConfig, ffmpeg_path: Optional[str],
                      progress_hook, cancel_filter) -> Dict[str, Any]:
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
        'progress_hooks': [progress_hook],
        'match_filter': cancel_filter,
    }

    # Use cookies file if available
    if os.path.isfile(COOKIES_PATH):
        base_opts['cookiefile'] = COOKIES_PATH

    if config.file_format == "mp3":
        return _add_mp3_options(base_opts, config, ffmpeg_path)
    elif config.file_format == "mp4":
        return _add_mp4_options(base_opts, config, ffmpeg_path)
    elif config.file_format == "opus":
        return _add_opus_options(base_opts, config, ffmpeg_path)

    return base_opts


def _add_mp3_options(opts: Dict, config: DownloadConfig,
                     ffmpeg_path: Optional[str]) -> Dict:
    """Add MP3-specific options.

    We skip FFmpegExtractAudio so that the CustomPostProcessor can probe
    the source bitrate and use it as a ceiling (cap).  This avoids
    inflating the file when the user selects a bitrate higher than the
    source (e.g. "Max 320Kbps" on a 128 kbps source).
    """
    opts['format'] = 'bestaudio/best'

    if ffmpeg_path is not None:
        opts['ffmpeg_location'] = ffmpeg_path
        # No FFmpegExtractAudio — conversion is handled by CustomPostProcessor
        # with proper bitrate capping logic.
        opts['postprocessors'] = []
    else:
        print("Warning: MP3 conversion disabled - ffmpeg not found")
        opts['format'] = 'bestaudio'

    return opts


def _add_opus_options(opts: Dict, config: DownloadConfig,
                      ffmpeg_path: Optional[str]) -> Dict:
    """Add Opus-specific options.

    We deliberately avoid FFmpegExtractAudio with preferredcodec='opus'
    because the 'opus' muxer in some ffmpeg builds (e.g. Fedora) is broken
    ("Error opening output files: Function not implemented").
    Instead, we download the best opus audio (YouTube already serves opus in
    WebM) and let the CustomPostProcessor remux to a proper .opus file using
    the reliable 'ogg' muxer.
    """
    opts['format'] = 'bestaudio[acodec=opus]/bestaudio/best'

    if ffmpeg_path is not None:
        opts['ffmpeg_location'] = ffmpeg_path
        # No FFmpegExtractAudio — remux is handled by CustomPostProcessor
        opts['postprocessors'] = []
    else:
        print("Warning: Opus conversion disabled - ffmpeg not found")
        opts['format'] = 'bestaudio'

    return opts


def _add_mp4_options(opts: Dict, config: DownloadConfig,
                     ffmpeg_path: Optional[str]) -> Dict:
    """Add MP4-specific options."""
    if config.quality and config.quality.lower() == 'best':
        format_string = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
    else:
        format_string = f'bestvideo[height<={config.quality}][vbr<=12000][ext=mp4]+bestaudio[ext=m4a]/best[vbr<=12000][ext=mp4]/best'
    opts['format'] = format_string

    if ffmpeg_path is not None:
        opts['ffmpeg_location'] = ffmpeg_path
        opts['postprocessors'] = [{'key': 'FFmpegVideoConvertor', 'preferedformat': 'mp4'}]

        # Add volume normalization if enabled
        # For MP4, apply loudnorm during the merge step.
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
