"""Minimal config loader for the Discord sharing demo.

Loads .env and exposes only the settings the Discord bridge needs.
This is a trimmed copy of the full project's config.py — enough to run
input/discord_bot.py standalone, nothing more.
"""
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # .env optional; env vars read from the OS directly

# --- Discord ---
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "").strip()
DISCORD_TEXT_CHANNEL_IDS = [
    int(x) for x in os.getenv("DISCORD_TEXT_CHANNEL_IDS", "").replace(" ", "").split(",")
    if x.strip().lstrip("-").isdigit()
]
DISCORD_VOICE_CHANNEL_ID = int(os.getenv("DISCORD_VOICE_CHANNEL_ID", "0") or 0)
DISCORD_OWNER_NAME = os.getenv("DISCORD_OWNER_NAME", "").strip()
DISCORD_BATCH_SIZE = max(1, int(os.getenv("DISCORD_BATCH_SIZE", "1")))
DISCORD_FLUSH_SECONDS = int(os.getenv("DISCORD_FLUSH_SECONDS", "30"))
DISCORD_VC_LISTEN = os.getenv("DISCORD_VC_LISTEN", "0") == "1"

# --- Wake words / voice ---
WAKE_WORDS = [w.strip().lower() for w in os.getenv("WAKE_WORDS", "bot name,bot").split(",") if w.strip()]
WAKE_ACTIVE_WINDOW = int(os.getenv("WAKE_ACTIVE_WINDOW", "8"))
WAKE_PARTIAL_ARM = os.getenv("WAKE_PARTIAL_ARM", "0") == "1"

# --- Vosk ---
VOSK_MODEL_PATH = os.getenv(
    "VOSK_MODEL_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "vosk-model-small-en-us"),
)

# --- Other ---
IGNORED_USERS = [u.strip().lower() for u in os.getenv("IGNORED_USERS", "").split(",") if u.strip()]
