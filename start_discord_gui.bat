@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

REM Discord Bridge launcher
REM -----------------------
REM Starts discord_gui.py as a subprocess. The GUI shows the live log and lets
REM you configure token, channels, voice, and Vosk settings.

set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

if not exist ".env" (
    echo [discord] .env not found. Run setup_discord_gui.bat first to configure.
    pause
    exit /b 1
)

echo Starting Discord AI Bridge...
"%PY%" discord_gui.py
pause
endlocal
