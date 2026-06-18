# yt-dlp Convenient GUI
<div align="center">
  <img src="assets/yt-dlp_convenient_gui_icon.png" alt="yt-dlp Convenient GUI" width="300">
  <p>
    <a href="https://github.com/Nicolas-Gth/yt-dlp-convenient-GUI/blob/main/LICENSE"><img src="https://img.shields.io/github/license/Nicolas-Gth/yt-dlp-convenient-GUI?style=flat&color=blue" alt="License"></a>
    <img src="https://img.shields.io/badge/OS-Windows%20%7C%20macOS%20%7C%20Linux-success?style=flat" alt="Supported OS">
    <img src="https://img.shields.io/badge/Python-3.x-yellow?style=flat&logo=python&logoColor=white" alt="Python">
    <a href="https://github.com/Nicolas-Gth/yt-dlp-convenient-GUI/stargazers"><img src="https://img.shields.io/github/stars/Nicolas-Gth/yt-dlp-convenient-GUI?style=flat&color=gold" alt="Stars"></a>
    <a href="https://github.com/Nicolas-Gth/yt-dlp-convenient-GUI/pulse"><img src="https://img.shields.io/github/commit-activity/m/Nicolas-Gth/yt-dlp-convenient-GUI?style=flat&color=007ec6" alt="Commits per month"></a>
  </p>
</div>

## Preview
<p align="center">
  <img alt="downloading a song" src="https://github.com/user-attachments/assets/3d6a077f-5c6d-4511-9acb-1ec7c60f4284" width="40%" align="middle"/>

  <img src="https://github.com/user-attachments/assets/867aa06b-e105-448e-b754-bbf8632fb8f2" width="50%" align="middle"/>
</p>

## Features
- Download media in your preferred quality, bitrate, and format (MP4, MP3, Opus)
- Audio normalization for consistent playback volume
- Advanced metadata search: automatically fetches and embeds rich track info (artist, album, cover art, etc.)
- Synchronized lyrics search: embeds time-synced lyrics (LRC) directly into downloaded files
- Edit easily the files in your downloads folder
- Remembers settings
- Warns you if videos from your playlist are no longer accessible, private or age-restricted so you can search for an alternative or set a cookies file.

## Installation

### Download
<div align="center">
  <a href="https://github.com/Nicolas-Gth/yt-dlp-convenient-GUI/releases/latest/download/yt-dlp-convenient-gui-setup.exe"><img src="https://img.shields.io/github/v/release/Nicolas-Gth/yt-dlp-convenient-GUI?style=for-the-badge&color=2ea043&labelColor=2ea043&label=%E2%86%93%20Download%20for%20Windows" alt="Download Latest Version for Windows"></a>
  <a href="https://github.com/Nicolas-Gth/yt-dlp-convenient-GUI/releases/latest/download/yt-dlp-convenient-GUI.zip"><img src="https://img.shields.io/github/v/release/Nicolas-Gth/yt-dlp-convenient-GUI?style=for-the-badge&color=2ea043&labelColor=2ea043&label=%E2%86%93%20Download%20for%20MacOS/Linux" alt="Download Latest Version for MacOS/Linux"></a>
</div>
<br>

Alternatively you can clone this repository with `git clone https://github.com/Nicolas-Gth/yt-dlp-convenient-GUI.git`

Both should be done in the directory where you want the app to be installed (your user folder for example. 

### Windows Users
Run `yt-dlp-convenient-gui-setup.exe`

### macOS & Linux Users
Depending on your desktop environment, you might be able to double-click `install.sh` or right-click it and select *Run in Terminal* or a similar option.

If that isn't possible, open a terminal and do these commands:
```bash
# Go to the project root directory:
# replace the line after the cd command with the path to where you downloaded the folder
# you can get the path by right clicking on the app folder-> copy folder path
cd /path/to/the/extracted/app/folder

# Run the installer:
./install.sh
```
If you encounter a permission issue, run the following line in the same powershell as mentioned above:
```bash
# Make the script executable
chmod +x install.sh
```

## Troubleshooting
### Windows
- If you encounter a permission issue due to Windows policies, run the following line in a powershell:
```powershell
Set-ExecutionPolicy -ExecutionPolicy Unrestricted -Scope CurrentUser
```
- For antivirus issues, add the project folder to exceptions

### macOS & Linux
- Make sure the script is executable: `chmod +x install.sh`
- For permission issues, the script will prompt for your password when needed
- If the launcher couldn't install the needed packages you might have to install them manually. This process will depend on your OS and you will have to install the following:
  - Python 3, pip, and FFmpeg using your package manager
  - ```pip3 install -r requirements.txt```

## License
This project is licensed under the [GNU GPL v3](LICENSE).