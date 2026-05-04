<h2 align="center">
  <img src="assets/titre_features.png" alt="Features" width="100%">
</h2>

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
  <img src="https://github.com/user-attachments/assets/49605fe5-894f-4047-9af7-f832ea62f187" width="30%" align="middle"/>
  <img src="https://github.com/user-attachments/assets/83271379-f116-4e17-81b2-99919d1bdb68" width="60%" align="middle"/>
</p>

## Features
- Download media in your preferred quality, bitrate, and format (MP4, MP3, Opus)
- Audio normalization for consistent playback volume
- Advanced metadata search: automatically fetches and embeds rich track info (artist, album, cover art, etc.)
- Synchronized lyrics search: embeds time-synced lyrics (LRC) directly into downloaded files
- Remembers settings
- Warns you if videos from your playlist are no longer accessible, private or age-restricted so you can search for an alternative or set a cookies file.

## Installation

### Download
Click the download button and extract the downloaded .zip file into your desired installation folder.
<div align="center">
  <a href="https://github.com/Nicolas-Gth/yt-dlp-convenient-GUI/releases/latest/download/yt-dlp-convenient-GUI.zip">
    <img src="https://img.shields.io/github/v/release/Nicolas-Gth/yt-dlp-convenient-GUI?style=for-the-badge&color=2ea043&labelColor=2ea043&label=%E2%86%93%20Download%20Latest" alt="Download Latest Version">
  </a>
</div>
<br>

Alternatively you can clone this repository with `git clone https://github.com/Nicolas-Gth/yt-dlp-convenient-GUI.git`

Both should be done in the directory where you want the app to be installed (your user folder for example. 

### Windows Users
Right-click `install.ps1` then select *Run with PowerShell*.

If that isn't possible, open a powershell and do these commands:
```powershell
# Go to the project root directory:
# replace the line after the cd command with the path to where you downloaded the folder
# you can get the path by right clicking on the app folder-> copy folder path
cd C:\path\to\the\extracted\app\folder

# Run the installer:
.\install.ps1
```

If you encounter a permission issue due to Windows policies, run the following line in the same powershell as mentioned above:
```powershell
Set-ExecutionPolicy -ExecutionPolicy Unrestricted -Scope CurrentUser
```

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
- If you encounter a permission issue due to Windows policies, run the following line in a powershell. In the same powershell (if you close it you will have to redo the command so don't close it), run install.ps1 like mentionned in [this section](#windows-users). 
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
