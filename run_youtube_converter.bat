@echo off

REM Mettre à jour yt_dlp
python -m pip install --upgrade yt_dlp 2>nul
IF ERRORLEVEL 1 (
    echo Erreur lors de la mise à jour de yt_dlp.
    PAUSE
    EXIT /B 1
)

REM Exécuter le script Python
python main.py
IF ERRORLEVEL 1 (
    echo Erreur lors de l'exécution de main.py.
    PAUSE
    EXIT /B 1
)

PAUSE
EXIT /B 0