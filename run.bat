@echo off
title yt-dlp Convenient GUI - Installation et Lancement Automatique
color 0F

:: Vérifier si c'est la première exécution (pas d'installation précédente)
if not exist ".installed" goto :install
goto :launch

:install
echo ================================================
echo yt-dlp Convenient GUI - Installation automatique
echo ================================================
echo.

:: Vérification et installation de Python
echo [1/4] Vérification de Python...
python --version >nul 2>&1
if %errorLevel% == 0 (
    echo [OK] Python est installé
    python --version
) else (
    echo [INFO] Installation de Python requise...
    if not exist "temp" mkdir temp
    echo Téléchargement de Python 3.11.9...
    powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile 'temp\python-installer.exe'"
    if exist "temp\python-installer.exe" (
        echo Installation de Python...
        temp\python-installer.exe /quiet InstallAllUsers=1 PrependPath=1
        echo [INFO] Redémarrez et relancez ce fichier
        pause
        exit /b 1
    )
)

:: Vérification et mise à jour de pip
echo [2/4] Vérification de pip...
pip --version >nul 2>&1
if %errorLevel% == 0 (
    echo [OK] pip disponible - Mise à jour...
    python -m pip install --upgrade pip
) else (
    python -m ensurepip --upgrade
    python -m pip install --upgrade pip
)

:: Installation des dépendances Python
echo [3/4] Installation des dépendances...
if exist "requirements.txt" (
    pip install -r requirements.txt
) else (
    pip install yt-dlp>=2023.12.30 Pillow>=10.0.0 ttkthemes>=3.2.2 plyer>=2.1.0 mutagen>=1.47.0
)

:: Installation de FFmpeg
echo [4/4] Installation de FFmpeg...
ffmpeg -version >nul 2>&1
if %errorLevel% neq 0 (
    if not exist "ffmpeg\bin" mkdir ffmpeg\bin
    echo Téléchargement de FFmpeg...
    powershell -Command "Invoke-WebRequest -Uri 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip' -OutFile 'temp\ffmpeg.zip'"
    if exist "temp\ffmpeg.zip" (
        powershell -Command "Expand-Archive -Path 'temp\ffmpeg.zip' -DestinationPath 'temp\ffmpeg-extract' -Force"
        for /d %%i in (temp\ffmpeg-extract\ffmpeg-*) do xcopy "%%i\bin\*" "ffmpeg\bin\" /Y /I
        echo [OK] FFmpeg installé
    )
)

:: Nettoyage et marquage d'installation
if exist "temp" rmdir /s /q "temp"
echo. > .installed
echo [OK] Installation terminée !
echo.

:launch
:: Ajouter FFmpeg au PATH
if exist "ffmpeg\bin" set "PATH=%CD%\ffmpeg\bin;%PATH%"

:: Vérification finale avant lancement
python --version >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERREUR] Python non accessible - Relancez après redémarrage
    pause
    exit /b 1
)

echo Lancement de yt-dlp Convenient GUI...
python run.py

if %errorLevel% neq 0 (
    echo.
    echo [ERREUR] Erreur de lancement
    pause
)
