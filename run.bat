@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
chcp 65001 >nul
title yt-dlp Convenient GUI - Automatic Installation and Launch
color 0F

echo  __   ______         ____  _     ____
echo  \ \ / /_   _        ^|  _ \^| ^|   ^|  _ \
echo   \ V /  ^| ^|   _____ ^| ^| ^| ^| ^|   ^| ^|_^) ^|
echo    ^| ^|   ^| ^|  ^|_____^|^| ^|_^| ^| ^|___^|  __/
echo    ^|_^|   ^|_^|         ^|____/^|_____^|_^|
echo   ____                            _            _      ____ _   _ ___
echo  / ___^| ___  _ ____   _____ _ __ ^(_^) ___ _ __ ^| ^|_   / ___^| ^| ^| ^|_ _^|
echo ^| ^|    / _ \^| '_ \ \ / / _ \ '_ \^| ^|/ _ \ '_ \^| __^| ^| ^|  _^| ^| ^| ^|^| ^|
echo ^| ^|___^| ^(_^) ^| ^| ^| \ V /  __/ ^| ^| ^| ^|  __/ ^| ^| ^| ^|_  ^| ^|_^| ^| ^|_^| ^|^| ^|
echo  \____^|\___/^|_^| ^|_^|\_/ \___^|_^| ^|_^|_^|\___^|_^| ^|_^|\__^|  \____^|\___/^|___^|
echo.

:: Check if all components are installed
call :check_components
if !componentsOK! == 0 goto :install
goto :launch

:check_components
set componentsOK=1

:: Add local FFmpeg to PATH for verification
if exist "ffmpeg\bin" set "PATH=%CD%\ffmpeg\bin;%PATH%"

:: Add Deno to PATH if installed
if exist "%USERPROFILE%\.deno\bin" set "PATH=%USERPROFILE%\.deno\bin;%PATH%"

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
if !componentsOK! == 1 (
    python -c "import yt_dlp, PIL, PySide6, mutagen" >nul 2>&1
    if !errorLevel! neq 0 set componentsOK=0
)

:: Check Deno (required for YouTube signature solving)
deno --version >nul 2>&1
if %errorLevel% neq 0 set componentsOK=0

goto :eof

:install
:: Python verification and installation
echo [1/5] Checking Python...
python --version >nul 2>&1
if !errorLevel! == 0 (
    echo [OK] Python is installed
    python --version
) else (
    echo [INFO] Python installation required...
    if not exist "temp" mkdir temp
    echo Downloading Python 3.11.9...
    powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile 'temp\python-installer.exe'"
    if exist "temp\python-installer.exe" (
        echo Installing Python ^(this may take a moment^)...
        temp\python-installer.exe /quiet InstallAllUsers=1 PrependPath=1
        echo [OK] Python installed successfully
        echo [INFO] Restarting script to apply new PATH...
        if exist "temp" rmdir /s /q "temp"
        timeout /t 3 /nobreak >nul
        start "" "%~f0"
        exit
    )
)

:: pip verification and update
echo [2/5] Checking pip...
pip --version >nul 2>&1
if !errorLevel! == 0 (
    echo [OK] pip available - Updating...
    python -m pip install --upgrade pip
) else (
    python -m ensurepip --upgrade
    python -m pip install --upgrade pip
)

:: Python dependencies installation
echo [3/5] Installing dependencies...
if exist "requirements.txt" (
    pip install -r requirements.txt
) else (
    pip install yt-dlp>=2023.12.30 yt-dlp-ejs>=0.4.0 Pillow>=10.0.0 PySide6>=6.5.0 mutagen>=1.47.0
)

