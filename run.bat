@echo off
title yt-dlp Convenient GUI - Automatic Installation and Launch
color 0F

:: Check if all components are installed
call :check_components
if %componentsOK% == 0 goto :install
goto :launch

:check_components
set componentsOK=1

:: Add local FFmpeg to PATH for verification
if exist "ffmpeg\bin" set "PATH=%CD%\ffmpeg\bin;%PATH%"

:: Check Python
python --version >nul 2>&1
if %errorLevel% neq 0 set componentsOK=0

:: Check pip
pip --version >nul 2>&1
if %errorLevel% neq 0 set componentsOK=0

:: Check FFmpeg (global or local)
ffmpeg -version >nul 2>&1
if %errorLevel% neq 0 set componentsOK=0

:: Check critical Python dependencies
if %componentsOK% == 1 (
    python -c "import yt_dlp, PIL, ttkthemes, plyer, mutagen" >nul 2>&1
    if %errorLevel% neq 0 set componentsOK=0
)

goto :eof
goto :launch

:install
echo ▗▖  ▗▖▗▄▄▄▖    ▗▄▄▄ ▗▖   ▗▄▄▖                                          
echo  ▝▚▞▘   █      ▐▌  █▐▌   ▐▌ ▐▌                                         
echo   ▐▌    █  ▀▀▘ ▐▌  █▐▌   ▐▛▀▘                                          
echo   ▐▌    █      ▐▙▄▄▀▐▙▄▄▖▐▌                                            
echo  ▗▄▄▖ ▗▄▖ ▗▖  ▗▖▗▖  ▗▖▗▄▄▄▖▗▖  ▗▖▗▄▄▄▖▗▄▄▄▖▗▖  ▗▖▗▄▄▄▖   ▗▄▄▖▗▖ ▗▖▗▄▄▄▖
echo ▐▌   ▐▌ ▐▌▐▛▚▖▐▌▐▌  ▐▌▐▌   ▐▛▚▖▐▌  █  ▐▌   ▐▛▚▖▐▌  █    ▐▌   ▐▌ ▐▌  █  
echo ▐▌   ▐▌ ▐▌▐▌ ▝▜▌▐▌  ▐▌▐▛▀▀▘▐▌ ▝▜▌  █  ▐▛▀▀▘▐▌ ▝▜▌  █    ▐▌▝▜▌▐▌ ▐▌  █  
echo ▝▚▄▄▖▝▚▄▞▘▐▌  ▐▌ ▝▚▞▘ ▐▙▄▄▖▐▌  ▐▌▗▄█▄▖▐▙▄▄▖▐▌  ▐▌  █    ▝▚▄▞▘▝▚▄▞▘▗▄█▄▖
echo.

:: Python verification and installation
echo [1/4] Checking Python...
python --version >nul 2>&1
if %errorLevel% == 0 (
    echo [OK] Python is installed
    python --version
) else (
    echo [INFO] Python installation required...
    if not exist "temp" mkdir temp
    echo Downloading Python 3.11.9...
    powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile 'temp\python-installer.exe'"
    if exist "temp\python-installer.exe" (
        echo Installing Python...
        temp\python-installer.exe /quiet InstallAllUsers=1 PrependPath=1
        echo [INFO] Restart and relaunch this file
        pause
        exit /b 1
    )
)

:: pip verification and update
echo [2/4] Checking pip...
pip --version >nul 2>&1
if %errorLevel% == 0 (
    echo [OK] pip available - Updating...
    python -m pip install --upgrade pip
) else (
    python -m ensurepip --upgrade
    python -m pip install --upgrade pip
)

:: Python dependencies installation
echo [3/4] Installing dependencies...
if exist "requirements.txt" (
    pip install -r requirements.txt
) else (
    pip install yt-dlp>=2023.12.30 Pillow>=10.0.0 ttkthemes>=3.2.2 plyer>=2.1.0 mutagen>=1.47.0
)

:: FFmpeg installation
echo [4/4] Installing FFmpeg...
ffmpeg -version >nul 2>&1
if %errorLevel% neq 0 (
    if not exist "temp" mkdir temp
    if not exist "ffmpeg\bin" mkdir ffmpeg\bin
    echo Downloading FFmpeg...
    powershell -Command "Invoke-WebRequest -Uri 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip' -OutFile 'temp\ffmpeg.zip'"
    if exist "temp\ffmpeg.zip" (
        powershell -Command "Expand-Archive -Path 'temp\ffmpeg.zip' -DestinationPath 'temp\ffmpeg-extract' -Force"
        for /d %%i in (temp\ffmpeg-extract\ffmpeg-*) do xcopy "%%i\bin\*" "ffmpeg\bin\" /Y /I
        echo [OK] FFmpeg installed
    )
)

:: Cleanup
if exist "temp" rmdir /s /q "temp"
echo [OK] Installation completed!
echo.

:launch
:: Add FFmpeg to PATH
if exist "ffmpeg\bin" set "PATH=%CD%\ffmpeg\bin;%PATH%"

:: Final verification before launch
python --version >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] Python not accessible - Relaunch after restart
    pause
    exit /b 1
)

echo Launching yt-dlp Convenient GUI...
python run.py

if %errorLevel% neq 0 (
    echo.
    echo [ERROR] Launch error
    pause
)
