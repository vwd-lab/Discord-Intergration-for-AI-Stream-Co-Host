# Changelog — sharing\Discord (MIT)

Canonical working copy at `C:\Users\bbsti\AI Projects\Project AI Logan\sharing\Discord`.

Framework-agnostic Discord text + voice bridge. Transport-only: ships no brain,
persona, TTS, or voice. Calls your `on_text(display, formatted, channel_id)`
callback for every gated message; optionally posts replies back to Discord.

This is not a git repository, so versions are tracked here by date instead of commit hash.

## 2026-10-28 — Initial release

- `discord_gui.py` — tkinter setup GUI (stdlib only, no extra pip install) that writes `DISCORD_BOT_TOKEN`, `DISCORD_TEXT_CHANNEL_IDS`, `DISCORD_VOICE_CHANNEL_ID`, `DISCORD_OWNER_NAME`, `DISCORD_BATCH_SIZE`, `DISCORD_FLUSH_SECONDS`, `DISCORD_VC_LISTEN`, `VOSK_MODEL_PATH`, `WAKE_WORDS`, `WAKE_ACTIVE_WINDOW`, `WAKE_PARTIAL_ARM`, `IGNORED_USERS` to `.env`; launches `demo_main.py` as a subprocess and streams its log.
- `setup_discord_gui.bat` / `start_discord_gui.bat` — interactive setup and launcher.
- `demo_main.py` — Discord gateway bridge template. Owns its own `discord.Client` connection; reads gated messages and calls `on_text()`.
- `config.example.json` — example configuration.
- `LICENSE` — MIT (copyright-notice retention guarantees attribution downstream).
- `README.md` — setup sequence, `on_text()` callback contract, Radeon AI Co-Host vs custom-framework plug-in instructions.
- `config.py` / `config.example.json` — companion config helpers.

## Planned

- (none yet — log changes here as they land)
