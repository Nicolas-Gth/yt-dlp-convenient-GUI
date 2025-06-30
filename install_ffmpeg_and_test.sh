#!/bin/bash

# Script to check and install ffmpeg on Linux
echo "Checking for ffmpeg installation..."

# Check if ffmpeg is installed
if command -v ffmpeg &> /dev/null; then
    echo "✓ ffmpeg is already installed at: $(which ffmpeg)"
    ffmpeg -version | head -n 1
else
    echo "✗ ffmpeg not found"
    echo ""
    echo "To install ffmpeg on your system:"
    echo ""
    
    # Detect Linux distribution
    if command -v apt &> /dev/null; then
        echo "Ubuntu/Debian detected:"
        echo "  sudo apt update && sudo apt install ffmpeg"
        echo ""
        read -p "Would you like to install ffmpeg now? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            sudo apt update && sudo apt install ffmpeg
        fi
    elif command -v dnf &> /dev/null; then
        echo "Fedora detected:"
        echo "  sudo dnf install ffmpeg"
        echo ""
        read -p "Would you like to install ffmpeg now? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            sudo dnf install ffmpeg
        fi
    elif command -v pacman &> /dev/null; then
        echo "Arch Linux detected:"
        echo "  sudo pacman -S ffmpeg"
        echo ""
        read -p "Would you like to install ffmpeg now? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            sudo pacman -S ffmpeg
        fi
    else
        echo "Could not detect your Linux distribution."
        echo "Please install ffmpeg using your package manager."
    fi
fi

echo ""
echo "Now testing the yt-dlp GUI application..."
echo ""

# Test the application
cd "$(dirname "$0")"
/var/home/nicolas/Code/yt-dlp-convenient-GUI/.venv/bin/python src/main.py
