# Discord Bridge — Integration Guide

`input/discord_bot.py` is a standalone Discord **text + voice** bridge you can
drop into any Python bot. It has no imports from a host framework and reads no
config or environment variables itself — everything is passed to the
constructor. `config.py` and `demo_main.py` are example scaffolding for the demo
only.

Contents:

- [Gateway ownership (read this first)](#gateway-ownership-read-this-first)
- [Minimal wiring](#minimal-wiring)
- [Constructor reference](#constructor-reference)
- [Callbacks](#callbacks)
- [Public methods](#public-methods)
- [Text gating rules](#text-gating-rules)
- [Voice behaviour](#voice-behaviour)
- [Layout and imports](#layout-and-imports)
- [Troubleshooting](#troubleshooting)

## Gateway ownership (read this first)

The bridge owns its own `discord.Client` and opens its own gateway connection
(`client.start(token)`).

- A bot token can have only **one live gateway session**. If your host bot
  already runs a `discord.py` client with the same token, the two clients will
  keep disconnecting each other.
- Use a **separate bot application/token** for the bridge, or let the bridge be
  your only Discord client and feed its `on_text` into your brain (the demo
  pattern).
- Attaching the bridge to an existing `discord.Client` is not supported by this
  standalone build.

You also need the **Message Content** intent enabled for the bot in the Discord
Developer Portal (the bridge requests it, but Discord requires the portal
toggle).

## Minimal wiring

```python
import os
from input.discord_bot import DiscordBridge

def on_text(display, formatted, channel_id=None):
    # Called from two threads:
    #  - text messages: the bridge's event loop thread, with channel_id
    #  - VC speech:     the voice reader thread, without channel_id
    # Keep it fast and thread-safe; hand off to your own queue/brain.
    my_inbox.put((display, formatted, channel_id))

bridge = DiscordBridge(
    token=os.environ["DISCORD_BOT_TOKEN"],
    allowed_channel_ids=[111111111111111111],
    mention_name="My Bot",          # "my bot ..." also triggers the gate
    command_prefix="!",             # "!cmd ..." triggers the gate
    ignored_users={"my_other_bot"},
    on_text=on_text,
)

bridge.start()
bridge.wait_ready(15)
bridge.send_text("Bridge online.")
```

For voice-channel listening, additionally pass `vc_listen=True` and a loaded
Vosk model as `voice_model` (see `demo_main.build_voice_model`).

## Constructor reference

| Argument | Default | Purpose |
|---|---|---|
| `token` | required | Bot token. |
| `allowed_channel_ids` | required | Text channels the bridge will read from. Ints or numeric strings. |
| `mention_name` | `"Bot Name"` | Bare keyword that gates a message (case-insensitive, whole word). |
| `command_prefix` | `"!ask"` | Prefix that gates `"<prefix> text"` (the prefix is stripped). |
| `owner_name` | `None` | Accepted for signature compatibility; **not used** by the standalone bridge. |
| `ignored_users` | `()` | Display names (case-insensitive) to ignore entirely. |
| `on_text` | `None` | Main callback for gated text and VC speech. |
| `on_ambient` | `None` | Optional callback for every non-bot message in allowed channels, gated or not. |
| `voice_model` | `None` | A loaded `vosk.Model`; required for VC listening. |
| `vc_listen` | `False` | Enable wake-word listening when joining a VC. |
| `vc_wake_words` | `()` | Wake phrases, lower-case. |
| `vc_active_window` | `8` | Seconds a conversation stays open after a wake word. |
| `vc_busy_fn` | `None` | Cheap `() -> bool`; return True while your bot is playing local audio. |
| `vc_wake_arm` | `False` | Arm on half-heard partial wake matches (earlier, more false positives). |

## Callbacks

### `on_text(display, formatted, channel_id=None)`

Called with two different argument counts:

| Source | Call | Thread |
|---|---|---|
| Gated text message | `on_text(display, formatted, channel_id)` | bridge event loop |
| VC wake-word speech | `on_text(display, formatted)` | voice reader |

`display` is the author's display name. `formatted` is ready to log:

- text: `[Discord viewer 'Name' says]: message`
- voice: `[Discord VC viewer 'Name' says]: message` (or `... says] (live): ...`
  for partials)

`channel_id` is the originating text channel for text messages, and `None` for
VC speech. Because of the two call sites, define it as
`def on_text(display, formatted, channel_id=None)`.

Keep the callback fast and thread-safe: enqueue the work and let your own loop
process it. Do not call blocking network/LLM code directly from it.

### `on_ambient(display, content)`

Optional. Called for **every** non-bot message in an allowed channel, before
gating, with the raw content. Also from the bridge event loop. Useful for
"lurking"/context collection; keep it cheap.

### `vc_busy_fn()`

Optional. Called from the voice reader thread (per audio frame). Return `True`
while your bot is audibly playing local audio so the listener does not treat it
as speech. Must be cheap and thread-safe.

## Public methods

All of these are safe to call from any thread.

| Method | Returns | Notes |
|---|---|---|
| `start()` | — | Starts the client on a daemon thread. |
| `wait_ready(timeout=15)` | `bool` | Blocks until logged in. |
| `send_text(text, channel_id=None)` | — | Posts to one channel, or to **all** allowed channels when `channel_id` is `None`. Splits at 1900 chars. |
| `join_voice(target="")` | `bool` | `target` = voice channel ID, name (leading `#` ok, case-insensitive), or `""` for the first VC in the first guild. Needs Connect + Speak. |
| `leave_voice()` | `bool` | Disconnects and stops the listener. |
| `in_voice()` | `bool` | Currently connected to a VC. |
| `play_in_vc(wav_path, delete_when_done=True)` | `bool` | Queues a WAV for VC playback (one at a time, in order). Needs FFmpeg on `PATH`. Deletes the file after playing by default. |

Notes:

- `join_voice` / `leave_voice` / `in_voice` operate on the **first guild** the
  bot is in.
- `play_in_vc` is a no-op returning `False` when not in a VC or not ready.
- The bridge does not batch messages; every gated message calls `on_text`
  immediately. Batch in your own pipeline if you need it.

## Text gating rules

A message is delivered only when **all** of these are true:

1. It is in a guild (DMs are ignored).
2. Its channel is in `allowed_channel_ids`.
3. The author is not a bot.
4. The author's display name is not in `ignored_users`.
5. It either mentions the bot (`@Bot`), contains `mention_name` as a whole
   word, or starts with `<command_prefix> ` (the prefix is removed).

A bare command prefix with no text is ignored. `mention_name` occurrences are
stripped from the delivered text.

## Voice behaviour

- **Out:** `play_in_vc` plays WAVs via `FFmpegOpusAudio`, serialized through a
  queue. Clips are cleaned up (deleted by default) after playback.
- **In:** with `vc_listen=True` and a `voice_model`, the bridge attaches a Vosk
  sink. Other users' audio is used; the bot's own audio is skipped.
- Wake-word gating is passive until a wake phrase is heard, then open for
  `vc_active_window` seconds (longer while the speaker keeps talking).
- While the bot is playing into the VC, incoming listening is **paused** so its
  own voice cannot loop back through an open mic; it resumes afterwards and
  resets the recognizer (dropping half-heard audio).
- Voice receive uses `discord-ext-voice-recv`; DAVE encryption is handled by
  the bridge automatically.

Prerequisites:

- `discord.py>=2.3`, `discord-ext-voice-recv`, `davey`, `vosk`, `rich`.
- FFmpeg on `PATH` for VC playback.
- Python 3.13 needs `audioop-lts` (the 3.13 stdlib removed `audioop`).

## Layout and imports

The bridge expects this folder structure:

```
your_project/
  input/
    discord_bot.py
    discord_voice_listener.py   # only if using VC listening
```

It is imported as `input.discord_bot`, and loads the sink with
`from input.discord_voice_listener import VoskVoiceSink`.

If your project uses a different package name or layout, update those two
imports. Relative imports (`from .discord_voice_listener import ...`) or
promoting the kit to its own package both work; the current form assumes an
`input/` package at the project root.

The bridge itself does not read `.env` or `config.py`. Those exist only for
`demo_main.py`.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| No messages delivered | Message Content intent off in the Developer Portal, wrong `allowed_channel_ids`, or messages don't mention/keyword/prefix the bot. |
| Bot keeps reconnecting | Two gateway clients using the same token. Use a separate token or one client only. |
| `TypeError: on_text() takes 2 positional arguments` | Your callback must accept `channel_id=None`. |
| No VC audio | FFmpeg missing from `PATH`, or missing Connect/Speak permission. |
| VC listening silent | `vc_listen=False`, `voice_model` is `None`, model path wrong, or wake word not matched. |
| Listener goes deaf after a clip | Update to this build; it pauses/resumes around playback. |
