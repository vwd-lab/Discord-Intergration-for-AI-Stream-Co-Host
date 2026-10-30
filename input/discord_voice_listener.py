try:
    import audioop
except ModuleNotFoundError:  # removed from the stdlib in Python 3.13
    # audioop-lts provides the same top-level "audioop" name, so on 3.13+ the
    # import above succeeds once the backport is installed
    # (pip install audioop-lts). This branch only fires when it is not.
    raise ModuleNotFoundError(
        "audioop was removed from Python 3.13. Either run Python 3.12 or "
        "below, or install the backport: pip install audioop-lts"
    )
import json
import re
import threading
import time

from discord.ext import voice_recv
from rich import print

_SAMPLE_RATE = 16000
_DISCORD_RATE = 48000


class VoskVoiceSink(voice_recv.AudioSink):
    """discord-ext-voice-recv AudioSink that feeds per-user audio to Vosk.

    Wake-word gating identical to PassiveListener: passive until a wake word
    is heard, then active for ``active_window`` seconds, dispatching speech
    to ``on_text(text)``.
    """

    def __init__(self, model, wake_words, active_window=8, on_text=None,
                 busy_fn=None, wake_partial_arm=False, min_command_words=3):
        self.model = model
        self.wake_words = [w.lower() for w in wake_words if w.strip()]
        self.active_window = active_window
        self.on_text = on_text
        self.busy_fn = busy_fn
        self._wake_partial_arm = wake_partial_arm
        self._min_command_words = min_command_words
        self._states = {}
        self._lock = threading.Lock()
        self._paused = False

    def write(self, user, data):
        if user is None or getattr(user, "bot", False):
            return
        if self._paused:
            return
        if self.busy_fn and self.busy_fn():
            return

        cnt = getattr(self, "_dbg_cnt", 0) + 1
        self._dbg_cnt = cnt
        if cnt % 100 == 1:
            print(f"[yellow]VC write flow: {cnt} pcm={len(getattr(data,'pcm',b'') or b'')}", flush=True)

        uid = user.id
        with self._lock:
            if uid not in self._states:
                self._states[uid] = _UserState(
                    self.model, self.wake_words, self.active_window,
                    wake_partial_arm=self._wake_partial_arm,
                    min_command_words=self._min_command_words,
                )
            state = self._states[uid]

        pcm = getattr(data, "pcm", b"")
        if not pcm or len(pcm) < 2:
            return

        pcm_mono = audioop.tomono(pcm, 2, 1.0, 1.0)
        pcm_16k, state._ratecv_state = audioop.ratecv(pcm_mono, 2, 1, _DISCORD_RATE, _SAMPLE_RATE, state._ratecv_state)

        try:
            state.feed(pcm_16k, self.on_text, self.busy_fn, user.display_name)
        except Exception as e:
            print(f"[red]VC feed error: {e}")

    def wants_opus(self):
        return False

    def cleanup(self):
        with self._lock:
            self._states.clear()

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False
        with self._lock:
            for s in self._states.values():
                s.reset_recognizer()


class _UserState:
    __slots__ = ("model", "recognizer", "wake_words", "active_window",
                 "active_until", "_partial_count", "_ratecv_state",
                 "_dispatch_sent", "_wake_partial_arm", "_min_command_words",
                 "_partial", "_last_text")

    def __init__(self, model, wake_words, active_window,
                 wake_partial_arm=False, min_command_words=3):
        from vosk import KaldiRecognizer
        self.model = model
        self.recognizer = KaldiRecognizer(model, _SAMPLE_RATE)
        self.wake_words = wake_words
        self.active_window = active_window
        self.active_until = 0.0
        self._partial_count = 0
        self._ratecv_state = None
        self._dispatch_sent = False
        self._wake_partial_arm = wake_partial_arm
        self._min_command_words = min_command_words
        self._partial = ""
        self._last_text = ""

    def _dispatch(self, on_text, display_name, text, live=False):
        formatted = f"[Discord VC viewer '{display_name}' says]{' (live)' if live else ''}: {text}"
        on_text(display_name, formatted)

    def feed(self, pcm_16k, on_text, busy_fn, display_name):
        try:
            accepted = self.recognizer.AcceptWaveform(pcm_16k)
        except Exception as e:
            print(f"[red]VC Vosk error: {e}")
            return

        if busy_fn and busy_fn():
            return

        partial = ""
        if not accepted:
            try:
                partial = json.loads(self.recognizer.PartialResult()).get("partial", "")
            except Exception:
                partial = ""
            self._partial = partial
            self._partial_count += 1

        now = time.time()
        active = now < self.active_until

        if not accepted:
            if active:
                # Speaker is still talking: slide the listening window
                # forward so a longer utterance never gets cut off.
                if partial:
                    self.active_until = now + self.active_window
            elif self._wake_partial_arm:
                wake, _ = self._match_wake(partial)
                if wake:
                    print(f"[green]VC wake word heard ('{wake}') — listening...")
                    self.active_until = now + max(
                        self.active_window,
                        int((len(partial.split()) + 6) * 0.7),
                    )
            wake, rest = self._match_wake(partial)
            if wake and rest and not self._dispatch_sent \
                    and len(rest.split()) >= self._min_command_words:
                print(f"[cyan]  (VC wake '{wake}' live) >> {rest}")
                self._dispatch(on_text, display_name, rest, live=True)
                self._dispatch_sent = True
                self.active_until = now + self.active_window
            return

        result = json.loads(self.recognizer.Result())
        text = result.get("text", "").strip()
        self._last_text = text
        if not text:
            return

        wake, rest = self._match_wake(text)
        if wake and rest:
            if not self._dispatch_sent:
                print(f"[cyan]  (VC wake '{wake}') >> {rest}")
                self._dispatch(on_text, display_name, rest)
            self.active_until = time.time() + self.active_window
            self._dispatch_sent = False
        elif wake:
            print(f"[green]VC wake word heard ('{wake}') — listening...")
            self.active_until = time.time() + self.active_window
            self._dispatch_sent = False
        elif active:
            print(f"[cyan]  (VC) {display_name} >> {text}")
            self._dispatch(on_text, display_name, text)
            self.active_until = time.time() + min(self.active_window, 4) + 2
        elif self._dispatch_sent:
            self._dispatch_sent = False

    def _match_wake(self, text):
        norm = " " + re.sub(r"[^a-z0-9 ]", " ", text.lower()) + " "
        for phrase in sorted(self.wake_words, key=len, reverse=True):
            p = f" {phrase} "
            idx = norm.find(p)
            if idx != -1:
                stripped = (norm[:idx] + " " + norm[idx + len(p):]).strip()
                return phrase, re.sub(r"\s+", " ", stripped).strip()
        return None, ""

    def reset_recognizer(self):
        from vosk import KaldiRecognizer
        self.recognizer = KaldiRecognizer(self.model, _SAMPLE_RATE)
        self.active_until = 0.0
        self._ratecv_state = None
        self._dispatch_sent = False
