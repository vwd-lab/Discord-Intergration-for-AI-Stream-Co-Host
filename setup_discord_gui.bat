@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

REM ========================================================================
REM Discord Bridge Setup - interactive configuration before launching discord_gui
REM ========================================================================
REM Prompts for your Discord bot settings, writes .env, then launches
REM discord_gui.py so you can start/stop the bridge from the GUI.
REM ========================================================================

set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

echo.
echo ============================================================
echo   Discord Bridge Setup
echo ============================================================
echo.

set "TOKEN="
set /p TOKEN="Discord bot token (from Developer Portal > Bot > Token): "

set "CHANNELS="
set /p CHANNELS="Allowed text channel IDs (comma-separated): "

set "OWNER="
set /p OWNER="Owner display name (press Enter to skip): "

set "BATCH="
set /p BATCH="Batch size (default 1): "
if not defined BATCH set BATCH=1

set "FLUSH="
set /p FLUSH="Flush seconds (default 30): "
if not defined FLUSH set FLUSH=30

set "VC_ID="
set /p VC_ID="Voice channel ID to auto-join (press Enter to skip): "

set "VC_LISTEN="
set /p VC_LISTEN="Enable VC listening? [yes/no] (default no): "
if not defined VC_LISTEN set VC_LISTEN=no

set "VOSK_PATH="
set /p VOSK_PATH="Vosk model path (default models/vosk-model-small-en-us): "
if not defined VOSK_PATH set VOSK_PATH=models/vosk-model-small-en-us

set "WAKE_WORDS="
set /p WAKE_WORDS="Wake words (default bot name,bot): "
if not defined WAKE_WORDS set WAKE_WORDS=bot name,bot

set "WAKE_WINDOW="
set /p WAKE_WINDOW="Active window seconds (default 8): "
if not defined WAKE_WINDOW set WAKE_WINDOW=8

set "PARTIAL_ARM="
set /p PARTIAL_ARM="Partial arm? [yes/no] (default no): "
if not defined PARTIAL_ARM set PARTIAL_ARM=no

set "IGNORED="
set /p IGNORED="Ignored users (comma-separated, press Enter to skip): "

REM Write .env via Python for safe quoting
%PY% -c "
import json, os

token  = os.environ.get('TOKEN', '').strip()
channels = os.environ.get('CHANNELS', '').strip()
owner  = os.environ.get('OWNER', '').strip()
batch  = os.environ.get('BATCH', '1').strip() or '1'
flush  = os.environ.get('FLUSH', '30').strip() or '30'
vc_id  = os.environ.get('VC_ID', '').strip()
vc_listen = os.environ.get('VC_LISTEN', 'no').strip().lower() in ('1', 'y', 'yes', 'true')
vosk   = os.environ.get('VOSK_PATH', 'models/vosk-model-small-en-us').strip() or 'models/vosk-model-small-en-us'
wake   = os.environ.get('WAKE_WORDS', 'bot name,bot').strip() or 'bot name,bot'
window = os.environ.get('WAKE_WINDOW', '8').strip() or '8'
partial= os.environ.get('PARTIAL_ARM', 'no').strip().lower() in ('1', 'y', 'yes', 'true')
ignored= os.environ.get('IGNORED', '').strip()

env = {
    'DISCORD_BOT_TOKEN': token,
    'DISCORD_TEXT_CHANNEL_IDS': channels,
    'DISCORD_VOICE_CHANNEL_ID': vc_id,
    'DISCORD_OWNER_NAME': owner,
    'DISCORD_BATCH_SIZE': batch,
    'DISCORD_FLUSH_SECONDS': flush,
    'DISCORD_VC_LISTEN': '1' if vc_listen else '0',
    'VOSK_MODEL_PATH': vosk,
    'WAKE_WORDS': wake,
    'WAKE_ACTIVE_WINDOW': window,
    'WAKE_PARTIAL_ARM': '1' if partial else '0',
    'IGNORED_USERS': ignored,
}

with open('.env', 'w', encoding='utf-8') as f:
    for k, v in env.items():
        f.write(f'{k}={v}\n')

print('.env written.')
"

echo.
echo ============================================================
echo   Setup complete. Launching Discord GUI...
echo ============================================================
echo.

"%PY%" discord_gui.py
pause
endlocal
