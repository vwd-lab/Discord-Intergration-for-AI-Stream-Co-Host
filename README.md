# This is a Beta intergrations add-on
While this was designed for my AI Stream Co-Host framework, I tried to make it so this could be added to any AI Stream Co-Host framework. Feedback would be appricated to help improve it and make it better.

# Discord AI Bridge

Framework-agnostic Discord text + voice bridge. Receive Discord chat messages
and hand them to **any** bot — Radeon AI Co-Host, a custom Python bot, Node
bot, or anything else that can accept a callback.

The kit is **transport-only**: it ships no brain, persona, TTS, or voice
support. It owns its own `discord.Client` gateway connection, reads gated
messages, and (optionally) posts replies back into Discord text channels or
voice channel audio.

## Universal integration point

The bridge calls your `on_text(display, formatted, channel_id)` callback for
every gated message:

- `display` — the author's display name
- `formatted` — ready-to-log line like
  `"[Discord viewer 'Name' says]: hello bot"`
- `channel_id` — the originating text channel ID (int, or `None` for VC speech)

Your bot drains those callbacks and routes them through its own brain —
identical to how Twitch chat is handled. That is the universal plug.

## Plugging in

### Option A: Radeon AI Co-Host

Route `on_text` into `Radeon AI Co-Host/main.py`'s `process_message()` exactly
like Twitch chat, using `discord:<username>` as the namespaced username.

### Option B: Any custom framework

Use `demo_main.py` as the template. Replace `on_text(display, formatted,
channel_id=None)` with a call into your own brain:

```python
def on_text(display, formatted, channel_id=None):
    text = formatted.split("]: ", 1)[-1] if "]:" in formatted else formatted
    reply_text = my_bot.answer(display, text)   # YOUR framework
    bridge.send_text(reply_text, channel_id=channel_id)
```

The `bridge.send_text()` helper posts to one channel, or to all allowed
channels when `channel_id` is `None`.

## The bridge

| Feature | What it does |
|---|---|
| Text gateway | Owns a `discord.Client`, reads gated messages from allowed channels |
| Gating | Mentions, keyword match, or `!prefix` — DMs and bots ignored |
| Voice out | `send_text()` posts replies; `play_in_vc()` plays WAVs in a VC |
| Voice in | Vosk wake-word listening when joined to a VC (`vc_listen=True`) |
| Batching | None — every gated message calls `on_text` immediately; batch in your own pipeline |

## Setup you'll still need

### 1. Create a Discord bot application
Go to https://discord.com/developers/applications, create a new app, go to the
**Bot** tab, and copy the **Token**. Treat it like a password.

### 2. Enable required intents
In the Developer Portal, under your bot's **Privileged Gateway Intents**, enable
**Message Content Intent** (required to read message text).

### 3. Invite the bot to your server
Use the OAuth2 URL generator with the `bot` and `applications.commands` scopes,
and give it the permissions you need (Read Messages, Send Messages, etc.).

### 4. Get channel IDs
Enable **Developer Mode** in Discord (Settings > Advanced), right-click a text
channel, and choose **Copy Channel ID**. Add those IDs to your config.

### 5. Configure `.env`
Copy `.env.example` to `.env` and fill in at minimum:

```
DISCORD_BOT_TOKEN=your-bot-token
DISCORD_TEXT_CHANNEL_IDS=111111111111111111,222222222222222222
```

### 6. Launch

**First run (recommended):** double-click `setup_discord_gui.bat`. It prompts
for your token, channel IDs, voice settings, and Vosk path, writes `.env`, then
opens `discord_gui.py` where you can start/stop the bridge.

**Subsequent runs:** double-click `start_discord_gui.bat` (reuses `.env`), or
run directly:

```bat
python demo_main.py
```

## Files

| File | Purpose |
|---|---|
| `demo_main.py` | Production wiring harness (Discord bridge → your `on_text()` → replies) |
| `discord_gui.py` | tkinter GUI launcher (stdlib only) |
| `setup_discord_gui.bat` | Interactive setup: prompts, writes `.env`, launches GUI |
| `start_discord_gui.bat` | Double-click launcher (uses existing `.env`) |
| `config.json` | Your saved configuration (GUI tracking) |
| `config.example.json` | Config template |
| `.env` | Your runtime configuration (created at runtime, git-ignored) |
| `.env.example` | Config template |
| `input/discord_bot.py` | Discord text + voice bridge (gateway client) |
| `input/discord_voice_listener.py` | Vosk voice sink for VC listening |
| `requirements.txt` | Python dependencies |

## Requirements

- Python 3
- `pip install discord.py discord-ext-voice-recv davey vosk rich`
- FFmpeg on `PATH` for VC playback (`play_in_vc`)

The GUI (`discord_gui.py`) uses tkinter only, so no extra packages are needed
to launch.

## Gateway ownership

The bridge owns its own `discord.Client` and opens its own gateway connection.
A bot token can have only **one live gateway session**. If your host bot
already runs a `discord.py` client with the same token, the two clients will
keep disconnecting each other. Use a separate bot token for the bridge, or let
the bridge be your only Discord client.

## License

This kit is released under the [MIT License](LICENSE). You are free to use,
copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
the software.

The one requirement is attribution: the copyright notice and license text must
be retained in all copies or substantial portions of the software, so the
original creator (the Radeon AI Co-Host authors) stays credited no matter how
far downstream the code is shared.
