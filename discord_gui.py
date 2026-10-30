"""Discord bridge GUI — tkinter (stdlib only, no extra pip install).

Starts demo_main.py as a subprocess and streams its log into a live
window. Lets you configure token, channel IDs, voice settings, and Vosk
without touching .env by hand.

Works whether you are plugging into Radeon AI Co-Host or your own custom bot.
"""

import json
import os
import subprocess
import sys
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

ROOT = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(ROOT, ".env")
CONFIG_PATH = os.path.join(ROOT, "config.json")
DEFAULT_ENV_PATH = os.path.join(ROOT, ".env.example")

DEFAULT_ENV = {
    "DISCORD_BOT_TOKEN": "",
    "DISCORD_TEXT_CHANNEL_IDS": "",
    "DISCORD_VOICE_CHANNEL_ID": "",
    "DISCORD_OWNER_NAME": "",
    "DISCORD_BATCH_SIZE": "1",
    "DISCORD_FLUSH_SECONDS": "30",
    "DISCORD_VC_LISTEN": "0",
    "VOSK_MODEL_PATH": "models/vosk-model-small-en-us",
    "WAKE_WORDS": "bot name,bot",
    "WAKE_ACTIVE_WINDOW": "8",
    "WAKE_PARTIAL_ARM": "0",
    "IGNORED_USERS": "",
}


