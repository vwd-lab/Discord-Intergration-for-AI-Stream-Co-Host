"""
Standalone demo for the Discord integration.

This is a MINIMAL harness that wires the real DiscordBridge
(input/discord_bot.py) to your own bot. It shows the 5-line setup:

    1. load .env
    2. build a Vosk voice model (optional, for VC listening)
    3. create DiscordBridge(...) with an on_text callback
    4. bridge.start()
    5. let the process run

Replace on_text with a call into YOUR bot's brain and you are done.

Run:  python demo_main.py
"""
import os
import sys

import config  # loads .env + exposes all DISCORD_* settings (see config.py)
from input.discord_bot import DiscordBridge

# --------------------------------------------------------------------------
# Optional voice model (wake-word listening in voice channels).
# Only built when DISCORD_VC_LISTEN=1 and VOSK_MODEL_PATH points at a model.
# --------------------------------------------------------------------------
def build_voice_model():
    try:
        from vosk import Model
    except Exception:
        print("[red]Vosk not installed — VC listening disabled. pip install vosk")
        return None
    path = config.VOSK_MODEL_PATH
    if not path or not os.path.isdir(path):
        print(f"[yellow]VOSK_MODEL_PATH not found: {path!r} — VC listening disabled.")
        print("[yellow]Download vosk-model-small-en-us from https://alphacephei.com/vosk/models")
        return None
    print(f"[cyan]Loading Vosk model from {path} ...")
    return Model(path)


# --------------------------------------------------------------------------
# Your bot's brain. Replace this with whatever YOU want to happen when the
# bridge hears a gated message or a VC wake-word utterance.
#   display   : the author's display name (str)
#   formatted : a ready-to-log line like:
#               "[Discord viewer 'X' says]: your text"
#   channel_id: the ID of the channel the message came from (int or None) —
#               pass it to bridge.send_text(...) to reply in-channel only
# --------------------------------------------------------------------------
def on_text(display, formatted, channel_id=None):
    print(f"[magenta]GOT -> {formatted}")

    # ---- built-in demo commands (handle these, don't forward to your bot) ----
    line = formatted.split("]: ", 1)[-1] if "]:" in formatted else formatted
    low = line.strip().lower()
    if low.startswith("!help"):
        bridge.send_text("Commands: !join <vc> , !leave , !ask <msg> , @me <msg>",
                         channel_id=channel_id)
        return
    if low.startswith("!join"):
        target = line.split(" ", 1)[1].strip() if " " in line else ""
        ok = bridge.join_voice(target)
        bridge.send_text("Joined voice." if ok else "Could not join voice.",
                         channel_id=channel_id)
        return
    if low == "!leave":
        bridge.leave_voice()
        bridge.send_text("Left voice.", channel_id=channel_id)
        return
    # ---------------------------------------------------------------------

    # --- REPLACE FROM HERE WITH YOUR OWN LOGIC ---
    # A trivial example: reply in the SAME channel the message came from
    # (channel_id is the originating channel; omit it to broadcast instead).
    if "VC viewer" not in formatted:
        reply = f"Hello {display}! You said: {line}"
        print(f"[green]Replying -> {reply}")
        bridge.send_text(reply, channel_id=channel_id)
    # --- REPLACE UP TO HERE ---


if __name__ == "__main__":
    if not config.DISCORD_BOT_TOKEN or "PASTE_YOUR" in config.DISCORD_BOT_TOKEN:
        print("[red]No DISCORD_BOT_TOKEN set. Copy .env.example to .env and fill it in.")
        sys.exit(1)
    if not config.DISCORD_TEXT_CHANNEL_IDS:
        print("[red]No DISCORD_TEXT_CHANNEL_IDS set. Add at least one channel ID to .env.")
        sys.exit(1)

    voice_model = build_voice_model() if config.DISCORD_VC_LISTEN else None

    bridge = DiscordBridge(
        token=config.DISCORD_BOT_TOKEN,
        allowed_channel_ids=config.DISCORD_TEXT_CHANNEL_IDS,
        # Prefix "!" lets every !command (demo !join/!leave/!help AND your own
        # !commands) pass the gate into on_text(); mentions work too.
        mention_name="Bot Name",
        command_prefix="!",
        owner_name=config.DISCORD_OWNER_NAME,
        ignored_users=config.IGNORED_USERS,
        on_text=on_text,
        voice_model=voice_model,
        vc_listen=config.DISCORD_VC_LISTEN,
        vc_wake_words=config.WAKE_WORDS,
        vc_active_window=config.WAKE_ACTIVE_WINDOW,
        vc_wake_arm=config.WAKE_PARTIAL_ARM,
    )
    bridge.start()

    print("[cyan]Discord bridge running. Press Ctrl+C to stop.")
    print("[cyan]In an allowed channel: @Bot Name <msg>, or '!join' to enter a voice channel.")
    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        bridge.leave_voice()
        print("[red]Stopped.")
