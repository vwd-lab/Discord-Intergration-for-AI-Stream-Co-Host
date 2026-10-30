================================================================================
 BOT NAME DISCORD INTEGRATION - STANDALONE SHARE KIT (Option A)
================================================================================

This folder is a bare-bones, plug-and-play version of the Discord integration
used by the Bot Name streamer bot. It gives you the REAL, battle-tested bridge
classes (input/discord_bot.py + input/discord_voice_listener.py) plus a tiny
harness (demo_main.py) showing the exact 5-line setup.

You plug your own bot in by replacing ONE function - on_text() in demo_main.py.

For the full contract (constructor args, callbacks, threading, layout), see
INTEGRATION.md.

--------------------------------------------------------------------------------
 WHAT YOU GET
--------------------------------------------------------------------------------
  input/discord_bot.py            The real DiscordBridge (text gate + VC voice)
  input/discord_voice_listener.py The real Vosk/DAVE voice sink (wake words)
  demo_main.py                    Minimal harness that wires it to YOUR bot
  config.py                       Trimmed config (only Discord settings)
  requirements.txt                Packages needed (incl. the 3 easy-to-miss ones)
  .env.example                    Copy to .env and fill in your values
  COMMANDS.txt                    Every command the bridge understands
  INTEGRATION.md                  Full integration contract (args, callbacks, layout)

--------------------------------------------------------------------------------
 1) SET UP A DISCORD BOT (5-10 minutes)
--------------------------------------------------------------------------------
  a. Go to  https://discord.com/developers/applications  and click
     "New Application". Name it whatever you like (e.g. "Bot Name").
  b. Go to the  BOT  tab  (left menu). Click  "Reset Token" then "Copy".
     This is your DISCORD_BOT_TOKEN. Treat it like a password - never share it.
  c. In the BOT tab, scroll to "Privileged Gateway Intents" and TURN ON:
        MESSAGE CONTENT INTENT      <-- REQUIRED. Without it the bot cannot
                                      see message text and won't work at all.
     ("Server Members" / "Presence" intents are NOT required, leave them off.)
  d. Go to the  OAuth2 > URL Generator  tab. For "Scopes" tick:
        bot
     (No need for applications.commands - the bridge doesn't use slash commands.)
  e. For "Bot Permissions" tick at least:
        Read Messages / View Channels
        Send Messages
        Connect , Speak                <- only if you want voice-channel audio
     For text chat you really only need "View Channels" + "Send Messages".
  f. Copy the generated URL at the bottom, open it in a browser, and add the
     bot to your Discord server. Pick a server and authorize.
  g. ENABLE DEVELOPER MODE in Discord:
        User Settings > Advanced > Developer Mode  (toggle ON)
     Then right-click the text channel (and/or voice channel) you want the bot
     in and choose "Copy Channel ID".

--------------------------------------------------------------------------------
 2) INSTALL (in this folder)
--------------------------------------------------------------------------------
  python -m venv venv
  venv\Scripts\activate           (Windows)
  # or: source venv/bin/activate  (macOS/Linux)
  pip install -r requirements.txt

  ALSO: install FFmpeg and put it on your PATH (https://ffmpeg.org/download.html).
  The bridge uses it to stream audio (FFmpegOpusAudio). Without ffmpeg, VC
  audio playback silently won't work even though text still will.

  ONLY for voice-channel listening: download a Vosk model
  from  https://alphacephei.com/vosk/models  (use "vosk-model-small-en-us").
  Unzip it and set VOSK_MODEL_PATH in .env to that folder.

--------------------------------------------------------------------------------
 3) CONFIGURE .env
--------------------------------------------------------------------------------
  Copy .env.example to .env and fill in:
    DISCORD_BOT_TOKEN        = the token from step 1b
    DISCORD_TEXT_CHANNEL_IDS = channel ID(s) from step 1g (comma-separated)
    DISCORD_OWNER_NAME       = your display name (optional, always replies to you)
    DISCORD_VC_LISTEN        = 1 if you want voice-channel wake-word listening
    VOSK_MODEL_PATH          = path to the unzipped Vosk model (if VC listen)

--------------------------------------------------------------------------------
 4) PLUG IN YOUR BOT
--------------------------------------------------------------------------------
  Open demo_main.py. Replace the body of on_text() with your own logic:

     def on_text(display, formatted, channel_id=None):
         print(f"[magenta]GOT -> {formatted}")
         # --- YOUR CODE HERE ---
         #   display    = author's display name (str)
         #   formatted  = a ready-to-log line, e.g.
         #                "[Discord viewer 'X' says]: hello"
         #   channel_id = ID of the channel it came from (int or None)
         #   To reply in that channel:
         #       bridge.send_text("your reply", channel_id=channel_id)
         #   To speak into a voice channel:
         #       bridge.play_in_vc("clip.wav")
         # --- END YOUR CODE ---

  You can call bridge methods from anywhere (threads, callbacks, your AI loop),
  they are safe to call from any thread:
     bridge.send_text(text[, channel_id])   post a message
     bridge.join_voice("channel-name|id")    join/move to a voice channel
     bridge.leave_voice()                    leave voice
     bridge.in_voice()                       bool: currently in a voice channel?
     bridge.play_in_vc("clip.wav")           play audio in the voice channel
     bridge.wait_ready(timeout=15)           True once logged in

  Integration note: the bridge is imported as `input.discord_bot` and loads the
  voice sink from `input.discord_voice_listener`. Keep this kit's `input/`
  folder at your project root, or update those two imports to match your layout.

--------------------------------------------------------------------------------
 5) RUN
--------------------------------------------------------------------------------
  python demo_main.py

  Then in an allowed channel:
     @Bot Name hello
     !join my-voice-channel        -> bot joins voice (needs Connect/Speak perm)
     !leave                         -> bot leaves voice
     !help                          -> list commands
  While in a voice channel with DISCORD_VC_LISTEN=1, say the wake word (default
  "bot name") then a phrase, e.g. "bot name what time is it" - it routes to on_text().

  While the bot is speaking into the VC, incoming voice listening pauses so its
  own audio is not picked up through someone's open mic; it resumes afterwards.

  The demo harness already handles !join, !leave and !help. Anything else that
  passes the gate (a mention, or any other "!command") is forwarded to on_text()
  for YOU to handle. The demo's command prefix is "!" so your own !commands
  reach your code - change command_prefix in demo_main.py if you want a
  different prefix.

--------------------------------------------------------------------------------
 HOW THE GATE WORKS (so you trust it in your bot)
--------------------------------------------------------------------------------
  DiscordBridge only forwards a message to on_text() when it is "gated":
    - the message is in an allowed channel (DISCORD_TEXT_CHANNEL_IDS)
    - the author is not a bot and not in IGNORED_USERS
    - AND either the bot is @mentioned, OR the message starts with the
      command prefix (the demo uses "!", changeable in demo_main.py).
  Everything else is ignored. This is the exact behavior the full Bot Name bot uses.

--------------------------------------------------------------------------------
 FILE LICENSING / USE
--------------------------------------------------------------------------------
  This is shared from a private project. Use it freely, but do not commit your
  .env or any real tokens. Config values, channel IDs and wake words are yours
  to set per-install.

   Got questions? Ask whoever shared this kit with you.
================================================================================
