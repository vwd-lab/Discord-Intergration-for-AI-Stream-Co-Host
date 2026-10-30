import asyncio
import collections
import os
import re
import threading

import discord
from discord.ext import voice_recv
from rich import print


class _DaveDecryptPatch:
    def __init__(self, vc):
        self._vc = vc
        self._conn = vc._connection
        self._err_count = 0
        self._MediaType = None
        try:
            from davey import MediaType as _MT
            self._MediaType = _MT
        except Exception:
            pass

    def patch(self):
        if self._MediaType is None:
            return
        self._safe_decode_patch()
        for reader in self._iter_readers():
            if reader.active and not hasattr(reader, '_dave_patched'):
                self._patch_reader(reader)

    def _safe_decode_patch(self):
        from discord.ext.voice_recv import opus as _vo
        if not hasattr(_vo.PacketDecoder, '_dave_safe_patched'):
            _orig = _vo.PacketDecoder._decode_packet
            def _safe(self_pd, packet):
                try:
                    return _orig(self_pd, packet)
                except Exception:
                    counter = getattr(_vo.PacketDecoder, '_dave_decode_err', 0)
                    _vo.PacketDecoder._dave_decode_err = counter + 1
                    pcm = b"\x00\x00" * 960 * 2
                    return packet, pcm
            _vo.PacketDecoder._decode_packet = _safe
            _vo.PacketDecoder._dave_safe_patched = True

    def _iter_readers(self):
        reader = self._vc._reader
        if reader:
            yield reader

    def _patch_reader(self, reader):
        reader._dave_patched = True
        orig = reader.callback
        conn = self._vc._connection

        def _dave_callback(packet_data: bytes):
            try:
                if not voice_recv.rtp.is_rtcp(packet_data):
                    rtp_packet = voice_recv.rtp.decode_rtp(packet_data)
                    rtp_packet.decrypted_data = reader.decryptor.decrypt_rtp(rtp_packet)
                    self._dave_unwrap(reader, rtp_packet)
                else:
                    rtcp_packet = voice_recv.rtp.decode_rtcp(reader.decryptor.decrypt_rtcp(packet_data))
                    reader.packet_router.feed_rtcp(rtcp_packet)
                    return
            except Exception:
                if reader._is_ip_discovery_packet(packet_data):
                    return
                return

            ssrc = rtp_packet.ssrc
            if ssrc not in self._vc._ssrc_to_id:
                if rtp_packet.is_silence():
                    return
                else:
                    reader.speaking_timer.notify(ssrc)
                    return

            reader.speaking_timer.notify(ssrc)
            try:
                reader.packet_router.feed_rtp(rtp_packet)
            except Exception as e:
                reader.error = e
                reader.stop()

        reader.callback = _dave_callback
        try:
            conn.remove_socket_listener(orig)
            conn.add_socket_listener(_dave_callback)
        except Exception as e:
            print(f"  [red]callback rebind error: {e}")

    def _dave_unwrap(self, reader, rtp_packet):
        session = self._conn.dave_session
        ssrc = rtp_packet.ssrc
        user_id = self._vc._ssrc_to_id.get(ssrc)

        if not (session and session.ready and user_id):
            return

        try:
            if session.can_passthrough(int(user_id)):
                return
        except Exception:
            pass

        try:
            rtp_packet.decrypted_data = session.decrypt(
                int(user_id), self._MediaType.audio, rtp_packet.decrypted_data
            )
        except Exception as e:
            msg = str(e)
            if "Unencrypted" in msg or "Passthrough" in msg:
                return
            self._err_count += 1
            if self._err_count <= 10:
                print(f"  [red]DAVE decrypt error: {e}")


