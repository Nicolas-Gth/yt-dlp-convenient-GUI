# yt-dlp Convenient GUI
<div align="center"><img src="assets/yt-dlp_convenient_gui_icon.png" alt="yt-dlp Convenient GUI" width="300"></div>

A simple and intuitive graphical interface for yt-dlp that allows you to download videos and audio from YouTube and other platforms with ease.

## Quick Start

### Windows Users
**Simply double-click `run.bat`** - Everything will be installed automatically!

The script will:
- Install Python (if needed)
- Install all dependencies
- Download FFmpeg locally
- Launch the application

### Linux/macOS Users
```bash
# Install dependencies
pip install -r requirements.txt

# Install FFmpeg (if not already installed)
# Ubuntu/Debian: sudo apt install ffmpeg
# macOS: brew install ffmpeg

# Run the application
python3 run.py
```

## Features

- Download videos in various qualities (144p to 4K)
- Extract audio in multiple bitrates (32Kbps to 320Kbps)
- Support for MP3 and MP4 formats
- Simple and clean interface
- Cross-platform compatibility

## Usage Tips

1. **Paste any video URL** in the input field
2. **Choose format**: MP3 for audio, MP4 for video
3. **Select quality/bitrate** as needed
4. **Click Download** and wait for completion

## Troubleshooting

### Windows
- If Python installation fails, restart your computer and run `run.bat` again
- For antivirus issues, add the project folder to exceptions

### Linux/macOS
- Make sure FFmpeg is installed: `ffmpeg -version`
- Check Python version: `python3 --version` (3.8+ required)
