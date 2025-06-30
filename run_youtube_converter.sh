#!/bin/bash

# yt-dlp Convenient GUI Launcher for Linux
# Make sure FFmpeg is installed: sudo apt install ffmpeg (Ubuntu/Debian)

cd "$(dirname "$0")"

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Install dependencies if requirements.txt exists
if [ -f "requirements.txt" ]; then
    echo "Installing dependencies..."
    pip install -r requirements.txt
fi

# Check if FFmpeg is available
if ! command -v ffmpeg &> /dev/null; then
    echo "Warning: FFmpeg not found. Please install it using:"
    echo "  Ubuntu/Debian: sudo apt install ffmpeg"
    echo "  Fedora: sudo dnf install ffmpeg"
    echo "  Arch: sudo pacman -S ffmpeg"
    echo ""
fi

# Run the application
echo "Starting yt-dlp Convenient GUI..."
python src/main.py

# Keep the terminal open if there's an error
if [ $? -ne 0 ]; then
    echo "Press any key to continue..."
    read -n 1
fi