class DiscordBridge:
    """Runs a discord.py client in a daemon thread. Gated text events are
    pushed to on_text(display_name, formatted_text, channel_id); voice
    join/leave and VC playback are scheduled onto the client's event loop
    from other threads."""

    def __init__(self, token, allowed_channel_ids, mention_name="Bot Name",
                 command_prefix="!ask", owner_name=None, ignored_users=(), on_text=None,
                 on_ambient=None, voice_model=None, vc_listen=False,
                 vc_wake_words=(), vc_active_window=8, vc_busy_fn=None,
                 vc_wake_arm=False):
        self.token = token
        self.allowed_channel_ids = set(allowed_channel_ids)
        self.mention_name = (mention_name or "Bot Name").lower()
        self.command_prefix = command_prefix.lower()
        self.owner_name = (owner_name or "").lower()
        self.ignored_users = {u.strip().lower() for u in ignored_users if u.strip()}
        self.on_text = on_text
        self.on_ambient = on_ambient
        self._loop = None
        self._ready = threading.Event()

        self._voice_model = voice_model
        self._vc_listen = vc_listen
        self._vc_wake_words = list(vc_wake_words or [])
        self._vc_active_window = vc_active_window
        self._vc_busy_fn = vc_busy_fn
        self._vc_wake_arm = vc_wake_arm
        self._voice_sink = None
        self._vc_queue = collections.deque()
        self._vc_current = None
        self._vc_listen_paused = False

        intents = discord.Intents.default()
        intents.message_content = True
        self.client = discord.Client(intents=intents)
        self.client.event(self.on_ready)
        self.client.event(self.on_message)

    @staticmethod
    def _strip_mentions(content):
        return re.sub(r"<@!?\d+>", "", content).strip()

    def _is_gated(self, message):
        """Returns cleaned text when the message targets the bot, else None."""
        if getattr(message, "guild", None) is None:
            return None
        if message.channel.id not in self.allowed_channel_ids:
            return None
        if getattr(message.author, "bot", False):
            return None
        author = str(message.author.display_name)
        if author.lower() in self.ignored_users:
            return None
        cleaned = self._strip_mentions(message.content)
        mentioned = bool(self.client.user and self.client.user in message.mentions)
        keyword_re = re.compile(rf"\b{re.escape(self.mention_name)}\b", re.IGNORECASE)
        has_keyword = bool(keyword_re.search(cleaned))
        if not mentioned and not has_keyword:
            low = cleaned.lower()
            if low.startswith(self.command_prefix + " "):
                cleaned = cleaned[len(self.command_prefix) + 1:].strip()
            elif low == self.command_prefix:
                return None
            else:
                return None
        if has_keyword:
            cleaned = keyword_re.sub("", cleaned).strip()
        return cleaned or None

    async def on_ready(self):
        self._loop = asyncio.get_running_loop()
        user = self.client.user
        print(f"[green]Discord connected as {user} (id {user.id})")
        print(f"[green]Listening in channel(s): {sorted(self.allowed_channel_ids)}")
        self._ready.set()

    async def on_message(self, message):
        try:
            if self.on_ambient and getattr(message, "guild", None) is not None \
                    and message.channel.id in self.allowed_channel_ids \
                    and not getattr(message.author, "bot", False) \
                    and str(message.author.display_name).lower() not in self.ignored_users:
                try:
                    self.on_ambient(str(message.author.display_name), message.content or "")
                except Exception as e:
                    print(f"[red]Ambient hook error: {e}")

            cleaned = self._is_gated(message)
            if not cleaned:
                return
            display = str(message.author.display_name)
            formatted = f"[Discord viewer '{display}' says]: {cleaned}"
            print(f"[magenta][Discord] {display}: {cleaned}")
            if self.on_text:
                self.on_text(display, formatted, message.channel.id)
        except Exception as e:
            print(f"[red]Discord message error: {e}")

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()
        print("[green]Discord bridge thread started.")

    def _run(self):
        try:
            asyncio.run(self._async_main())
        except Exception as e:
            print(f"[red]Discord connection error: {e}")
            print("[yellow]Check DISCORD_BOT_TOKEN / intents in the developer portal.")

    async def _async_main(self):
        async with self.client:
            await self.client.start(self.token)

    # ---- cross-thread helpers ----

    def wait_ready(self, timeout=15):
        return self._ready.wait(timeout)

    def _schedule(self, coro_factory, timeout=20):
        if not self.wait_ready():
            print("[yellow]Discord bridge not ready yet.")
            return None
        future = asyncio.run_coroutine_threadsafe(coro_factory(), self._loop)
        try:
            return future.result(timeout=timeout)
        except Exception as e:
            print(f"[red]Discord operation failed: {e}")
            return None

    def _first_guild(self):
        return next(iter(self.client.guilds), None)

    # ---- text output ----

    def send_text(self, text, channel_id=None):
        ids = [channel_id] if channel_id else sorted(self.allowed_channel_ids)
        for cid in ids:
            self._schedule(lambda cid=cid: self._send_text_impl(int(cid), text))

    async def _send_text_impl(self, channel_id, text):
        channel = self.client.get_channel(channel_id)
        if channel:
            for chunk_start in range(0, len(text), 1900):
                await channel.send(text[chunk_start:chunk_start + 1900])

    # ---- VC listening ----

    def _start_vc_listener(self, vc):
        from input.discord_voice_listener import VoskVoiceSink
        self._stop_vc_listener(vc)

        self._voice_sink = VoskVoiceSink(
            model=self._voice_model,
            wake_words=self._vc_wake_words,
            active_window=self._vc_active_window,
            on_text=self.on_text,
            busy_fn=self._vc_busy_fn,
            wake_partial_arm=self._vc_wake_arm,
        )
        vc.listen(self._voice_sink)

        try:
            self._dave_patch = _DaveDecryptPatch(vc)
            self._dave_patch.patch()
        except Exception as e:
            print(f"[red]DAVE patch error: {e}")

        print("[green]Discord: VC voice listener started.")

    def _stop_vc_listener(self, vc):
        if self._voice_sink:
            try:
                vc.stop_listening()
            except Exception:
                pass
            self._voice_sink.cleanup()
        self._voice_sink = None
        self._vc_queue = collections.deque()
        self._vc_current = None
        self._vc_listen_paused = False

    def _vc_pause_listening(self, paused):
        """Suspend the Vosk sink while the bot's TTS plays into the VC.

        The sink only receives other users (bot audio is skipped), so this is
        not the bot hearing itself: it stops the bot's voice coming back through
        a participant's open mic. resume() also drops half-heard audio.
        """
        if paused == self._vc_listen_paused:
            return
        self._vc_listen_paused = paused
        sink = self._voice_sink
        if not sink:
            return
        try:
            if paused:
                sink.pause()
            else:
                sink.resume()
        except Exception as e:
            print(f"[yellow]Discord VC listener "
                  f"{'pause' if paused else 'resume'} failed: {e}")

    # ---- voice ----

    def join_voice(self, target=""):
        result = self._schedule(lambda: self._join_voice_impl(str(target)))
        return bool(result)

    async def _join_voice_impl(self, target):
        guild = self._first_guild()
        if guild is None:
            print("[red]Discord: no server available to join voice in.")
            return False
        channel = None
        if target.isdigit():
            channel = discord.utils.get(guild.voice_channels, id=int(target))
        if channel is None and target:
            needle = target.lower().lstrip("#")
            channel = next((c for c in guild.voice_channels if c.name.lower() == needle), None)
        if channel is None and not target:
            channel = guild.voice_channels[0] if guild.voice_channels else None
        if channel is None:
            print(f"[red]Discord: voice channel '{target}' not found.")
            return False
        vc = guild.voice_client
        if vc and vc.is_connected():
            await vc.move_to(channel)
        else:
            vc = await channel.connect(cls=voice_recv.VoiceRecvClient)
        if self._vc_listen and self._voice_model and vc and vc.is_connected():
            self._start_vc_listener(vc)
        print(f"[green]Discord: joined voice channel '{channel.name}'. Replies now route there.")
        return True

    def leave_voice(self):
        result = self._schedule(lambda: self._leave_voice_impl())
        return bool(result)

    async def _leave_voice_impl(self):
        guild = self._first_guild()
        vc = guild.voice_client if guild else None
        if vc and vc.is_connected():
            self._stop_vc_listener(vc)
            await vc.disconnect()
            print("[green]Discord: left voice channel. Replies go back to text channels.")
            return True
        return False

    def in_voice(self):
        try:
            guild = self._first_guild()
            vc = guild.voice_client if guild else None
            return bool(vc and vc.is_connected())
        except Exception:
            return False

    def play_in_vc(self, wav_path, delete_when_done=True):
        """Queue a clip for playback. Clips are played one at a time in order —
        calling this repeatedly while audio is playing no longer makes clips
        clobber or overlap each other."""
        if not self.in_voice():
            return False
        if not self.wait_ready():
            return False
        self._vc_queue.append((wav_path, delete_when_done))
        try:
            self._loop.call_soon_threadsafe(self._vc_play_next)
        except Exception as e:
            print(f"[red]Discord VC schedule failed: {e}")
            self._vc_queue.pop()
            return False
        return True

    def _vc_play_next(self):
        if self._vc_current:
            wav_path, delete_when_done = self._vc_current
            self._vc_current = None
            self._vc_cleanup(wav_path, delete_when_done)
        guild = self._first_guild()
        vc = guild.voice_client if guild else None
        if not vc or not vc.is_connected():
            while self._vc_queue:
                wav_path, delete_when_done = self._vc_queue.popleft()
                self._vc_cleanup(wav_path, delete_when_done)
            self._vc_pause_listening(False)
            return
        if vc.is_playing():
            return
        if not self._vc_queue:
            self._vc_pause_listening(False)
            return
        wav_path, delete_when_done = self._vc_queue.popleft()
        try:
            source = discord.FFmpegOpusAudio(wav_path)
        except Exception as e:
            print(f"[red]Discord VC source failed: {e}")
            self._vc_cleanup(wav_path, delete_when_done)
            self._loop.call_soon_threadsafe(self._vc_play_next)
            return
        self._vc_current = (wav_path, delete_when_done)
        self._vc_pause_listening(True)
        try:
            vc.play(source, after=lambda _err: self._loop.call_soon_threadsafe(self._vc_play_next))
        except Exception as e:
            print(f"[red]Discord VC play failed: {e}")
            self._vc_cleanup(wav_path, delete_when_done)
            self._vc_current = None
            self._loop.call_soon_threadsafe(self._vc_play_next)

    def _vc_cleanup(self, wav_path, delete_when_done):
        if delete_when_done and os.path.exists(wav_path):
            try:
                os.remove(wav_path)
            except OSError:
                pass
