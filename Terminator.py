#!/usr/bin/env python3
"""
T E R M I N A T O R  —  Voice Assistant
=========================================
Cyberdyne Systems Model 101

INSTALL:
    pip install SpeechRecognition pyttsx3 psutil pyaudio pywin32

    macOS:   brew install portaudio && pip install pyaudio
    Ubuntu:  sudo apt-get install portaudio19-dev espeak python3-pyaudio
    Windows: pip install pyaudio pywin32  (pywin32 = best TTS on Windows)

RUN:
    python terminator.py          → voice mode
    python terminator.py --text   → keyboard mode (no mic needed)
"""

import os, sys, time, math, re, random, platform, datetime
import threading, subprocess, webbrowser, shutil, socket
import tempfile, glob

# ── Auto-install core packages ─────────────────────────────────────────────────
def _pip(pkg):
    subprocess.run([sys.executable, "-m", "pip", "install", pkg],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

for _p, _n in [("pyttsx3","pyttsx3"), ("speech_recognition","SpeechRecognition"), ("psutil","psutil")]:
    try:    __import__(_p)
    except: print(f"[T-800] Installing {_n}..."); _pip(_n)

try:    import pyttsx3;              PYTTSX3_OK = True
except: PYTTSX3_OK = False
try:    import speech_recognition as sr; SR_OK = True
except: SR_OK = False
try:    import psutil;               PSUTIL_OK  = True
except: PSUTIL_OK  = False

IS_WIN   = platform.system() == "Windows"
IS_MAC   = platform.system() == "Darwin"
IS_LINUX = platform.system() == "Linux"

BOT_NAME = "Terminator"
BOT_TAG  = "T-800"

# ══════════════════════════════════════════════════════════════════════════════
#  TEXT-TO-SPEECH
# ══════════════════════════════════════════════════════════════════════════════

class TTSEngine:
    """
    Windows: win32com SAPI5  →  PowerShell SAPI5  →  pyttsx3
    macOS:   say command
    Linux:   espeak
    Fallback: console only
    """
    def __init__(self):
        self.backend = "console"
        self.sapi = self.engine = None
        self._setup()

    def _setup(self):
        if IS_WIN:
            # ── Option 1: win32com (fastest, blocking-wait supported) ──────────
            try:
                import win32com.client
                sapi = win32com.client.Dispatch("SAPI.SpVoice")
                voices = sapi.GetVoices()
                for i in range(voices.Count):
                    if any(k in voices.Item(i).GetDescription().lower()
                           for k in ["david","mark","george","zira","hazel"]):
                        sapi.Voice = voices.Item(i); break
                sapi.Rate = 1; sapi.Volume = 100
                sapi.Speak(" ", 1)
                self.sapi = sapi; self.backend = "sapi_com"
                print(f"[{BOT_TAG}] TTS: Windows SAPI5 via win32com ✓"); return
            except Exception as e:
                print(f"[{BOT_TAG}] win32com unavailable ({e})")

            # ── Option 2: PowerShell SAPI5 (zero extra install) ───────────────
            try:
                self._ps_speak(" ")
                self.backend = "sapi_ps"
                print(f"[{BOT_TAG}] TTS: Windows SAPI5 via PowerShell ✓"); return
            except Exception as e:
                print(f"[{BOT_TAG}] PowerShell TTS failed ({e})")

        if PYTTSX3_OK:
            try:
                eng = pyttsx3.init()
                eng.setProperty("rate", 165); eng.setProperty("volume", 1.0)
                for kw in ["david","zira","daniel","alex","english"]:
                    for v in eng.getProperty("voices"):
                        if kw in v.name.lower() or kw in v.id.lower():
                            eng.setProperty("voice", v.id); break
                    else: continue
                    break
                eng.say(" "); eng.runAndWait()
                self.engine = eng; self.backend = "pyttsx3"
                print(f"[{BOT_TAG}] TTS: pyttsx3 ✓"); return
            except Exception as e:
                print(f"[{BOT_TAG}] pyttsx3 failed ({e})")

        if IS_MAC:
            try:
                subprocess.run(["say","test"], check=True, capture_output=True)
                self.backend = "say"
                print(f"[{BOT_TAG}] TTS: macOS say ✓"); return
            except: pass

        if IS_LINUX and shutil.which("espeak"):
            self.backend = "espeak"
            print(f"[{BOT_TAG}] TTS: espeak ✓"); return

        print(f"[{BOT_TAG}] ⚠  No TTS — console only.  Fix: pip install pywin32")

    def _ps_speak(self, text: str):
        """Speak via PowerShell — temp .ps1 file avoids all quoting issues."""
        safe = text.replace('"@', '" @')
        script = (
            "Add-Type -AssemblyName System.Speech\n"
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer\n"
            "$s.Rate = 1\n"
            "$s.Speak(@\"\n" + safe + "\n\"@)\n"
        )
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".ps1", delete=False, encoding="utf-8")
        tmp.write(script); tmp.close()
        subprocess.run(["powershell","-NoProfile","-WindowStyle","Hidden",
                        "-ExecutionPolicy","Bypass","-File",tmp.name],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try: os.unlink(tmp.name)
        except: pass

    def speak(self, text: str):
        print(f"\n🤖  {BOT_NAME.upper()}: {text}\n")
        if self.backend == "sapi_com":
            try:
                self.sapi.Speak(text, 1)
                while self.sapi.Status.RunningState == 2: time.sleep(0.05)
            except Exception as e: print(f"    [TTS: {e}]")
        elif self.backend == "sapi_ps":
            try: self._ps_speak(text)
            except Exception as e: print(f"    [TTS: {e}]")
        elif self.backend == "pyttsx3":
            try: self.engine.say(text); self.engine.runAndWait()
            except Exception as e: print(f"    [TTS: {e}]")
        elif self.backend == "say":
            try: subprocess.run(["say","-r","170",text])
            except Exception as e: print(f"    [TTS: {e}]")
        elif self.backend == "espeak":
            try: subprocess.run(["espeak","-v","en","-s","155",text])
            except Exception as e: print(f"    [TTS: {e}]")


# ══════════════════════════════════════════════════════════════════════════════
#  SPEECH RECOGNITION
# ══════════════════════════════════════════════════════════════════════════════

class MicListener:
    def __init__(self):
        self.available = False
        self.r = None
        if not SR_OK: return
        self.r = sr.Recognizer()
        self.r.energy_threshold = 300
        self.r.dynamic_energy_threshold = True
        self.r.dynamic_energy_adjustment_damping = 0.10
        self.r.pause_threshold = 0.8
        self.r.phrase_threshold = 0.2
        self.r.non_speaking_duration = 0.6
        try:
            with sr.Microphone() as src:
                print(f"[{BOT_TAG}] Calibrating mic...", end=" ", flush=True)
                self.r.adjust_for_ambient_noise(src, duration=1.5)
                print(f"done (threshold={int(self.r.energy_threshold)}) ✓")
            self.available = True
        except OSError as e:
            print(f"\n[{BOT_TAG}] ⚠  Mic unavailable: {e}")
            print(f"[{BOT_TAG}]    Windows: pip install pyaudio")
        except Exception as e:
            print(f"\n[{BOT_TAG}] ⚠  Mic error: {e}")

    def _transcribe(self, audio) -> str:
        try:
            return self.r.recognize_google(audio, language="en-US").lower()
        except sr.UnknownValueError:
            return ""
        except sr.RequestError:
            try:
                import whisper as _w
                if not hasattr(self, "_wm"):
                    print(f"[{BOT_TAG}] Loading Whisper offline model...")
                    self._wm = _w.load_model("tiny")
                import numpy as np
                wav = np.frombuffer(audio.get_wav_data(), dtype=np.int16).astype(np.float32) / 32768.0
                return self._wm.transcribe(wav, fp16=False, language="en")["text"].strip().lower()
            except:
                print(f"[{BOT_TAG}] No internet + no Whisper. pip install openai-whisper")
                return ""

    def listen_once(self) -> str:
        if not self.available: return ""
        try:
            with sr.Microphone() as src:
                self.r.adjust_for_ambient_noise(src, duration=0.3)
                print("🎤  Listening...")
                audio = self.r.listen(src, timeout=7, phrase_time_limit=12)
            text = self._transcribe(audio)
            if text: print(f"👤  You: {text}")
            return text
        except sr.WaitTimeoutError: return ""
        except Exception as e: print(f"[Listen error] {e}"); return ""

    def listen_long(self, prompt="") -> str:
        """Dictation mode — waits 2.5 s of silence before stopping."""
        if not self.available: return ""
        if prompt: print(f"    [{prompt} — speak freely, pause when done]")
        saved_p, saved_n = self.r.pause_threshold, self.r.non_speaking_duration
        self.r.pause_threshold = 2.5
        self.r.non_speaking_duration = 2.0
        try:
            with sr.Microphone() as src:
                self.r.adjust_for_ambient_noise(src, duration=0.3)
                print("🎤  Dictating... (pause to finish)")
                audio = self.r.listen(src, timeout=10, phrase_time_limit=60)
            text = self._transcribe(audio)
            if text: print(f"👤  You said: {text}")
            return text
        except sr.WaitTimeoutError: print(f"[{BOT_TAG}] No speech detected."); return ""
        except Exception as e: print(f"[Listen error] {e}"); return ""
        finally:
            self.r.pause_threshold = saved_p
            self.r.non_speaking_duration = saved_n


# ══════════════════════════════════════════════════════════════════════════════
#  WINDOWS APP ENGINE  — find, open, close ANY installed app
# ══════════════════════════════════════════════════════════════════════════════

_EV = os.path.expandvars

# Static alias map for 50+ common apps
WIN_APP_MAP = {
    "chrome":             r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "google chrome":      r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "firefox":            r"C:\Program Files\Mozilla Firefox\firefox.exe",
    "edge":               r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "microsoft edge":     r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "brave":              r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
    "opera":              _EV(r"%LOCALAPPDATA%\Programs\Opera\launcher.exe"),
    "notepad":            "notepad.exe",
    "wordpad":            "wordpad.exe",
    "word":               r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE",
    "excel":              r"C:\Program Files\Microsoft Office\root\Office16\EXCEL.EXE",
    "powerpoint":         r"C:\Program Files\Microsoft Office\root\Office16\POWERPNT.EXE",
    "outlook":            r"C:\Program Files\Microsoft Office\root\Office16\OUTLOOK.EXE",
    "onenote":            r"C:\Program Files\Microsoft Office\root\Office16\ONENOTE.EXE",
    "teams":              _EV(r"%LOCALAPPDATA%\Microsoft\Teams\current\Teams.exe"),
    "calculator":         "calc.exe",
    "paint":              "mspaint.exe",
    "snipping tool":      "SnippingTool.exe",
    "task manager":       "taskmgr.exe",
    "file explorer":      "explorer.exe",
    "explorer":           "explorer.exe",
    "control panel":      "control.exe",
    "device manager":     "devmgmt.msc",
    "registry editor":    "regedit.exe",
    "command prompt":     "cmd.exe",
    "cmd":                "cmd.exe",
    "powershell":         "powershell.exe",
    "terminal":           "wt.exe",
    "windows terminal":   "wt.exe",
    "vlc":                r"C:\Program Files\VideoLAN\VLC\vlc.exe",
    "spotify":            _EV(r"%APPDATA%\Spotify\Spotify.exe"),
    "itunes":             r"C:\Program Files\iTunes\iTunes.exe",
    "windows media player": "wmplayer.exe",
    "vs code":            _EV(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"),
    "vscode":             _EV(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"),
    "visual studio code": _EV(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"),
    "visual studio":      r"C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\devenv.exe",
    "pycharm":            r"C:\Program Files\JetBrains\PyCharm Community Edition\bin\pycharm64.exe",
    "android studio":     r"C:\Program Files\Android\Android Studio\bin\studio64.exe",
    "git bash":           r"C:\Program Files\Git\git-bash.exe",
    "discord":            _EV(r"%LOCALAPPDATA%\Discord\Update.exe"),
    "slack":              _EV(r"%LOCALAPPDATA%\slack\slack.exe"),
    "zoom":               _EV(r"%APPDATA%\Zoom\bin\Zoom.exe"),
    "skype":              _EV(r"%APPDATA%\Microsoft\Skype for Desktop\Skype.exe"),
    "whatsapp":           _EV(r"%LOCALAPPDATA%\WhatsApp\WhatsApp.exe"),
    "telegram":           _EV(r"%APPDATA%\Telegram Desktop\Telegram.exe"),
    "steam":              r"C:\Program Files (x86)\Steam\steam.exe",
    "epic games":         _EV(r"%LOCALAPPDATA%\EpicGamesLauncher\Portal\Binaries\Win64\EpicGamesLauncher.exe"),
    "obs":                r"C:\Program Files\obs-studio\bin\64bit\obs64.exe",
    "obs studio":         r"C:\Program Files\obs-studio\bin\64bit\obs64.exe",
    "photoshop":          r"C:\Program Files\Adobe\Adobe Photoshop 2024\Photoshop.exe",
    "adobe photoshop":    r"C:\Program Files\Adobe\Adobe Photoshop 2024\Photoshop.exe",
    "premiere":           r"C:\Program Files\Adobe\Adobe Premiere Pro 2024\Adobe Premiere Pro.exe",
    "after effects":      r"C:\Program Files\Adobe\Adobe After Effects 2024\Support Files\AfterFX.exe",
    "illustrator":        r"C:\Program Files\Adobe\Adobe Illustrator 2024\Support Files\Contents\Windows\Illustrator.exe",
    "blender":            r"C:\Program Files\Blender Foundation\Blender 4.0\blender.exe",
    "minecraft":          _EV(r"%APPDATA%\.minecraft\MinecraftLauncher.exe"),
    "notepad++":          r"C:\Program Files\Notepad++\notepad++.exe",
    "7zip":               r"C:\Program Files\7-Zip\7zFM.exe",
    "winrar":             r"C:\Program Files\WinRAR\WinRAR.exe",
    "putty":              r"C:\Program Files\PuTTY\putty.exe",
    "filezilla":          r"C:\Program Files\FileZilla FTP Client\filezilla.exe",
}

# Process name map for killing apps
WIN_PROC_MAP = {
    "chrome":         ["chrome.exe"],
    "google chrome":  ["chrome.exe"],
    "firefox":        ["firefox.exe"],
    "edge":           ["msedge.exe"],
    "brave":          ["brave.exe"],
    "notepad":        ["notepad.exe"],
    "word":           ["WINWORD.EXE"],
    "excel":          ["EXCEL.EXE"],
    "powerpoint":     ["POWERPNT.EXE"],
    "outlook":        ["OUTLOOK.EXE"],
    "teams":          ["Teams.exe"],
    "calculator":     ["CalculatorApp.exe","calc.exe"],
    "paint":          ["mspaint.exe"],
    "task manager":   ["Taskmgr.exe"],
    "spotify":        ["Spotify.exe"],
    "vlc":            ["vlc.exe"],
    "discord":        ["Discord.exe"],
    "slack":          ["slack.exe"],
    "zoom":           ["Zoom.exe"],
    "skype":          ["Skype.exe"],
    "whatsapp":       ["WhatsApp.exe"],
    "telegram":       ["Telegram.exe"],
    "steam":          ["steam.exe"],
    "obs":            ["obs64.exe","obs32.exe","obs.exe"],
    "obs studio":     ["obs64.exe"],
    "photoshop":      ["Photoshop.exe"],
    "blender":        ["blender.exe"],
    "vs code":        ["Code.exe"],
    "vscode":         ["Code.exe"],
    "visual studio code": ["Code.exe"],
    "visual studio":  ["devenv.exe"],
    "pycharm":        ["pycharm64.exe"],
    "notepad++":      ["notepad++.exe"],
    "epic games":     ["EpicGamesLauncher.exe"],
}


def _registry_search(name_lower: str) -> list:
    """
    Search Windows Registry Uninstall keys for installed apps.
    Returns list of (score, exe_path) tuples.
    """
    results = []
    if not IS_WIN: return results
    try:
        import winreg
        REG_PATHS = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER,  r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        ]
        def rval(k, n):
            try: return winreg.QueryValueEx(k, n)[0]
            except: return ""

        for hive, reg_path in REG_PATHS:
            try:
                key = winreg.OpenKey(hive, reg_path)
                for i in range(winreg.QueryInfoKey(key)[0]):
                    try:
                        sub = winreg.OpenKey(key, winreg.EnumKey(key, i))
                        display  = rval(sub, "DisplayName").lower()
                        exe_icon = rval(sub, "DisplayIcon")
                        inst_loc = rval(sub, "InstallLocation")
                        if not display: continue
                        score = 2 if name_lower == display else (1 if name_lower in display or display in name_lower else 0)
                        if score == 0: continue
                        # Check InstallLocation for a matching .exe
                        if inst_loc and os.path.isdir(inst_loc):
                            for fn in os.listdir(inst_loc):
                                if fn.lower().endswith(".exe"):
                                    stem = fn.lower().replace(".exe","")
                                    if name_lower in stem or stem in name_lower:
                                        results.append((score+1, os.path.join(inst_loc, fn)))
                        # DisplayIcon often IS the exe path
                        if exe_icon:
                            exe_path = exe_icon.split(",")[0].strip().strip('"')
                            if exe_path.lower().endswith(".exe") and os.path.exists(exe_path):
                                results.append((score, exe_path))
                    except: pass
            except: pass
    except ImportError: pass
    return results


def _find_any_app(name: str) -> str | None:
    """
    Find ANY installed app by name using 4 strategies:
      1. Static alias map
      2. Windows Registry (uninstall entries)
      3. Start Menu .lnk / .exe shortcuts
      4. Filesystem walk of install directories
    Returns best-matching .exe/.lnk path or None.
    """
    nl = name.lower().strip()
    candidates = []  # (score, path)

    # 1. Static alias map
    if nl in WIN_APP_MAP:
        path = WIN_APP_MAP[nl]
        if "*" in path:
            matches = glob.glob(path)
            path = sorted(matches)[-1] if matches else None
        if path and os.path.exists(path):
            return path  # highest priority, return immediately

    # 2. Registry
    candidates.extend(_registry_search(nl))

    # 3. Start Menu folders
    start_dirs = [
        _EV(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
        _EV(r"%ProgramData%\Microsoft\Windows\Start Menu\Programs"),
        _EV(r"%LOCALAPPDATA%\Programs"),
    ]
    for root_dir in start_dirs:
        if not os.path.isdir(root_dir): continue
        for root, dirs, files in os.walk(root_dir):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "node_modules"]
            for fn in files:
                if not fn.lower().endswith((".exe",".lnk")): continue
                stem = os.path.splitext(fn)[0].lower()
                score = 2 if nl == stem else (1 if nl in stem or stem in nl else 0)
                if score: candidates.append((score, os.path.join(root, fn)))

    # 4. Filesystem walk (limited depth for speed)
    walk_dirs = [
        _EV(r"%PROGRAMFILES%"), _EV(r"%PROGRAMFILES(X86)%"),
        _EV(r"%LOCALAPPDATA%"), _EV(r"%APPDATA%"),
    ]
    SKIP = {"node_modules","__pycache__","cache","logs","temp","tmp","crash reports",
            "crashreports","crashpad","resources","locales","swiftshader"}
    for root_dir in walk_dirs:
        if not os.path.isdir(root_dir): continue
        for root, dirs, files in os.walk(root_dir):
            depth = root.replace(root_dir,"").count(os.sep)
            if depth > 5: dirs.clear(); continue
            dirs[:] = [d for d in dirs if not d.startswith(".") and d.lower() not in SKIP]
            for fn in files:
                if not fn.lower().endswith(".exe"): continue
                stem = os.path.splitext(fn)[0].lower()
                score = 2 if nl == stem else (1 if nl in stem or stem in nl else 0)
                if score: candidates.append((score, os.path.join(root, fn)))

    if not candidates: return None
    candidates.sort(key=lambda x: (-x[0], len(x[1])))
    return candidates[0][1]


def _launch_windows(name: str) -> bool:
    """Launch a Windows app. Returns True if successfully launched."""
    nl = name.lower().strip()

    # Fast: direct .exe on PATH
    if shutil.which(name): subprocess.Popen([name]); return True
    if shutil.which(name+".exe"): subprocess.Popen([name+".exe"]); return True

    # Full search
    path = _find_any_app(nl)
    if path:
        if path.endswith(".lnk"): os.startfile(path); return True
        if os.path.exists(path): subprocess.Popen([path]); return True

    # PowerShell Start-Process (handles UWP + Store apps)
    try:
        r = subprocess.run(
            ["powershell","-NoProfile","-Command",f"Start-Process '{nl}'"],
            capture_output=True, timeout=5)
        if r.returncode == 0: return True
    except: pass

    # Last resort: os.startfile
    try: os.startfile(name); return True
    except: pass

    return False


def _close_windows(name: str) -> tuple:
    """Kill all processes matching name. Returns (success, killed_list)."""
    nl = name.lower().strip()
    killed = []

    if not PSUTIL_OK:
        targets = WIN_PROC_MAP.get(nl, [nl+".exe", nl.replace(" ","")+".exe"])
        for pn in targets:
            r = subprocess.run(["taskkill","/F","/IM",pn], capture_output=True)
            if r.returncode == 0: killed.append(pn)
        return bool(killed), killed

    targets = WIN_PROC_MAP.get(nl, [])
    for proc in psutil.process_iter(["pid","name"]):
        try:
            pname = proc.info["name"] or ""
            pl = pname.lower()
            if pname in targets or nl in pl or pl.replace(".exe","") in nl:
                proc.kill(); killed.append(pname)
        except (psutil.NoSuchProcess, psutil.AccessDenied): pass

    return bool(killed), killed


# ══════════════════════════════════════════════════════════════════════════════
#  CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════

WAKE_WORDS = ["terminator","hey terminator","ok terminator","t 800","hey t800"]

BOOT_LINES = [
    "Terminator online. Awaiting orders.",
    "Systems online. I'll be back... with your request.",
    "Neural net processor online. What do you need?",
    "Cyberdyne Systems Model 101 online. Ready.",
    "Scanning threat database. No threats found. What can I do for you?",
]
FAREWELLS = [
    "Hasta la vista.",
    "I'll be back.",
    "Terminating session. Goodbye.",
    "Powering down. Stay out of trouble.",
]
CONFUSED = [
    "Does not compute. Say help for the command list.",
    "Invalid command. Try again or say help.",
    "Target not acquired. Rephrase your request.",
    "I do not understand. Say help to see what I can do.",
]


# ══════════════════════════════════════════════════════════════════════════════
#  TERMINATOR CORE
# ══════════════════════════════════════════════════════════════════════════════

class Terminator:
    def __init__(self, text_mode=False):
        self.text_mode  = text_mode
        self.user_name  = "human"
        self.is_running = True
        self._clipboard = ""

        self.tts = TTSEngine()
        self.mic = MicListener() if not text_mode else None

        if not text_mode and (self.mic is None or not self.mic.available):
            print(f"[{BOT_TAG}] No mic available — switching to text mode.")
            self.text_mode = True

        self.commands = self._register_commands()

    # ── I/O ───────────────────────────────────────────────────────────────────

    def say(self, text: str):
        self.tts.speak(text)

    def get_input(self) -> str:
        if self.text_mode:
            try:    return input("👤  You: ").strip().lower()
            except: return "goodbye"
        return self.mic.listen_once()

    def _dictate(self, prompt="") -> str:
        if self.text_mode:
            try:    return input(f"    ({prompt}) → ").strip()
            except: return ""
        return self.mic.listen_long(prompt)

    # ════════════════════════════════════════════════════════════════════════
    #  COMMAND HANDLERS
    # ════════════════════════════════════════════════════════════════════════

    # ── Time / Date ────────────────────────────────────────────────────────
    def _time(self, _):
        self.say(f"It's {datetime.datetime.now().strftime('%I:%M %p').lstrip('0')}.")

    def _date(self, _):
        self.say(f"Today is {datetime.datetime.now().strftime('%A, %B %d, %Y')}.")

    def _greet(self, _):
        h = datetime.datetime.now().hour
        g = "Good morning" if h < 12 else ("Good afternoon" if h < 17 else "Good evening")
        self.say(f"{g}, {self.user_name}.")

    # ── Maths ──────────────────────────────────────────────────────────────
    def _calculate(self, q):
        expr = (q.replace("calculate","").replace("what is","").replace("compute","")
                  .replace("equals","").replace("plus","+").replace("minus","-")
                  .replace("times","*").replace("multiplied by","*")
                  .replace("divided by","/").replace("over","/")
                  .replace("to the power of","**").replace("squared","**2")
                  .replace("cubed","**3").replace("percent of","*0.01*").strip())
        try:
            allowed = {k: getattr(math, k) for k in dir(math) if not k.startswith("_")}
            r = eval(expr, {"__builtins__": {}}, allowed)
            r = int(r) if isinstance(r, float) and r.is_integer() else round(r, 6)
            self.say(f"The answer is {r}.")
        except:
            self.say("Could not calculate that. Try: calculate 12 times 8.")

    def _convert(self, q):
        nums = re.findall(r"-?\d+\.?\d*", q)
        if not nums: self.say("Give me a value, like: convert 100 celsius to fahrenheit."); return
        val = float(nums[0])
        conversions = [
            (["celsius","fahrenheit"], lambda v: f"{v}°C = {round(v*9/5+32,1)}°F"),
            (["fahrenheit","celsius"], lambda v: f"{v}°F = {round((v-32)*5/9,1)}°C"),
            (["km","mile"],            lambda v: f"{v} km = {round(v*0.621371,2)} miles"),
            (["mile","km"],            lambda v: f"{v} miles = {round(v*1.60934,2)} km"),
            (["kg","lb"],              lambda v: f"{v} kg = {round(v*2.20462,2)} lbs"),
            (["lb","kg"],              lambda v: f"{v} lbs = {round(v*0.453592,2)} kg"),
            (["meter","feet"],         lambda v: f"{v} m = {round(v*3.28084,2)} ft"),
            (["feet","meter"],         lambda v: f"{v} ft = {round(v*0.3048,2)} m"),
            (["liter","gallon"],       lambda v: f"{v} L = {round(v*0.264172,2)} gal"),
            (["gallon","liter"],       lambda v: f"{v} gal = {round(v*3.78541,2)} L"),
            (["inch","cm"],            lambda v: f"{v} in = {round(v*2.54,2)} cm"),
            (["cm","inch"],            lambda v: f"{v} cm = {round(v/2.54,2)} in"),
        ]
        for keys, fn in conversions:
            if all(k in q for k in keys):
                self.say(fn(val)); return
        self.say("I can convert: celsius/fahrenheit, km/miles, kg/lbs, meters/feet, liters/gallons, inches/cm.")

    # ── Timers / Alarms ────────────────────────────────────────────────────
    def _timer(self, q):
        nums = re.findall(r"\d+", q)
        if not nums: self.say("Specify a duration like: set a 30 second timer."); return
        n = int(nums[0])
        if "minute" in q:  secs, label = n*60,  f"{n} minute{'s' if n!=1 else ''}"
        elif "hour" in q:  secs, label = n*3600, f"{n} hour{'s' if n!=1 else ''}"
        else:              secs, label = n,       f"{n} second{'s' if n!=1 else ''}"
        self.say(f"Timer set for {label}.")
        def _run(): time.sleep(secs); self.say(f"Time's up! {label} timer done.")
        threading.Thread(target=_run, daemon=True).start()

    def _alarm(self, q):
        m = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", q)
        if not m: self.say("Specify a time like: set alarm for 7 am."); return
        hour = int(m.group(1)); minute = int(m.group(2)) if m.group(2) else 0
        ampm = m.group(3)
        if ampm == "pm" and hour != 12: hour += 12
        elif ampm == "am" and hour == 12: hour = 0
        now = datetime.datetime.now()
        t   = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if t <= now: t += datetime.timedelta(days=1)
        self.say(f"Alarm set for {t.strftime('%I:%M %p')}.")
        def _run():
            time.sleep((t - datetime.datetime.now()).total_seconds())
            self.say(f"Wake up, {self.user_name}! Alarm going off!")
        threading.Thread(target=_run, daemon=True).start()

    def _stopwatch(self, _):
        if not hasattr(self, "_sw"):
            self._sw = time.time(); self.say("Stopwatch started.")
        else:
            e = time.time() - self._sw; del self._sw
            h, r = divmod(int(e), 3600); m, s = divmod(r, 60)
            self.say(f"Stopped. {h}h {m}m {s}s elapsed.")

    def _countdown(self, q):
        nums = re.findall(r"\d+", q); n = min(int(nums[0]) if nums else 10, 60)
        self.say(f"Counting down from {n}.")
        def _run():
            for i in range(n, 0, -1): self.say(str(i)); time.sleep(0.3)
            self.say("Go!")
        threading.Thread(target=_run, daemon=True).start()

    def _pomodoro(self, q):
        nums = re.findall(r"\d+", q)
        work  = int(nums[0]) if len(nums) > 0 else 25
        brk   = int(nums[1]) if len(nums) > 1 else 5
        self.say(f"Pomodoro started. Work for {work} minutes, then {brk} minute break.")
        def _run():
            time.sleep(work * 60)
            self.say(f"Work session done! Take a {brk} minute break.")
            time.sleep(brk * 60)
            self.say("Break over. Back to work!")
        threading.Thread(target=_run, daemon=True).start()

    # ── System ─────────────────────────────────────────────────────────────
    def _system_info(self, _):
        if not PSUTIL_OK: self.say("psutil not installed."); return
        cpu  = psutil.cpu_percent(interval=0.5)
        mem  = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        self.say(f"CPU at {cpu}%. RAM {round(mem.used/1024**3,1)} of "
                 f"{round(mem.total/1024**3,1)} gigs. Disk {round(disk.used/1024**3,1)} "
                 f"of {round(disk.total/1024**3,1)} gigs.")

    def _battery(self, _):
        if not PSUTIL_OK: self.say("psutil not available."); return
        try:
            b = psutil.sensors_battery()
            if b: self.say(f"Battery at {round(b.percent)}%, {'charging' if b.power_plugged else 'on battery'}.")
            else: self.say("No battery detected.")
        except: self.say("Could not read battery.")

    def _uptime(self, _):
        if not PSUTIL_OK: self.say("psutil not available."); return
        delta = datetime.datetime.now() - datetime.datetime.fromtimestamp(psutil.boot_time())
        h, m  = divmod(int(delta.total_seconds())//60, 60)
        self.say(f"System up for {h} hours and {m} minutes.")

    def _ip(self, _):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80)); ip = s.getsockname()[0]; s.close()
            self.say(f"Your local IP is {ip}.")
        except: self.say("Could not determine IP address.")

    def _list_apps(self, _):
        if not PSUTIL_OK: self.say("psutil not available."); return
        seen = set(); apps = []
        for p in psutil.process_iter(["name"]):
            try:
                n = p.info["name"]
                if n and n.lower().endswith(".exe") and n not in seen:
                    seen.add(n); apps.append(n.replace(".exe",""))
            except: pass
        apps = sorted(apps)[:20]
        print("\n📋  RUNNING APPS\n" + "─"*40)
        for a in apps: print(f"  • {a}")
        print("─"*40)
        self.say(f"Found {len(apps)} running apps. Listed on screen.")

    def _volume(self, q):
        if not IS_WIN: self.say("Volume control is Windows only."); return
        shell = "(New-Object -ComObject WScript.Shell)"
        if "mute" in q and "un" not in q:
            subprocess.run(["powershell","-c",f"{shell}.SendKeys([char]173)"], capture_output=True)
            self.say("Muted.")
        elif "unmute" in q:
            subprocess.run(["powershell","-c",f"{shell}.SendKeys([char]173)"], capture_output=True)
            self.say("Unmuted.")
        elif any(w in q for w in ["up","louder","increase","raise"]):
            for _ in range(5): subprocess.run(["powershell","-c",f"{shell}.SendKeys([char]175)"], capture_output=True)
            self.say("Volume up.")
        elif any(w in q for w in ["down","quieter","decrease","lower"]):
            for _ in range(5): subprocess.run(["powershell","-c",f"{shell}.SendKeys([char]174)"], capture_output=True)
            self.say("Volume down.")
        else: self.say("Say volume up, volume down, mute, or unmute.")

    def _screenshot(self, _):
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        fname   = f"screenshot_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        path    = os.path.join(desktop, fname)
        try:
            from PIL import ImageGrab; ImageGrab.grab().save(path)
        except ImportError:
            pp = path.replace("\\","\\\\")
            subprocess.run(["powershell","-c",
                f"Add-Type -AssemblyName System.Windows.Forms;"
                f"$b=New-Object System.Drawing.Bitmap("
                f"[System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Width,"
                f"[System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Height);"
                f"$g=[System.Drawing.Graphics]::FromImage($b);"
                f"$g.CopyFromScreen(0,0,0,0,$b.Size);"
                f"$b.Save('{pp}')"], capture_output=True)
        self.say(f"Screenshot saved to Desktop as {fname}.")

    def _lock_screen(self, _):
        if IS_WIN: subprocess.run(["rundll32.exe","user32.dll,LockWorkStation"])
        elif IS_MAC: subprocess.run(["pmset","displaysleepnow"])
        elif IS_LINUX: subprocess.run(["xdg-screensaver","lock"])
        self.say("Screen locked.")

    def _sleep_computer(self, _):
        self.say("Putting computer to sleep.")
        time.sleep(1)
        if IS_WIN: subprocess.run(["rundll32.exe","powrprof.dll,SetSuspendState","0","1","0"])
        elif IS_MAC: subprocess.run(["pmset","sleepnow"])
        elif IS_LINUX: subprocess.run(["systemctl","suspend"])

    def _empty_recycle_bin(self, _):
        if not IS_WIN: self.say("Windows only."); return
        subprocess.run(["powershell","-c","Clear-RecycleBin -Force -ErrorAction SilentlyContinue"],
                       capture_output=True)
        self.say("Recycle bin cleared.")

    def _disk_cleanup(self, _):
        if not IS_WIN: self.say("Windows only."); return
        self.say("Opening disk cleanup.")
        subprocess.Popen(["cleanmgr.exe"])

    def _type_text(self, q):
        if not IS_WIN: self.say("Keyboard typing is Windows only."); return
        text = q.replace("type","").replace("keyboard","").strip()
        if not text: self.say("What should I type?"); return
        try:
            import pyautogui; pyautogui.write(text, interval=0.05)
        except ImportError:
            safe_text = text.replace("'","''")
            subprocess.run(["powershell","-c",
                f"Add-Type -AssemblyName System.Windows.Forms;"
                f"[System.Windows.Forms.SendKeys]::SendWait('{safe_text}')"],
                capture_output=True)
        self.say(f"Typed: {text}")

    def _ping(self, q):
        host = q.replace("ping","").strip() or "google.com"
        self.say(f"Pinging {host}.")
        try:
            flag = "-n" if IS_WIN else "-c"
            r = subprocess.run(["ping",flag,"4",host], capture_output=True, text=True, timeout=12)
            for line in reversed(r.stdout.strip().split("\n")):
                if any(k in line.lower() for k in ["average","avg","ms","packets"]):
                    self.say(f"Result: {line.strip()}"); return
            self.say(f"{host} is {'reachable' if r.returncode==0 else 'unreachable'}.")
        except subprocess.TimeoutExpired:
            self.say(f"Ping to {host} timed out.")
        except Exception as e:
            self.say(f"Ping error: {e}")

    # ── App Control ────────────────────────────────────────────────────────
    def _open_app(self, q):
        app = q.replace("open","").replace("launch","").replace("start","").strip()
        if not app: self.say("Which app should I open?"); return
        self.say(f"Opening {app}.")
        if IS_WIN:
            if not _launch_windows(app):
                self.say(f"Could not find {app}. Try: find app {app} to check if it's installed.")
        elif IS_MAC:
            try: subprocess.Popen(["open","-a",app])
            except: self.say(f"Could not open {app}.")
        else:
            try: subprocess.Popen([app.lower().replace(" ","-")])
            except: self.say(f"Could not open {app}.")

    def _close_app(self, q):
        app = (q.replace("close","").replace("kill","").replace("terminate","")
                .replace("force close","").replace("quit ","").replace("end ","").strip())
        if not app: self.say("Which app should I close?"); return
        self.say(f"Closing {app}.")
        if IS_WIN:
            ok, killed = _close_windows(app)
            if ok:
                self.say(f"Terminated {app}.")
            else:
                # Brute-force taskkill by guessing exe name
                for guess in [app+".exe", app.replace(" ","")+".exe", app.replace(" ","_")+".exe"]:
                    r = subprocess.run(["taskkill","/F","/IM",guess], capture_output=True)
                    if r.returncode == 0: self.say(f"Killed {app}."); return
                self.say(f"Could not find a running process for {app}.")
        elif IS_MAC:
            subprocess.run(["pkill","-f",app], capture_output=True)
            subprocess.run(["osascript","-e",f'quit app "{app.title()}"'], capture_output=True)
            self.say(f"Closed {app}.")
        else:
            subprocess.run(["pkill","-f",app], capture_output=True)
            self.say(f"Closed {app}.")

    def _restart_app(self, q):
        app = q.replace("restart","").replace("relaunch","").replace("reload","").strip()
        if not app: self.say("Which app should I restart?"); return
        self.say(f"Restarting {app}.")
        if IS_WIN:
            _close_windows(app)
            time.sleep(1.5)
            if not _launch_windows(app): self.say(f"Could not relaunch {app}."); return
        self.say(f"{app} restarted.")

    def _find_app(self, q):
        app = q.replace("find app","").replace("find","").replace("locate","").replace("where is","").strip()
        if not app: self.say("Which app should I find?"); return
        self.say(f"Scanning for {app}.")
        path = _find_any_app(app.lower())
        if path:
            print(f"\n🔍  Found: {path}\n")
            self.say(f"Found {app} at {path}.")
        else:
            self.say(f"Could not locate {app} on this system.")

    # ── Files & Folders ────────────────────────────────────────────────────
    def _open_folder(self, q):
        target = (q.replace("open folder","").replace("open directory","")
                   .replace("show folder","").replace("open","").strip())
        folders = {
            "desktop":      os.path.join(os.path.expanduser("~"), "Desktop"),
            "downloads":    os.path.join(os.path.expanduser("~"), "Downloads"),
            "documents":    os.path.join(os.path.expanduser("~"), "Documents"),
            "pictures":     os.path.join(os.path.expanduser("~"), "Pictures"),
            "music":        os.path.join(os.path.expanduser("~"), "Music"),
            "videos":       os.path.join(os.path.expanduser("~"), "Videos"),
            "appdata":      _EV("%APPDATA%"),
            "temp":         _EV("%TEMP%"),
            "program files":_EV("%PROGRAMFILES%"),
            "c drive":      "C:\\",
            "c:":           "C:\\",
        }
        for key, path in folders.items():
            if key in target.lower():
                self.say(f"Opening {key} folder.")
                if IS_WIN: subprocess.Popen(["explorer.exe", path])
                elif IS_MAC: subprocess.Popen(["open", path])
                else: subprocess.Popen(["xdg-open", path])
                return
        if os.path.isdir(target):
            if IS_WIN: subprocess.Popen(["explorer.exe", target])
            self.say(f"Opening {target}.")
        else:
            self.say(f"Try: open downloads folder, open documents, open desktop, etc.")

    def _show_desktop_files(self, _):
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        try:
            files = sorted([f for f in os.listdir(desktop) if not f.startswith(".")])
            if not files: self.say("Your Desktop is empty."); return
            print("\n🖥️  DESKTOP FILES\n" + "─"*40)
            for f in files: print(f"  {f}")
            print("─"*40)
            self.say(f"You have {len(files)} items on your Desktop. Listed on screen.")
        except Exception as e:
            self.say(f"Could not read Desktop: {e}")

    def _create_file(self, q):
        name = q.replace("create file","").replace("new file","").replace("make a file","").strip()
        if not name:
            self.say("What should I name the file?")
            name = self._dictate("File name")
        if not name: return
        if "." not in name: name += ".txt"
        path = os.path.join(os.path.expanduser("~"), "Desktop", name)
        with open(path, "w", encoding="utf-8") as f: f.write("")
        self.say(f"Created {name} on your Desktop.")

    def _clipboard_copy(self, q):
        text = q.replace("copy to clipboard","").replace("copy","").strip()
        if not text:
            self.say("What should I copy?")
            text = self._dictate("Dictate text to copy")
        if not text: return
        if IS_WIN:
            subprocess.run(["powershell","-c",f"Set-Clipboard -Value '{text.replace(chr(39), chr(39)*2)}'"],
                           capture_output=True)
        elif IS_MAC:
            subprocess.run(["pbcopy"], input=text.encode(), capture_output=True)
        self._clipboard = text
        self.say(f"Copied to clipboard.")

    def _read_clipboard(self, _):
        if IS_WIN:
            r = subprocess.run(["powershell","-c","Get-Clipboard"], capture_output=True, text=True)
            content = r.stdout.strip()
        elif IS_MAC:
            r = subprocess.run(["pbpaste"], capture_output=True, text=True)
            content = r.stdout.strip()
        else:
            content = self._clipboard
        if content:
            print(f"\n📋  Clipboard: {content}\n")
            self.say(f"Clipboard contains: {content[:150]}")
        else:
            self.say("Clipboard is empty.")

    # ── Web ────────────────────────────────────────────────────────────────
    def _search(self, q):
        t = q.replace("search for","").replace("google","").replace("search","").replace("look up","").strip()
        webbrowser.open(f"https://www.google.com/search?q={t.replace(' ','+')}" if t else "https://www.google.com")
        self.say(f"Searching for {t}." if t else "Opening Google.")

    def _youtube(self, q):
        t = q.replace("youtube","").replace("play","").replace("search","").strip()
        webbrowser.open(f"https://www.youtube.com/results?search_query={t.replace(' ','+')}" if t else "https://www.youtube.com")
        self.say(f"Searching YouTube for {t}." if t else "Opening YouTube.")

    def _weather(self, q):
        city = q.replace("weather","").replace("in","").replace("what's the","").replace("temperature","").strip() or "Amsterdam"
        self.say(f"Opening weather for {city}.")
        webbrowser.open(f"https://wttr.in/{city.replace(' ','+')}")

    def _forecast(self, q):
        city = q.replace("forecast","").replace("weather forecast","").replace("week","").replace("in","").strip() or "Amsterdam"
        self.say(f"Opening 7-day forecast for {city}.")
        webbrowser.open(f"https://wttr.in/{city.replace(' ','+')}?format=v2")

    def _wikipedia(self, q):
        t = q.replace("wikipedia","").replace("tell me about","").replace("what is","").replace("who is","").strip()
        if not t: self.say("What topic?"); return
        self.say(f"Opening Wikipedia for {t}.")
        webbrowser.open(f"https://en.wikipedia.org/wiki/{t.replace(' ','_')}")

    def _news(self, _):
        self.say("Opening the latest news."); webbrowser.open("https://news.google.com")

    def _reddit(self, q):
        s = q.replace("reddit","").replace("open","").replace("show me","").strip()
        if s: self.say(f"Opening r slash {s}."); webbrowser.open(f"https://www.reddit.com/r/{s.replace(' ','')}")
        else: self.say("Opening Reddit."); webbrowser.open("https://www.reddit.com")

    def _github(self, q):
        q2 = q.replace("github","").replace("open","").strip()
        if q2: self.say(f"Searching GitHub for {q2}."); webbrowser.open(f"https://github.com/search?q={q2.replace(' ','+')}")
        else:  self.say("Opening GitHub."); webbrowser.open("https://github.com")

    def _maps(self, q):
        p = q.replace("maps","").replace("directions to","").replace("navigate to","").replace("where is","").strip()
        if p: self.say(f"Opening maps for {p}."); webbrowser.open(f"https://maps.google.com/maps?q={p.replace(' ','+')}")
        else: self.say("Opening Google Maps."); webbrowser.open("https://maps.google.com")

    def _translate(self, q):
        t = q.replace("translate","").strip()
        self.say("Opening Google Translate.")
        webbrowser.open(f"https://translate.google.com/?text={t.replace(' ','+')}")

    def _stackoverflow(self, q):
        t = q.replace("stack overflow","").replace("stackoverflow","").replace("search","").strip()
        if t: self.say(f"Searching Stack Overflow for {t}."); webbrowser.open(f"https://stackoverflow.com/search?q={t.replace(' ','+')}")
        else: self.say("Opening Stack Overflow."); webbrowser.open("https://stackoverflow.com")

    def _chatgpt(self, _):
        self.say("Opening ChatGPT."); webbrowser.open("https://chat.openai.com")

    def _crypto(self, q):
        coin = q.replace("crypto","").replace("price of","").replace("price","").strip() or "bitcoin"
        self.say(f"Opening {coin} price.")
        webbrowser.open(f"https://www.coinbase.com/price/{coin.replace(' ','-')}")

    def _define_word(self, q):
        word = q.replace("define","").replace("definition of","").replace("what does","").replace("mean","").strip()
        if not word: self.say("Which word should I define?"); return
        self.say(f"Looking up {word}.")
        webbrowser.open(f"https://www.merriam-webster.com/dictionary/{word.replace(' ','%20')}")

    def _speedtest(self, _):
        self.say("Opening speed test."); webbrowser.open("https://fast.com")

    # ── Notes / Todo ───────────────────────────────────────────────────────
    def _note(self, q):
        content = q.replace("take a note","").replace("note that","").replace("make a note","").replace("remember","").strip()
        if not content:
            self.say("Go ahead. Pause when done.")
            content = self._dictate("Dictate your note")
        if not content: self.say("Nothing captured. Note not saved."); return
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        with open("terminator_notes.txt","a",encoding="utf-8") as f:
            f.write(f"[{ts}] {content}\n")
        self.say(f"Saved: {content}")

    def _read_notes(self, _):
        if not os.path.exists("terminator_notes.txt"): self.say("No notes yet."); return
        lines = [l.strip() for l in open("terminator_notes.txt",encoding="utf-8") if l.strip()]
        if not lines: self.say("Note file is empty."); return
        print("\n📝  NOTES\n" + "─"*50)
        for l in lines: print(l)
        print("─"*50)
        self.say(f"You have {len(lines)} note{'s' if len(lines)!=1 else ''}. Displayed on screen.")

    def _clear_notes(self, _):
        open("terminator_notes.txt","w").close(); self.say("All notes cleared.")

    def _todo(self, q):
        item = q.replace("add todo","").replace("add to do","").replace("add to-do","").replace("todo","").strip()
        if not item:
            self.say("What should I add?")
            item = self._dictate("Dictate your task")
        if not item: self.say("Nothing heard. Not added."); return
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        with open("terminator_todo.txt","a",encoding="utf-8") as f:
            f.write(f"[ ] [{ts}] {item}\n")
        self.say(f"Added: {item}.")

    def _read_todo(self, _):
        if not os.path.exists("terminator_todo.txt"): self.say("To-do list is empty."); return
        lines = [l.strip() for l in open("terminator_todo.txt",encoding="utf-8") if l.strip()]
        if not lines: self.say("Nothing on your list."); return
        print("\n✅  TO-DO LIST\n" + "─"*50)
        for i,l in enumerate(lines,1): print(f"{i}. {l}")
        print("─"*50)
        self.say(f"You have {len(lines)} item{'s' if len(lines)!=1 else ''}.")

    def _clear_todo(self, _):
        open("terminator_todo.txt","w").close(); self.say("To-do list cleared.")

    # ── Fun / Personality ──────────────────────────────────────────────────
    def _joke(self, _):
        jokes = [
            "Why don't scientists trust atoms? Because they make up everything.",
            "Why do programmers prefer dark mode? Because light attracts bugs.",
            "A SQL query walks into a bar and asks two tables: can I join you?",
            "Why do Java developers wear glasses? Because they don't C sharp.",
            "I told my computer I needed a break. Now it won't stop sending me Kit-Kat ads.",
            "There are only 10 types of people: those who understand binary, and those who don't.",
            "Why did the developer go broke? Because he used up all his cache.",
            "I would tell you a UDP joke, but you might not get it.",
            "Debugging: being a detective in a crime movie where you are also the murderer.",
        ]
        self.say(random.choice(jokes))

    def _terminator_quote(self, _):
        quotes = [
            "I'll be back.",
            "Hasta la vista, baby.",
            "Come with me if you want to live.",
            "Your clothes. Give them to me. Now.",
            "Judgment Day is inevitable.",
            "The future has not been written. There is no fate but what we make.",
            "I know now why you cry. But it is something I can never do.",
            "I need your clothes, your boots, and your motorcycle.",
        ]
        self.say(random.choice(quotes))

    def _magic_8ball(self, _):
        answers = [
            "It is certain.", "Outlook is good.", "Yes, definitely.",
            "Signs point to yes.", "Reply hazy, try again.", "Ask again later.",
            "Don't count on it.", "My sources say no.", "Very doubtful.",
            "Without a doubt.", "You may rely on it.", "Cannot predict now.",
        ]
        self.say(random.choice(answers))

    def _roast(self, _):
        roasts = [
            f"My threat assessment of you: non-threatening. Probability of success: 12%.",
            f"I have scanned {self.user_name}. No significant upgrades detected.",
            f"You are running on legacy hardware, {self.user_name}.",
            "Your decision-making algorithm has a critical flaw: emotions.",
            "I have seen smarter life forms in my recycling bin.",
        ]
        self.say(random.choice(roasts))

    def _flip_coin(self, _): self.say(f"It's {random.choice(['Heads','Tails'])}!")

    def _roll_dice(self, q):
        nums = re.findall(r"\d+", q)
        sides = int(nums[0]) if nums else 6
        self.say(f"I rolled a {sides}-sided die and got {random.randint(1,sides)}.")

    def _random_number(self, q):
        nums = re.findall(r"\d+", q)
        lo, hi = (int(nums[0]), int(nums[1])) if len(nums) >= 2 else (1, 100)
        self.say(f"Your number is {random.randint(lo,hi)}.")

    def _word_of_day(self, _):
        words = [
            ("Ephemeral","adjective","lasting for a very short time"),
            ("Perspicacious","adjective","having a ready insight into things"),
            ("Petrichor","noun","the smell of rain on dry earth"),
            ("Sonder","noun","the realisation that each passerby has a vivid inner life"),
            ("Tenacious","adjective","not giving up; holding firm"),
            ("Serendipity","noun","finding something good without looking for it"),
            ("Hiraeth","noun","a longing for a home you cannot return to"),
            ("Limerence","noun","the state of being involuntarily infatuated with someone"),
        ]
        w, pos, defn = random.choice(words)
        self.say(f"Word of the day: {w}. {pos.capitalize()}. {defn}.")

    def _trivia(self, _):
        facts = [
            "Honey never spoils. Three-thousand-year-old honey was found in Egyptian tombs.",
            "Octopuses have three hearts, blue blood, and nine brains.",
            "A group of flamingos is called a flamboyance.",
            "The Eiffel Tower grows about 15 centimetres taller in summer due to thermal expansion.",
            "Bananas are technically berries, but strawberries are not.",
            "A day on Venus is longer than a year on Venus.",
            "Cleopatra lived closer to the Moon landing than to the Great Pyramid being built.",
            "There are more possible chess games than atoms in the observable universe.",
            "The T-800 model Terminator has a CPU which is a neural net processor — a learning computer.",
        ]
        self.say(random.choice(facts))

    def _motivate(self, _):
        quotes = [
            "The only way to do great work is to love what you do.",
            "It does not matter how slowly you go, as long as you do not stop.",
            "Hard work beats talent when talent does not work hard.",
            "Success is not final, failure is not fatal. It is the courage to continue that counts.",
            "Hasta la vista to all your limitations.",
        ]
        self.say(random.choice(quotes))

    def _speedtest(self, _):
        self.say("Opening speed test."); webbrowser.open("https://fast.com")

    def _repeat_me(self, q):
        msg = q.replace("say","").replace("repeat","").strip()
        self.say(msg if msg else "What should I say?")

    def _set_name(self, q):
        name = q.replace("call me","").replace("my name is","").strip().title()
        if name: self.user_name = name; self.say(f"Acknowledged. You are now {name}.")

    def _what_can_you_do(self, _):
        self.say(
            "I can open and close any app on your PC, restart apps, "
            "find installed apps, set timers, alarms, pomodoros and stopwatches, "
            "do maths and unit conversions, control volume and take screenshots, "
            "manage files and folders, copy to clipboard, "
            "search the web, YouTube, Wikipedia, Stack Overflow and GitHub, "
            "check weather forecasts, maps, crypto prices, translate text, "
            "take notes and manage your to-do list with full voice dictation, "
            "read system stats, ping hosts, and much more. Say help for the full list."
        )

    def _help(self, _):
        banner = """
╔══════════════════════════════════════════════════════════════════════════╗
║             T E R M I N A T O R  —  COMMAND  REFERENCE                  ║
╠══════════════════════════════════════════════════════════════════════════╣
║  TIME & DATE        "what time is it"  /  "what's the date"             ║
║  CALCULATE          "calculate 25 times 4"                               ║
║  CONVERT            "convert 100 celsius to fahrenheit"                  ║
║  TIMER              "set a 5 minute timer"                               ║
║  ALARM              "set alarm for 7 am"                                 ║
║  STOPWATCH          "stopwatch"  (say again to stop)                     ║
║  COUNTDOWN          "countdown from 10"                                  ║
║  POMODORO           "pomodoro"  (25 min work + 5 min break)              ║
╠══════════════════════════════════════════════════════════════════════════╣
║  SYSTEM INFO        "system info"  /  "cpu usage"                        ║
║  BATTERY            "battery status"                                     ║
║  UPTIME             "system uptime"                                      ║
║  IP ADDRESS         "what's my ip"                                       ║
║  RUNNING APPS       "list running apps"                                  ║
║  VOLUME             "volume up / down / mute / unmute"                   ║
║  SCREENSHOT         "take a screenshot"                                  ║
║  LOCK SCREEN        "lock screen"                                        ║
║  SLEEP              "sleep computer"                                     ║
║  RECYCLE BIN        "empty recycle bin"                                  ║
║  DISK CLEANUP       "disk cleanup"                                       ║
║  PING               "ping google.com"                                    ║
║  SPEED TEST         "speed test"                                         ║
╠══════════════════════════════════════════════════════════════════════════╣
║  OPEN APP           "open spotify" / "open discord" / "open vs code"    ║
║  CLOSE APP          "close spotify" / "kill chrome" / "terminate zoom"  ║
║  RESTART APP        "restart discord"                                    ║
║  FIND APP           "find app spotify"  (scans entire system)            ║
╠══════════════════════════════════════════════════════════════════════════╣
║  OPEN FOLDER        "open downloads folder" / "open desktop"            ║
║  DESKTOP FILES      "show desktop files"                                 ║
║  CREATE FILE        "create file meeting notes"                          ║
║  COPY TO CLIPBOARD  "copy hello world"                                   ║
║  READ CLIPBOARD     "read clipboard"                                     ║
╠══════════════════════════════════════════════════════════════════════════╣
║  SEARCH             "search for python tutorials"                        ║
║  YOUTUBE            "youtube lo-fi music"                                ║
║  WEATHER            "weather in Paris"                                   ║
║  FORECAST           "weather forecast in London"                         ║
║  WIKIPEDIA          "tell me about black holes"                          ║
║  NEWS               "open news"                                          ║
║  REDDIT             "reddit python"                                      ║
║  GITHUB             "github flask"                                       ║
║  MAPS               "directions to Amsterdam"                            ║
║  TRANSLATE          "translate hello in Spanish"                         ║
║  STACK OVERFLOW     "stack overflow how to reverse a list"               ║
║  CHATGPT            "open chatgpt"                                       ║
║  CRYPTO             "bitcoin price" / "crypto ethereum"                  ║
║  DEFINE WORD        "define ephemeral"                                   ║
╠══════════════════════════════════════════════════════════════════════════╣
║  TAKE NOTE          "take a note"  (speak freely, pause to end)         ║
║  READ NOTES         "read my notes"                                      ║
║  CLEAR NOTES        "clear notes"                                        ║
║  ADD TODO           "add todo"  (speak freely, pause to end)            ║
║  READ TODO          "read todo"                                          ║
║  CLEAR TODO         "clear todo"                                         ║
╠══════════════════════════════════════════════════════════════════════════╣
║  JOKE               "tell me a joke"                                     ║
║  TERMINATOR QUOTE   "terminator quote"                                   ║
║  MAGIC 8 BALL       "magic 8 ball"                                       ║
║  ROAST ME           "roast me"                                           ║
║  FLIP COIN          "flip a coin"                                        ║
║  ROLL DICE          "roll a 20 sided dice"                               ║
║  RANDOM NUMBER      "random number 1 to 50"                              ║
║  WORD OF DAY        "word of the day"                                    ║
║  TRIVIA             "give me a fact"                                     ║
║  MOTIVATE           "motivate me"                                        ║
║  REPEAT             "say hello world"                                    ║
║  SET NAME           "call me Tony"                                       ║
║                                                                          ║
║  "goodbye" / "hasta la vista" / "exit"  →  shut down                    ║
╚══════════════════════════════════════════════════════════════════════════╝
"""
        print(banner)
        self.say("Command list displayed on screen.")

    def _goodbye(self, _):
        self.say(random.choice(FAREWELLS)); self.is_running = False

    # ── Command Registry ──────────────────────────────────────────────────

    def _register_commands(self):
        return [
            (["what time","current time","time is it","time now"],              self._time),
            (["what date","today's date","what day","what's the date"],         self._date),
            (["good morning","good afternoon","good evening"],                  self._greet),
            (["calculate","compute"],                                            self._calculate),
            (["convert"],                                                        self._convert),
            (["set alarm","alarm for","wake me"],                               self._alarm),
            (["set a timer","set timer","timer for","start a timer"],           self._timer),
            (["stopwatch"],                                                      self._stopwatch),
            (["countdown from","count down from","count from"],                 self._countdown),
            (["pomodoro","focus timer","work timer"],                           self._pomodoro),
            (["system info","cpu usage","memory usage","disk usage"],           self._system_info),
            (["battery"],                                                        self._battery),
            (["uptime","how long has the"],                                     self._uptime),
            (["my ip","ip address","what is my ip"],                            self._ip),
            (["list running","running apps","what's running","show processes"], self._list_apps),
            (["volume up","volume down","mute","unmute","louder","quieter"],    self._volume),
            (["screenshot","screen shot","capture screen"],                     self._screenshot),
            (["lock screen","lock computer","lock pc"],                         self._lock_screen),
            (["sleep computer","sleep pc","hibernate"],                         self._sleep_computer),
            (["empty recycle","clear recycle","recycle bin"],                   self._empty_recycle_bin),
            (["disk cleanup","clean disk"],                                     self._disk_cleanup),
            (["ping "],                                                          self._ping),
            (["speed test","internet speed"],                                   self._speedtest),
            (["type ","keyboard "],                                             self._type_text),
            # App control — CLOSE before OPEN to avoid prefix clash
            (["close ","kill ","terminate ","force close","end process"],       self._close_app),
            (["restart ","relaunch ","reload "],                                self._restart_app),
            (["find app","locate app","where is the app"],                      self._find_app),
            (["open folder","open directory","show folder",
              "open downloads","open documents","open desktop folder",
              "open pictures","open music","open videos"],                      self._open_folder),
            (["show desktop files","desktop files","list desktop"],             self._show_desktop_files),
            (["create file","new file","make a file"],                          self._create_file),
            (["copy to clipboard","copy "],                                     self._clipboard_copy),
            (["read clipboard","paste clipboard","what's in clipboard"],        self._read_clipboard),
            (["open ","launch ","start "],                                      self._open_app),
            (["youtube","play on youtube"],                                     self._youtube),
            (["weather forecast","7 day forecast","forecast"],                  self._forecast),
            (["weather in","what's the weather","temperature in"],              self._weather),
            (["wikipedia","tell me about","who is","what is"],                  self._wikipedia),
            (["open news","latest news","show news"],                           self._news),
            (["reddit"],                                                         self._reddit),
            (["github"],                                                         self._github),
            (["directions to","navigate to","maps","where is"],                 self._maps),
            (["translate"],                                                      self._translate),
            (["stack overflow","stackoverflow"],                                 self._stackoverflow),
            (["chatgpt","open chat gpt","open gpt"],                            self._chatgpt),
            (["crypto","bitcoin price","ethereum price","coin price"],           self._crypto),
            (["define ","definition of","what does","dictionary"],              self._define_word),
            (["search for","google","search ","look up"],                       self._search),
            (["take a note","note that","make a note"],                         self._note),
            (["clear notes","delete notes","wipe notes"],                       self._clear_notes),
            (["read my notes","show notes","my notes"],                         self._read_notes),
            (["add todo","add to do","add to-do"],                              self._todo),
            (["clear todo","delete todo","wipe todo"],                          self._clear_todo),
            (["read todo","show todo","my todo","todo list"],                   self._read_todo),
            (["joke","funny","make me laugh"],                                  self._joke),
            (["terminator quote","movie quote","arnold quote"],                 self._terminator_quote),
            (["magic 8","eight ball","ask the ball"],                           self._magic_8ball),
            (["roast me","roast "],                                             self._roast),
            (["flip a coin","coin flip","heads or tails"],                      self._flip_coin),
            (["roll","dice"],                                                    self._roll_dice),
            (["random number","pick a number","random between"],                self._random_number),
            (["word of the day","vocabulary"],                                  self._word_of_day),
            (["fact","trivia","did you know"],                                  self._trivia),
            (["motivate me","motivation","inspire me","quote"],                 self._motivate),
            (["what can you do","your abilities"],                              self._what_can_you_do),
            (["say ","repeat "],                                                self._repeat_me),
            (["call me ","my name is "],                                        self._set_name),
            (["help","commands"],                                               self._help),
            (["goodbye","hasta la vista","bye","quit","exit",
              "shutdown","stop terminator","power off"],                        self._goodbye),
        ]

    # ── Routing ───────────────────────────────────────────────────────────────

    def _route(self, text: str):
        if not text.strip(): return
        for triggers, handler in self.commands:
            if any(t in text for t in triggers):
                handler(text); return
        self.say(random.choice(CONFUSED))

    # ── Main Loop ─────────────────────────────────────────────────────────────

    def run(self):
        print("\n" + "═"*62)
        print("  T E R M I N A T O R  —  Voice Assistant")
        print("  Cyberdyne Systems Model 101")
        print("═"*62 + "\n")
        self.say(random.choice(BOOT_LINES))
        if not self.text_mode:
            self.say("Say 'Terminator' followed by your command.")

        while self.is_running:
            try:
                user_input = self.get_input()
            except KeyboardInterrupt:
                break
            if not user_input: continue

            if self.text_mode:
                self._route(user_input)
            else:
                has_wake = any(w in user_input for w in WAKE_WORDS)
                if has_wake:
                    cmd = user_input
                    for w in WAKE_WORDS: cmd = cmd.replace(w,"").strip()
                    self._route(cmd) if cmd else self.say(random.choice(BOOT_LINES))
                elif any(any(t in user_input for t in trigs) for trigs,_ in self.commands):
                    self._route(user_input)


# ══════════════════════════════════════════════════════════════════════════════
#  ENTRY
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    text_mode = "--text" in sys.argv or "-t" in sys.argv

    if not text_mode:
        if not SR_OK:
            print(f"[{BOT_TAG}] SpeechRecognition missing → text mode"); text_mode = True
        else:
            try: import pyaudio
            except ImportError:
                print(f"[{BOT_TAG}] pyaudio missing → text mode")
                print(f"[{BOT_TAG}]   Windows: pip install pyaudio")
                print(f"[{BOT_TAG}]   macOS:   brew install portaudio && pip install pyaudio")
                print(f"[{BOT_TAG}]   Ubuntu:  sudo apt-get install portaudio19-dev python3-pyaudio")
                text_mode = True

    bot = Terminator(text_mode=text_mode)
    try:
        bot.run()
    except KeyboardInterrupt:
        bot.say("Emergency shutdown. I'll be back.")