:: FFmpeg installation
echo [4/5] Installing FFmpeg...
ffmpeg -version >nul 2>&1
if !errorLevel! neq 0 (
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

:: Deno installation
echo [5/5] Installing Deno ^(JavaScript runtime for YouTube signature solving^)...
deno --version >nul 2>&1
if !errorLevel! neq 0 (
    echo Downloading and installing Deno...
    powershell -Command "irm https://deno.land/install.ps1 | iex" >nul 2>&1
    if exist "%USERPROFILE%\.deno\bin" set "PATH=%USERPROFILE%\.deno\bin;%PATH%"
    deno --version >nul 2>&1
    if !errorLevel! == 0 (
        echo [OK] Deno installed successfully
    ) else (
        echo [WARN] Deno installation may have failed
        echo [INFO] Install Deno manually: https://deno.land/#installation
    )
) else (
    echo [OK] Deno is already installed
)

echo [OK] Installation completed!
echo.

:launch
:: Add FFmpeg to PATH
if exist "ffmpeg\bin" set "PATH=%CD%\ffmpeg\bin;%PATH%"

:: Add Deno to PATH
if exist "%USERPROFILE%\.deno\bin" set "PATH=%USERPROFILE%\.deno\bin;%PATH%"

:: Check for updates from GitHub
call :check_updates

:: Update yt-dlp (critical to avoid 403 errors from YouTube)
call :update_ytdlp

:: Final verification before launch
python --version >nul 2>&1
if !errorLevel! neq 0 (
    echo [ERROR] Python not accessible - Relaunch after restart
    pause
    exit /b 1
)

echo Launching yt-dlp Convenient GUI...
echo.
python run.py
set launch_error=!errorLevel!
echo.
if !launch_error! neq 0 (
    echo [ERROR] Launch error (code: !launch_error!)
    echo.
    echo If the problem persists, check that all dependencies are installed:
    echo   pip install -r requirements.txt
)
echo.
echo Press any key to close this window...
pause >nul
goto :eof

:check_updates
:: Check if Git is installed, offer to install if not
git --version >nul 2>&1
if !errorLevel! == 0 goto :git_available
echo [INFO] Git is not installed.
echo [INFO] Installing Git allows the app to automatically download updates.
set /p "install_git=Install Git? (Y/n): "
if /i "!install_git!"=="n" (
    echo [SKIP] Skipping update check
    echo.
    goto :eof
)
call :install_git
git --version >nul 2>&1
if !errorLevel! neq 0 (
    echo [SKIP] Git not available, skipping update check
    echo.
    goto :eof
)

:git_available
:: Set up Git repository if not already one
git rev-parse --is-inside-work-tree >nul 2>&1
if !errorLevel! == 0 goto :repo_available
echo [INFO] Setting up Git repository for automatic updates...
git init >nul 2>&1
git remote add origin https://github.com/Nicolas-Gth/yt-dlp-convenient-GUI.git >nul 2>&1
git fetch origin >nul 2>&1
echo [OK] Fetched remote repository
echo [INFO] Applying latest version and restarting...
call :write_updater "checkout"
exit

:repo_available
echo Checking for updates...
git fetch origin >nul 2>&1
if !errorLevel! neq 0 (
    echo [SKIP] Could not reach GitHub ^(no internet?^)
    goto :eof
)
for /f %%a in ('git rev-parse HEAD') do set "LOCAL=%%a"
set "REMOTE="
for /f %%a in ('git rev-parse origin/main 2^>nul') do set "REMOTE=%%a"
if not defined REMOTE (
    for /f %%a in ('git rev-parse origin/master 2^>nul') do set "REMOTE=%%a"
)
if not defined REMOTE (
    echo [SKIP] Could not determine remote branch
    goto :eof
)
if "!LOCAL!"=="!REMOTE!" (
    echo [OK] Already up to date
) else (
    set "BEHIND="
    for /f %%a in ('git rev-list --count HEAD..origin/main 2^>nul') do set "BEHIND=%%a"
    if not defined BEHIND (
        for /f %%a in ('git rev-list --count HEAD..origin/master 2^>nul') do set "BEHIND=%%a"
    )
    echo [UPDATE] !BEHIND! new commit^(s^) available
    set /p "update_response=Update now? (Y/n): "
    if /i not "!update_response!"=="n" (
        rem Save requirements hash before update for comparison after restart
        if exist "requirements.txt" (
            for /f "tokens=*" %%h in ('certutil -hashfile requirements.txt MD5 2^>nul ^| findstr /v ":" ^| findstr /v "CertUtil"') do set "_hash=%%h"
            echo !_hash!>".req_hash_before"
        )
        rem Use trampoline script to avoid run.bat being overwritten mid-execution
        echo [INFO] Updating and restarting...
        call :write_updater "reset"
        exit
    ) else (
        echo [SKIP] Update skipped
    )
)
echo.
goto :eof

:install_git
echo Installing Git...
:: Try winget first (Windows 10/11)
where winget >nul 2>&1
if !errorLevel! neq 0 goto :install_git_download
winget install --id Git.Git -e --accept-source-agreements --accept-package-agreements >nul 2>&1
if !errorLevel! neq 0 goto :install_git_download
set "PATH=!PATH!;C:\Program Files\Git\bin;C:\Program Files\Git\cmd"
echo [OK] Git installed via winget
goto :eof

:install_git_download
if not exist "temp" mkdir temp
echo Downloading Git for Windows...
powershell -Command "$ProgressPreference='SilentlyContinue'; try { $r=Invoke-RestMethod 'https://api.github.com/repos/git-for-windows/git/releases/latest'; $a=$r.assets|Where-Object{$_.name -match '64-bit\.exe$' -and $_.name -notmatch 'portable'}|Select-Object -First 1; Invoke-WebRequest -Uri $a.browser_download_url -OutFile 'temp\git-installer.exe' } catch { exit 1 }"
if not exist "temp\git-installer.exe" (
    echo [ERROR] Could not download Git installer
    echo [INFO] You can install Git manually from: https://git-scm.com/download/win
    goto :eof
)
echo Installing Git ^(this may take a moment^)...
temp\git-installer.exe /VERYSILENT /NORESTART /NOCANCEL /SP- /CLOSEAPPLICATIONS /RESTARTAPPLICATIONS /COMPONENTS="icons,ext\reg\shellhere,assoc,assoc_sh"
set "PATH=!PATH!;C:\Program Files\Git\bin;C:\Program Files\Git\cmd"
del "temp\git-installer.exe" >nul 2>&1
echo [OK] Git installed
goto :eof

:write_updater
set "_mode=%~1"
set "_bat=%~dp0_updater.bat"
echo @echo off>"!_bat!"
echo cd /d "%~dp0">>"!_bat!"
echo ping -n 2 127.0.0.1 ^>nul>>"!_bat!"
if "!_mode!"=="checkout" (
    echo git checkout -f main>>"!_bat!"
    echo if errorlevel 1 git checkout -f master>>"!_bat!"
) else (
    echo git reset --hard origin/main>>"!_bat!"
    echo if errorlevel 1 git reset --hard origin/master>>"!_bat!"
)
echo echo [OK] Done. Restarting...>>"!_bat!"
echo ping -n 2 127.0.0.1 ^>nul>>"!_bat!"
echo start "" "%~f0">>"!_bat!"
echo del "%%~f0" ^& exit>>"!_bat!"
start /min "" "!_bat!"
goto :eof

:update_ytdlp
:: Check if requirements changed after a git update
set "_req_changed=0"
if exist ".req_hash_before" (
    set /p "_old_hash="<".req_hash_before"
    del ".req_hash_before" >nul 2>&1
    if exist "requirements.txt" (
        for /f "tokens=*" %%h in ('certutil -hashfile requirements.txt MD5 2^>nul ^| findstr /v ":" ^| findstr /v "CertUtil"') do set "_new_hash=%%h"
        if not "!_old_hash!"=="!_new_hash!" set "_req_changed=1"
    )
)
if !_req_changed! == 1 (
    echo Dependencies changed, updating all Python packages...
    if exist "requirements.txt" (
        pip install -r requirements.txt >nul 2>&1
    )
    if !errorLevel! == 0 (
        echo [OK] All Python dependencies updated
    ) else (
        echo [WARN] Could not update some dependencies
    )
) else (
    echo Checking for yt-dlp updates...
    pip install --upgrade yt-dlp yt-dlp-ejs >nul 2>&1
    if !errorLevel! == 0 (
        echo [OK] yt-dlp is up to date
    ) else (
        echo [WARN] Could not update yt-dlp
    )
)
echo.
goto :eof