def load_env():
    if os.path.exists(ENV_PATH):
        try:
            data = {}
            with open(ENV_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    data[k.strip()] = v.strip()
            return data
        except Exception:
            pass
    return dict(DEFAULT_ENV)


def save_env(env):
    lines = ["# Discord bridge configuration — written by setup_discord_gui.bat / discord_gui.py",
             "# Edit by hand or re-run setup_discord_gui.bat to change values.",
             ""]
    for k, v in env.items():
        lines.append(f"{k}={v}")
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


class DiscordBridgeGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Discord AI Bridge — Launcher")
        self.geometry("900x700")
        self.minsize(700, 520)

        self.process = None
        self.log_queue = []
        self.env = load_env()

        self._build_ui()
        self._load_env_into_fields()

        self.after(100, self._poll_process)
        self.after(500, self._poll_log_queue)

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        self.status_var = tk.StringVar(value="Stopped")
        status = ttk.Label(
            self, textvariable=self.status_var,
            relief=tk.SUNKEN, anchor=tk.W, padding=(6, 3),
        )
        status.pack(side=tk.BOTTOM, fill=tk.X)

        nb = ttk.Notebook(self)
        nb.pack(fill=tk.BOTH, expand=True)

        self.tab_env = ttk.Frame(nb, padding=10)
        self.tab_log = ttk.Frame(nb, padding=10)
        self.tab_about = ttk.Frame(nb, padding=10)
        nb.add(self.tab_env, text="Configure")
        nb.add(self.tab_log, text="Live Log")
        nb.add(self.tab_about, text="About")

        self._build_env_tab()
        self._build_log_tab()
        self._build_about_tab()

    def _build_env_tab(self):
        f = self.tab_env
        canvas = tk.Canvas(f, highlightthickness=0)
        scrollbar = ttk.Scrollbar(f, orient="vertical", command=canvas.yview)
        scrollable = ttk.Frame(canvas)
        scrollable.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.entries = {}

        def entry_row(parent, label, key, width=40, show=False, tip=None):
            row = ttk.Frame(parent)
            row.pack(fill=tk.X, pady=3)
            ttk.Label(row, text=label, width=26, anchor=tk.W).pack(side=tk.LEFT)
            var = tk.StringVar()
            ent = ttk.Entry(row, textvariable=var, width=width, show="*" if show else "")
            ent.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self.entries[key] = var
            if tip:
                ttk.Label(parent, text=tip, wraplength=300, foreground="#666666").pack(anchor=tk.W, pady=(0, 4))
            return row

        def check_row(parent, label, key, default="0", tip=None):
            row = ttk.Frame(parent)
            row.pack(fill=tk.X, pady=4)
            var = tk.BooleanVar(value=default == "1")
            ttk.Checkbutton(row, text=label, variable=var).pack(side=tk.LEFT)
            self.entries[key] = var
            if tip:
                ttk.Label(parent, text=tip, wraplength=300, foreground="#666666").pack(anchor=tk.W, pady=(0, 4))
            return row

        # --- Required ---
        left = ttk.LabelFrame(scrollable, text="Required", padding=10)
        left.pack(fill=tk.X, pady=(0, 8))
        entry_row(left, "Bot token", "DISCORD_BOT_TOKEN", width=50, show=True,
                  tip="From https://discord.com/developers/applications > Bot > Token. Treat like a password.")
        entry_row(left, "Text channel IDs", "DISCORD_TEXT_CHANNEL_IDS", width=50,
                  tip="Comma-separated channel IDs. Enable Developer Mode in Discord, right-click a channel > Copy Channel ID.")

        # --- Optional text ---
        right = ttk.LabelFrame(scrollable, text="Optional — text", padding=10)
        right.pack(fill=tk.X, pady=(0, 8))
        entry_row(right, "Owner name", "DISCORD_OWNER_NAME",
                  tip="Display name whose messages always get a reply.")
        entry_row(right, "Batch size", "DISCORD_BATCH_SIZE", width=10,
                  tip="Gated messages to batch before replying.")
        entry_row(right, "Flush seconds", "DISCORD_FLUSH_SECONDS", width=10,
                  tip="Flush batch after this many seconds.")

        # --- Voice ---
        vc = ttk.LabelFrame(scrollable, text="Voice channel (optional)", padding=10)
        vc.pack(fill=tk.X, pady=(0, 8))
        entry_row(vc, "Voice channel ID", "DISCORD_VOICE_CHANNEL_ID",
                  tip="Single voice channel ID to auto-join. Blank = use !join in chat.")
        check_row(vc, "Enable VC listening", "DISCORD_VC_LISTEN", default=self.env.get("DISCORD_VC_LISTEN", "0"),
                  tip="Wake-word listening when joined to a VC. Needs a Vosk model below.")
        entry_row(vc, "Vosk model path", "VOSK_MODEL_PATH",
                  tip="Download vosk-model-small-en-us from https://alphacephei.com/vosk/models")
        entry_row(vc, "Wake words", "WAKE_WORDS",
                  tip="Lowercase, comma-separated.")
        entry_row(vc, "Active window (s)", "WAKE_ACTIVE_WINDOW", width=10,
                  tip="Seconds the listener stays active after a wake word.")
        check_row(vc, "Partial arm", "WAKE_PARTIAL_ARM", default=self.env.get("WAKE_PARTIAL_ARM", "0"),
                  tip="Arm on half-heard partial matches (earlier, more false positives).")
        entry_row(vc, "Ignored users", "IGNORED_USERS",
                  tip="Comma-separated display names to ignore entirely.")

        # --- Launch buttons ---
        btns = ttk.Frame(scrollable)
        btns.pack(fill=tk.X, pady=(16, 0))
        self.btn_start = ttk.Button(btns, text="Start bridge", command=self._start_bridge)
        self.btn_start.pack(side=tk.LEFT, padx=(0, 6))
        self.btn_stop = ttk.Button(btns, text="Stop bridge", command=self._stop_bridge, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT)
        ttk.Button(btns, text="Save .env", command=self._save_env).pack(side=tk.LEFT, padx=(10, 0))

    def _build_log_tab(self):
        f = self.tab_log
        self.log_text = scrolledtext.ScrolledText(f, wrap=tk.WORD, font=("Consolas", 10))
        self.log_text.pack(fill=tk.BOTH, expand=True)
        btns = ttk.Frame(f)
        btns.pack(fill=tk.X, pady=(6, 0))
        ttk.Button(btns, text="Clear log", command=self._clear_log).pack(side=tk.LEFT)

    def _build_about_tab(self):
        f = self.tab_about
        text = (
            "Discord AI Bridge\n\n"
            "Framework-agnostic Discord text + voice bridge. Receives Discord\n"
            "messages through its own gateway connection and hands them to your\n"
            "bot adapter via the on_text callback.\n\n"
            "  • text  — gated messages (mention, keyword, or !prefix)\n"
            "  • voice — wake-word listening in a voice channel (Vosk)\n"
            "  • out   — post replies back to Discord text or VC audio\n\n"
            "Requires: Python 3, discord.py, discord-ext-voice-recv, davey, vosk, rich\n"
            "Optional: FFmpeg on PATH for VC playback\n\n"
            "No credentials are hard-coded; everything lives in .env.\n"
        )
        ttk.Label(f, text=text, justify=tk.LEFT, wraplength=640).pack(anchor=tk.W, pady=10)

    # ------------------------------------------------------------------ env fields

    def _load_env_into_fields(self):
        for key, var in self.entries.items():
            var.set(str(self.env.get(key, "")))

    def _collect_env(self):
        env = {}
        for key, var in self.entries.items():
            if isinstance(var, tk.BooleanVar):
                env[key] = "1" if var.get() else "0"
            else:
                env[key] = var.get().strip()
        return env

    def _save_env(self):
        env = self._collect_env()
        save_env(env)
        self.env = env
        messagebox.showinfo("Saved", ".env written.")

    # ------------------------------------------------------------------ bridge process

    def _start_bridge(self):
        if self.process is not None and self.process.poll() is None:
            messagebox.showwarning("Already running", "The bridge is already running.")
            return

        env = self._collect_env()
        if not env.get("DISCORD_BOT_TOKEN"):
            messagebox.showwarning("Missing token", "Please set a Discord bot token.")
            return
        if not env.get("DISCORD_TEXT_CHANNEL_IDS"):
            messagebox.showwarning("Missing channels", "Please set at least one text channel ID.")
            return

        save_env(env)
        self.env = env

        script = os.path.join(ROOT, "demo_main.py")
        python = sys.executable or "python"
        try:
            self.process = subprocess.Popen(
                [python, script],
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except Exception as e:
            messagebox.showerror("Start failed", str(e))
            return

        self.btn_start.configure(state=tk.DISABLED)
        self.btn_stop.configure(state=tk.NORMAL)
        self.status_var.set("Running")
        self._log_ui(f"Bridge started (PID {self.process.pid})")
        self._log_ui(f"Token: {'set' if env.get('DISCORD_BOT_TOKEN') else 'missing'}")
        self._log_ui(f"Channels: {env.get('DISCORD_TEXT_CHANNEL_IDS')}")

    def _stop_bridge(self):
        if self.process is None:
            return
        try:
            self.process.terminate()
            self.process.wait(timeout=5)
        except Exception:
            try:
                self.process.kill()
            except Exception:
                pass
        self.process = None
        self.btn_start.configure(state=tk.NORMAL)
        self.btn_stop.configure(state=tk.DISABLED)
        self.status_var.set("Stopped")
        self._log_ui("Bridge stopped.")

    # ------------------------------------------------------------------ log plumbing

    def _poll_process(self):
        if self.process is None:
            self.after(200, self._poll_process)
            return
        line = self.process.stdout.readline()
        if line:
            self.log_queue.append(line.rstrip("\n"))
        if self.process.poll() is not None:
            remaining = self.process.stdout.read()
            if remaining:
                for ln in remaining.splitlines():
                    self.log_queue.append(ln)
            self._log_ui(f"[process exited code {self.process.returncode}]")
            self.process = None
            self.btn_start.configure(state=tk.NORMAL)
            self.btn_stop.configure(state=tk.DISABLED)
            self.status_var.set("Stopped")
        self.after(100, self._poll_process)

    def _poll_log_queue(self):
        while self.log_queue:
            line = self.log_queue.pop(0)
            self._log_ui(line)
        self.after(500, self._poll_log_queue)

    def _log_ui(self, text):
        self.log_text.insert(tk.END, text + "\n")
        self.log_text.see(tk.END)

    def _clear_log(self):
        self.log_text.delete("1.0", tk.END)

    def on_closing(self):
        self._stop_bridge()
        self.destroy()


if __name__ == "__main__":
    app = DiscordBridgeGUI()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
