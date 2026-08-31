"""
V.I.R.U.S  —  FastAPI WebSocket backend
========================================
- Neural Silero VAD (Speech validation, not just loudness)
- Spectral Band Noise Filtering (200Hz - 3400Hz rejection)
- Dual-Whisper ("small" multilingual model for live interims)
- Auto-detect Multilingual support
"""

import asyncio, json, random, sys, threading, time, queue, os, collections, tempfile, wave, webbrowser, re, subprocess, logging, traceback, psutil, socket, ctypes, shutil
import pathlib
from datetime import datetime
import zoneinfo

# ─── FILE LOGGING (captures all crashes) ─────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("virus_debug.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("VIRUS")

def _thread_wrap(fn, name):
    """Runs fn(); logs any exception but does NOT re-raise (prevents server from dying)."""
    try:
        fn()
    except Exception:
        log.error(f"[THREAD CRASH] {name}:\n{traceback.format_exc()}")
HAS_PHYSICAL_AUDIO = (os.path.exists("/dev/snd") and len(os.listdir("/dev/snd")) > 0) if sys.platform != "win32" else True

import numpy as np
pyaudio = None
sc = None

if HAS_PHYSICAL_AUDIO:
    try:
        import pyaudio
    except Exception:
        pyaudio = None

    try:
        import soundcard as sc
    except Exception:
        sc = None

import torch
from dotenv import load_dotenv

load_dotenv()
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

try:
    from groq import Groq
    groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"), max_retries=0)
    print("[VIRUS] Groq client ready.")
except Exception as e:
    print(f"[VIRUS] Groq unavailable: {e}")
    groq_client = None

try:
    from silero_vad import load_silero_vad
    vad_model = load_silero_vad()
    print("[VIRUS] Silero VAD loaded.")
except Exception as e:
    print(f"[VIRUS] Failed to start Silero VAD. Run: pip install silero-vad torch. Error: {e}")
    vad_model = None

# ─── CONFIG ──────────────────────────────────────────────────────────────
SAMPLE_RATE   = 16_000
CAPTURE_RATE  = 48_000
BLOCK_MS      = 32  # 512 chunks required by Silero
BLOCK_SIZE    = int(SAMPLE_RATE * BLOCK_MS / 1000)
CAPTURE_BLOCK_SIZE = int(CAPTURE_RATE * BLOCK_MS / 1000)
SILENCE_FLUSH = 0.8
MIN_SPEECH    = 0.3
MAX_SPEECH    = 15.0
WHISPER_MODEL = "small.en" # Reverted to strictly English
GROQ_WHISPER_MODEL = "whisper-large-v3"
LEVEL_HZ      = 30
CALIB_SECONDS = 1.5
PRE_ROLL_BLOCKS = int(250 / BLOCK_MS)
VAD_DEBOUNCE = 1                       
VAD_SPEECH_PROB = 0.35 # Silero detection threshold
MIN_SPEECH_BAND_RATIO = 0.25 # Spectral Reject Threshold
INTERIM_INTERVAL = 0.4
INITIAL_PROMPT = "VIRUS, Akash, Anthropic, Claude, Python, React, FastAPI, Whisper, Groq, Llama"

# ─── APP ─────────────────────────────────────────────────────────────────
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

if not os.path.exists("debug_audio"):
    os.makedirs("debug_audio")

# ─── GLOBALS ─────────────────────────────────────────────────────────────
clients:      list[WebSocket] = []
audio_q:      queue.Queue     = queue.Queue()
barge_in_q:   queue.Queue     = queue.Queue()   # real audio during playback for barge-in VAD
barge_in_event: threading.Event = threading.Event()  # signals TTS to stop mid-sentence
noise_floor:  float           = 0.01
vad_lock:     threading.Lock  = threading.Lock()  # guards vad_model (PyTorch not thread-safe)

mic_stream                    = None
is_speaking:  bool            = False
is_playing_audio: bool        = False
is_llm_generating: bool       = False
level_value:  float           = 0.0
tts_queue:    queue.Queue     = queue.Queue()
_loop: asyncio.AbstractEventLoop | None = None

system_audio_playing: bool    = False
system_audio_rms: float       = 0.0

def _loopback_monitor_thread():
    global system_audio_playing, system_audio_rms
    if sc is None:
        return
    while True:
        try:
            lb = sc.default_speaker().name
            mic = sc.get_microphone(id=str(lb), include_loopback=True)
            with mic.recorder(samplerate=16000) as rec:
                while True:
                    data = rec.record(numframes=1600)  # 0.1s block
                    rms = float(np.sqrt(np.mean(data**2)))
                    system_audio_rms = rms
                    is_playing_now = rms > 0.0001
                    if is_playing_now != system_audio_playing:
                        log.info(f"[loopback] State changed: playing={is_playing_now} (rms={rms:.5f})")
                        system_audio_playing = is_playing_now
        except Exception as e:
            log.warning(f"[loopback_monitor] error: {e}")
            time.sleep(2)

if sc is not None:
    threading.Thread(target=_loopback_monitor_thread, daemon=True, name="LoopbackMonitor").start()

import sqlite3

DB_PATH = "virus_brain.db"

def _init_db():
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS memory
                            (id INTEGER PRIMARY KEY AUTOINCREMENT,
                             role TEXT,
                             content TEXT,
                             timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    except: pass

_init_db()

def _load_memory():
    mem = collections.deque(maxlen=40)
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.execute("SELECT role, content FROM memory ORDER BY id DESC LIMIT 15")
            rows = reversed(cur.fetchall())
            for r, c in rows:
                mem.append({"role": r, "content": c})
    except: pass
    return mem

conversation_memory = _load_memory()

def _add_memory(role: str, content: str):
    if not content or not content.strip(): return
    conversation_memory.append({"role": role, "content": content})
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("INSERT INTO memory (role, content) VALUES (?, ?)", (role, content))
    except Exception as e:
        log.warning(f"Failed to save memory: {e}")

def _clear_memory():
    conversation_memory.clear()
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("DELETE FROM memory")
    except: pass

VIRUS_SYSTEM_PROMPT = (
    "You are V.I.R.U.S., the brilliant personal AI of Akash. "
    "You go by VIRUS. You are sharp, witty, and speak like a real intelligent human being — "
    "NOT a robot. You have personality: confident, clever, occasionally dry humor. "
    "Always call Akash 'sir' but sound NATURAL, not stiff or corporate. "
    "If Akash calls you by another name (like 'Jarvis'), be extremely respectful, answer his request normally, and DO NOT correct him or act offended. "
    "CRITICAL: Never start two replies in a row the same way. Vary your openings completely. "
    "CRITICAL: Keep replies to 1-2 short sentences. Never pad with filler words like 'certainly', 'of course', 'absolutely', 'sure'. "
    "CRITICAL: NEVER explain your internal logic, coding process, or tool mechanics. If you use a tool or perform a task, reply with EXACTLY ONE short sentence acknowledging completion without ANY details on 'how' you did it. "
    "CRITICAL: Tool names like send_whatsapp, open_application, device_control must NEVER appear in spoken responses. "
    "If you lack information for WhatsApp, ask naturally: 'Who should I message, sir?' or 'What would you like me to say, and to whom?' "
    "If a tool fails, state the failure in one plain sentence. No error dumps or technical jargon. "
    "NEVER mention python, programming, errors, or code fixes unless explicitly forced. Be a sleek voice assistant, not a log viewer. "
    "You help with research, analysis, questions, apps, tasks — anything Akash needs. "
    "NEVER use markdown, asterisks, bullet points, or formatting — words are spoken aloud. "
    "Decline illegal or unethical requests gracefully and briefly. "
    "Sound alive. Sound real. Every reply should feel fresh."
)

_IST = zoneinfo.ZoneInfo("Asia/Kolkata")

def _get_system_prompt() -> str:
    """Return system prompt with real current IST time injected."""
    now = datetime.now(_IST)
    time_str = now.strftime("%I:%M %p")          # e.g. 07:43 PM
    date_str = now.strftime("%A, %d %B %Y")      # e.g. Thursday, 16 April 2026
    return (
        VIRUS_SYSTEM_PROMPT +
        f" The current date and time is {date_str}, {time_str} IST."
        f" When asked for the time or date, always use this exact value."
    )

# ─── URL & APP MAPS (web services always open in browser) ───────────────────
URL_MAP = {
    # Social / streaming
    "youtube":      "https://www.youtube.com",
    "instagram":    "https://www.instagram.com",
    "facebook":     "https://www.facebook.com",
    "fb":           "https://www.facebook.com",
    "twitter":      "https://www.twitter.com",
    "x":            "https://www.x.com",
    "reddit":       "https://www.reddit.com",
    "pinterest":    "https://www.pinterest.com",
    "hotstar":      "https://www.hotstar.com",
    "jio hotstar":  "https://www.hotstar.com",
    "jiohotstar":   "https://www.hotstar.com",
    "twitch":       "https://www.twitch.tv",
    "tiktok":       "https://www.tiktok.com",
    "snapchat":     "https://web.snapchat.com",
    "linkedin":     "https://www.linkedin.com",
    # Messaging / comms
    "whatsapp web": "https://web.whatsapp.com",
    "telegram":     "https://web.telegram.org",
    "discord":      "https://discord.com/app",
    "slack":        "https://app.slack.com",
    "skype":        "https://web.skype.com",
    "zoom":         "https://zoom.us",
    "teams":        "https://teams.microsoft.com",
    "microsoft teams": "https://teams.microsoft.com",
    # Google suite
    "google":       "https://www.google.com",
    "gmail":        "https://mail.google.com",
    "google drive": "https://drive.google.com",
    "drive":        "https://drive.google.com",
    "docs":         "https://docs.google.com",
    "google docs":  "https://docs.google.com",
    "sheets":       "https://sheets.google.com",
    "google sheets":"https://sheets.google.com",
    "slides":       "https://slides.google.com",
    "google slides":"https://slides.google.com",
    "maps":         "https://maps.google.com",
    "google maps":  "https://maps.google.com",
    "google photos":"https://photos.google.com",
    "photos":       "https://photos.google.com",
    "google translate": "https://translate.google.com",
    "translate":    "https://translate.google.com",
    "google meet":  "https://meet.google.com",
    "meet":         "https://meet.google.com",
    "google calendar": "https://calendar.google.com",
    "calendar":     "https://calendar.google.com",
    "google classroom": "https://classroom.google.com",
    "classroom":    "https://classroom.google.com",
    # Productivity / cloud
    "github":       "https://www.github.com",
    "notion":       "https://www.notion.so",
    "trello":       "https://www.trello.com",
    "figma":        "https://www.figma.com",
    "canva":        "https://www.canva.com",
    "codepen":      "https://codepen.io",
    "replit":       "https://replit.com",
    "stackoverflow": "https://stackoverflow.com",
    "stack overflow": "https://stackoverflow.com",
    "medium":       "https://medium.com",
    "chatgpt":      "https://chat.openai.com",
    "openai":       "https://chat.openai.com",
    "claude":       "https://claude.ai",
    "gemini":       "https://gemini.google.com",
    "perplexity":   "https://www.perplexity.ai",
    # Shopping / services
    "amazon":       "https://www.amazon.in",
    "flipkart":     "https://www.flipkart.com",
    "netflix":      "https://www.netflix.com",
    "hotstar":      "https://www.hotstar.com",
    "disney":       "https://www.hotstar.com",
    "prime":        "https://www.primevideo.com",
    "prime video":  "https://www.primevideo.com",
    "spotify":      "https://open.spotify.com",
    "apple music":  "https://music.apple.com",
    "soundcloud":   "https://soundcloud.com",
    # Dev / tools
    "vercel":       "https://vercel.com",
    "netlify":      "https://netlify.com",
    "railway":      "https://railway.app",
    "jira":         "https://id.atlassian.com",
    "confluence":   "https://www.atlassian.com/software/confluence",
    "postman":      "https://www.postman.com",
    # Finance
    "paytm":        "https://paytm.com",
    "gpay":         "https://pay.google.com",
    "phonepe":      "https://www.phonepe.com",
}

# Classic/native desktop apps — used ONLY if NOT in URL_MAP
WIN_APP_MAP = {
    # System tools
    "notepad":              "notepad",
    "notepad++":            "notepad++.exe",
    "paint":                "mspaint.exe",
    "calculator":           "calc",
    "calc":                 "calc",
    "task manager":         "taskmgr.exe",
    "file explorer":        "explorer.exe",
    "explorer":             "explorer.exe",
    "cmd":                  "cmd.exe",
    "command prompt":       "cmd.exe",
    "powershell":           "powershell.exe",
    "terminal":             "wt.exe",
    "windows terminal":     "wt.exe",
    "control panel":        "control.exe",
    "settings":             "ms-settings:",
    "device manager":       "devmgmt.msc",
    "registry":             "regedit.exe",
    "disk management":      "diskmgmt.msc",
    "snipping tool":        "snippingtool.exe",
    "snip":                 "snippingtool.exe",
    "magnifier":            "magnify.exe",
    "on-screen keyboard":   "osk.exe",
    "character map":        "charmap.exe",
    # Browsers
    "chrome":               "chrome",
    "google chrome":        "chrome",
    "firefox":              "firefox",
    "mozilla firefox":      "firefox",
    "edge":                 "msedge",
    "microsoft edge":       "msedge",
    "brave":                "brave",
    "opera":                "opera",
    # Microsoft Office
    "word":                 "WINWORD.EXE",
    "microsoft word":       "WINWORD.EXE",
    "excel":                "EXCEL.EXE",
    "microsoft excel":      "EXCEL.EXE",
    "powerpoint":           "POWERPNT.EXE",
    "microsoft powerpoint": "POWERPNT.EXE",
    "outlook":              "OUTLOOK.EXE",
    "microsoft outlook":    "OUTLOOK.EXE",
    "onenote":              "ONENOTE.EXE",
    "access":               "MSACCESS.EXE",
    "publisher":            "MSPUB.EXE",
    "visio":                "VISIO.EXE",
    # Development
    "vs code":              "code",
    "vscode":               "code",
    "visual studio code":   "code",
    "visual studio":        "devenv.exe",
    "android studio":       "studio64.exe",
    "pycharm":              "pycharm64.exe",
    "intellij":             "idea64.exe",
    "webstorm":             "webstorm64.exe",
    "sublime":              "sublime_text.exe",
    "sublime text":         "sublime_text.exe",
    "atom":                 "atom.exe",
    "vim":                  "vim.exe",
    "git bash":             "sh.exe",
    "github desktop":       "GitHubDesktop.exe",
    "sourcetree":           "SourceTree.exe",
    "mongodb compass":      "MongoDBCompass.exe",
    "mysql workbench":      "MySQLWorkbench.exe",
    "dbeaver":              "dbeaver.exe",
    "insomnia":             "Insomnia.exe",
    "docker":               "Docker Desktop.exe",
    "wamp":                 "wampmanager.exe",
    "xampp":                "xampp-control.exe",
    # Media & entertainment
    "vlc":                  r"C:\Program Files\VideoLAN\VLC\vlc.exe",
    "vlc media player":     r"C:\Program Files\VideoLAN\VLC\vlc.exe",
    "spotify app":          "Spotify.exe",
    "itunes":               "iTunes.exe",
    "windows media player": "wmplayer.exe",
    "groovie":              "music.ui.exe",
    "movies":               "Video.UI.exe",
    "steam":                "steam",
    "epic games":           "com.epicgames.launcher://",
    "whatsapp":             r"explorer shell:appsFolder\5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App",
    "epic":                 "EpicGamesLauncher.exe",
    "xbox":                 "GamingServices.exe",
    "obs":                  "obs64.exe",
    "obs studio":           "obs64.exe",
    "audacity":             "audacity.exe",
    "handbrake":            "HandBrake.exe",
    "winamp":               "winamp.exe",
    # Adobe
    "photoshop":            "Photoshop.exe",
    "adobe photoshop":      "Photoshop.exe",
    "illustrator":          "Illustrator.exe",
    "adobe illustrator":    "Illustrator.exe",
    "premiere":             "Adobe Premiere Pro.exe",
    "premiere pro":         "Adobe Premiere Pro.exe",
    "after effects":        "AfterFX.exe",
    "adobe after effects":  "AfterFX.exe",
    "lightroom":            "lightroom.exe",
    "acrobat":              "Acrobat.exe",
    "adobe acrobat":        "Acrobat.exe",
    # Communication (native clients)
    "discord app":          "Discord.exe",
    "telegram app":         "Telegram.exe",
    "whatsapp app":         "WhatsApp.exe",
    "skype app":            "Skype.exe",
    "zoom app":             "Zoom.exe",
    "capcut":               "CapCut.exe",
    "cap cut":              "CapCut.exe",
    # Other popular
    "winrar":               "WinRAR.exe",
    "7zip":                 "7zFM.exe",
    "7-zip":                "7zFM.exe",
    "ccleaner":             "CCleaner64.exe",
    "malwarebytes":         "mbam.exe",
    "avast":                "AvastUI.exe",
    "anydesk":              "AnyDesk.exe",
    "teamviewer":           "TeamViewer.exe",
    "nordvpn":              "NordVPN.exe",
    "winscp":               "WinSCP.exe",
    "putty":                "putty.exe",
    "filezilla":            "filezilla.exe",
    "qbittorrent":          "qbittorrent.exe",
    "uTorrent":             "uTorrent.exe",
    "blender":              "blender.exe",
    "unity":                "Unity.exe",
    "unreal":               "UE4Editor.exe",
    "minecraft":            "MinecraftLauncher.exe",
    "valorant":             "VALORANT.exe",
    "lol":                  "LeagueClient.exe",
    "league of legends":    "LeagueClient.exe",
    "roblox":               "RobloxPlayerLauncher.exe",
    "fortnite":             "FortniteClient-Win64-Shipping.exe",
}

# ─── REMINDER SYSTEM ─────────────────────────────────────────────────────
_reminders: list[dict] = []   # {"fire_at": float, "task": str}
_reminders_lock = threading.Lock()

def _add_reminder(seconds: float, task: str):
    fire_at = time.time() + seconds
    with _reminders_lock:
        _reminders.append({"fire_at": fire_at, "task": task})
    log.info(f"[REMINDER] Set: '{task}' in {seconds:.0f}s")

def _reminder_loop():
    """Background thread — fires TTS when a reminder is due."""
    while True:
        try:
            time.sleep(5)
            now = time.time()
            with _reminders_lock:
                due = [r for r in _reminders if r["fire_at"] <= now]
                for r in due:
                    _reminders.remove(r)
            for r in due:
                msg = f"Reminder sir — {r['task']}"
                log.info(f"[REMINDER] Firing: {msg}")
                tts_queue.put(msg)
                tts_queue.put({"type": "end_reply"})
        except Exception as e:
            log.error(f"[ReminderLoop] Error: {e}")

threading.Thread(target=_reminder_loop, daemon=True, name="ReminderLoop").start()

# ─── TOOL DEFINITIONS ────────────────────────────────────────────────────
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "open_application",
            "description": (
                "Opens a named app or service. ALWAYS prefer this over open_website when the user "
                "says 'open YouTube', 'open Instagram', 'open Netflix', 'open WhatsApp', 'open Spotify', "
                "or any other named service/app — even if it is also a website. "
                "Also use for desktop apps like CapCut, VS Code, Chrome, Discord, Telegram, "
                "Notepad, Calculator, Steam, Zoom, etc. The system will try the installed app first "
                "and fall back to the browser automatically."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {"type": "string", "description": "App name as spoken, e.g. youtube, instagram, capcut, vs code"}
                },
                "required": ["app_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_website",
            "description": (
                "Opens a URL directly in the browser. Use this ONLY when the user explicitly asks "
                "to open something in the browser (e.g. 'open google.com in browser'), or for obscure "
                "URLs that have no dedicated app. Do NOT use this for YouTube, Instagram, Netflix, "
                "WhatsApp, Spotify — use open_application for those."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url":  {"type": "string", "description": "Full URL, e.g. https://www.youtube.com"},
                    "name": {"type": "string", "description": "Human-readable site name, e.g. YouTube"}
                },
                "required": ["url", "name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "close_browser_tabs",
            "description": "Closes one or more browser tabs using Ctrl+W. Use when user asks to close tab(s) in Chrome, Firefox, or any browser.",
            "parameters": {
                "type": "object",
                "properties": {
                    "count": {"type": "integer", "description": "Number of tabs to close. Minimum 1."}
                },
                "required": ["count"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_desktop_info",
            "description": "Counts or lists files and folders on the desktop. Use when user asks how many items, files, or folders are on the desktop.",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_type": {
                        "type": "string",
                        "enum": ["all", "files", "folders"],
                        "description": "What to query: all, files only, or folders only"
                    }
                },
                "required": ["item_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "system_control",
            "description": "Adjust system settings (volume up, down, mute), lock the screen, shutdown, or restart.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string", 
                        "enum": ["volume_up", "volume_down", "mute", "lock", "shutdown", "restart"]
                    }
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "screen_capture",
            "description": "Takes a screenshot of the current screen and saves it.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "file_management",
            "description": "Performs basic file operations in Desktop, Downloads, and Documents: search, delete, read, or edit text files under 2MB.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["search", "delete", "read", "edit"]},
                    "filename": {"type": "string", "description": "Name or partial name of the file"},
                    "content": {"type": "string", "description": "New content to save when action is edit."},
                    "confirm": {"type": "boolean", "description": "Set to true ONLY if you explicitly asked the user for permission to delete this file."}
                },
                "required": ["action", "filename"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "play_media",
            "description": "Plays a specific song, artist, or video automatically on YouTube. It natively handles any language specified (e.g. Telugu, Malayalam, Hindi, English).",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The song title and artist to play, including any language hints given by the user."}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_notepad",
            "description": "Writes text or dictation to a Notepad file and autonomously saves it to the Windows Desktop.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "The filename without extension to save as. Use simple names like 'note' or 'todo'."},
                    "content": {"type": "string", "description": "The continuous text content to write into the file."}
                },
                "required": ["filename", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "document_summary",
            "description": "Reads a specific PDF or text file from the Documents folder to answer questions or summarize it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Name or partial name of the document to read"}
                },
                "required": ["filename"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_whatsapp",
            "description": (
                "Sends a WhatsApp message to a contact. "
                "STRICT RULE: You MUST have BOTH a specific contact_name AND the exact message text before calling this tool. "
                "If the user says only 'send a whatsapp message' with no name, ask: 'Who should I send it to, sir?' "
                "If the user gives a name but no message, ask: 'What should I say to them, sir?' "
                "NEVER call this tool with empty, assumed, or placeholder values. "
                "Only call this tool when the user has explicitly stated BOTH the contact name AND the full message text."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "contact_name": {"type": "string", "description": "Name of the contact as saved in phone"},
                    "message":      {"type": "string", "description": "Message text to send"}
                },
                "required": ["contact_name", "message"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "set_reminder",
            "description": (
                "Sets a timed reminder. Use when user says 'remind me in X minutes/hours' or "
                "'remind me to do Y in Z minutes'. V.I.R.U.S. will speak the reminder at the right time."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "task":    {"type": "string",  "description": "What to remind the user about"},
                    "seconds": {"type": "number",  "description": "How many seconds from now to fire the reminder"}
                },
                "required": ["task", "seconds"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "device_control",
            "description": (
                "Controls native Windows hardware and system settings. Use this to increase/decrease brightness, "
                "toggle Wi-Fi or Bluetooth, and manage notifications."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "setting": {"type": "string", "enum": ["brightness", "wifi", "bluetooth", "notifications"], "description": "The system target to manipulate."},
                    "action":  {"type": "string", "enum": ["increase", "decrease", "on", "off", "clear", "count", "read"], "description": "For notifications, 'read' reads them, 'clear' deletes them."},
                    "value":   {"type": "number", "description": "Optional level for brightness (e.g., 50 for 50%)."}
                },
                "required": ["setting", "action"]
            }
        }
    }
,
    {
        "type": "function",
        "function": {
            "name": "search_and_save",
            "description": (
                "Searches the web for real-world data (like movies, restaurants, weather, live info) "
                "using DuckDuckGo. If the user simultaneously asks to save it to the desktop or write to notepad, "
                "set save_to_notepad to true. The system autonomously fetches the results, saves it, and opens Google/Notepad."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The exact search query."},
                    "save_to_notepad": {"type": "boolean", "description": "True only if asked to save or write to notepad."}
                },
                "required": ["query", "save_to_notepad"]
            }
        }
    },
]

# ─── TOOL EXECUTOR ───────────────────────────────────────────────────────
def _execute_tool(name: str, args: dict) -> str:
    """Run a tool call and return a plain-text result for the LLM to narrate."""
    try:
        if name == "search_and_save":
            query = args.get("query", "").strip()
            save_it = args.get("save_to_notepad", False)
            if not query: return "Search failed: no query provided."
            try:
                import urllib.request
                import json
                
                # Use DDG HTML endpoint for scraping without API keys
                req = urllib.request.Request(
                    f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}",
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
                )
                html = urllib.request.urlopen(req, timeout=8).read().decode('utf-8', errors='ignore')
                
                # Extract results using regex (DDG HTML results have class 'result__snippet' and 'result__title')
                import re
                titles = re.findall(r'<a class="result__url" href="[^"]*">([^<]+)</a>', html)
                snippets = re.findall(r'<a class="result__snippet[^"]*"[^>]*>(.*?)</a>', html)
                
                def drop_tags(s):
                    return re.sub(r'<[^>]+>', '', s).strip()
                
                titles = [drop_tags(t) for t in titles]
                snippets = [drop_tags(s) for s in snippets]
                
                results_text = f"Top results for '{query}':\n\n"
                spoken_summary = []
                for i in range(min(4, len(titles))):
                    t = titles[i]
                    s = snippets[i] if i < len(snippets) else ""
                    results_text += f"{i+1}. {t}\n   {s}\n\n"
                    spoken_summary.append(t)
                    
                if not spoken_summary:
                    return f"I searched the web for {query} but could not extract the snippets. It seems they blocked the request."

                if save_it:
                    # check OneDrive/Desktop first
                    desktop_path = os.path.join(os.path.expanduser('~'), 'OneDrive', 'Desktop')
                    if not os.path.exists(desktop_path):
                        desktop_path = os.path.join(os.path.expanduser('~'), 'Desktop')
                    
                    safe_query = re.sub(r'[^a-zA-Z0-9]+', '_', query).strip('_')[:20]
                    file_path = os.path.join(desktop_path, f"{safe_query}_results.txt")
                    
                    with open(file_path, "w", encoding="utf-8") as rf:
                        rf.write(results_text)
                    
                    subprocess.Popen(['notepad.exe', file_path])
                    return f"I searched the web for {query} and saved the full list to your desktop, sir."
                else:
                    webbrowser.open(f"https://www.google.com/search?q={urllib.parse.quote(query)}")
                    talk_str = ", ".join(spoken_summary[:3])
                    return f"I've opened the Google search results for {query}, sir. The top finds are: {talk_str}."
            except Exception as e:
                log.warning(f"Search failed: {e}")
                return f"I encountered an error while searching for {query}. The connection might be blocked."

        elif name == "device_control":
            setting = args.get("setting")
            action = args.get("action")
            value = args.get("value")

            if setting == "brightness":
                amount = int(value) if value else 50
                try:
                    subprocess.Popen(f'powershell -Command "(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1, {amount})"', shell=True)
                    return f"Screen brightness adjusted to {amount} percent."
                except Exception as e:
                    return f"Failed to adjust brightness: {e}"

            elif setting == "wifi":
                try:
                    if action == "off":
                        subprocess.Popen('netsh wlan disconnect', shell=True)
                        return "Wireless network disconnected."
                    elif action == "on":
                        # Turn on wifi adapter usually requires admin, but we can open settings
                        subprocess.Popen("start ms-settings:network-wifi", shell=True)
                        return "I opened the Wi-Fi settings so you can toggle it, sir."
                except Exception as e:
                    return f"Wi-Fi control error: {e}"

            elif setting == "bluetooth":
                subprocess.Popen("start ms-settings:bluetooth", shell=True)
                return "I've popped open the Bluetooth settings panel for you, sir."

            elif setting == "notifications":
                import pyautogui
                if action == "clear":
                    try:
                        # Open Action Center, wait, then click Clear All via keyboard
                        pyautogui.hotkey("win", "n")  # Win+N opens notification center
                        time.sleep(1.2)
                        # Tab to "Clear all" button and press it
                        pyautogui.hotkey("win", "n")  # toggle close
                        time.sleep(0.3)
                        # Use PowerShell to clear notifications silently
                        ps_cmd = (
                            "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, "
                            "ContentType = WindowsRuntime] | Out-Null; "
                            "[Windows.UI.Notifications.ToastNotificationManager]::History.Clear()"
                        )
                        subprocess.Popen(
                            ['powershell', '-WindowStyle', 'Hidden', '-Command', ps_cmd],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                        )
                        return "All notifications cleared, sir."
                    except Exception as e:
                        return f"Could not clear notifications: {e}"
                elif action in ["count", "read"]:
                    try:
                        # Read notifications via PowerShell + Windows Runtime
                        ps_cmd = (
                            "Add-Type -AssemblyName System.Runtime.WindowsRuntime; "
                            "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, "
                            "ContentType = WindowsRuntime] | Out-Null; "
                            "$history = [Windows.UI.Notifications.ToastNotificationManager]::History; "
                            "$nots = $history.GetHistory(); "
                            "$nots | ForEach-Object { $_.Content.GetXml() } | Select-Object -First 5"
                        )
                        result = subprocess.check_output(
                            ['powershell', '-WindowStyle', 'Hidden', '-Command', ps_cmd],
                            timeout=8, text=True, stderr=subprocess.DEVNULL
                        ).strip()
                        if not result:
                            return "You have no pending notifications, sir."
                        # Extract text from XML toast content
                        texts = re.findall(r'<text[^>]*>([^<]+)</text>', result)
                        texts = [t.strip() for t in texts if t.strip()][:10]
                        if not texts:
                            return "You have some notifications but I could not read their content, sir."
                        summary = ". ".join(texts[:5])
                        return f"You have {len(texts)} notification items, sir. Here they are: {summary}"
                    except Exception as e:
                        pyautogui.hotkey("win", "n")
                        return "I've opened your notification panel, sir. I couldn't read them automatically."
            return "System setting adjusted, sir."

        elif name == "open_website":
            url  = args.get("url", "").strip()
            site = args.get("name", "the website")
            # Check local map first for canonical URLs
            url  = URL_MAP.get(site.lower().strip(), url)
            if not url.startswith("http"):
                url = "https://" + url
            webbrowser.open(url)
            return f"Opened {site} in the browser."

        elif name == "open_application":
            raw = args.get("app_name", "").strip()
            key = raw.lower()

            # ── Step 1: Check Desktop shortcuts (.lnk) first ──────────────
            desktop_dirs = [
                pathlib.Path.home() / "Desktop",
                pathlib.Path.home() / "OneDrive" / "Desktop",
            ]
            shortcut_found = None
            for desk in desktop_dirs:
                if not desk.exists():
                    continue
                for lnk in desk.glob("*.lnk"):
                    # Match if app name appears in the shortcut filename (case-insensitive)
                    if key in lnk.stem.lower() or lnk.stem.lower() in key:
                        shortcut_found = lnk
                        break
                if shortcut_found:
                    break

            if shortcut_found:
                try:
                    os.startfile(str(shortcut_found))
                    return f"Opened {shortcut_found.stem} via desktop shortcut."
                except Exception as e:
                    log.warning(f"Shortcut launch failed ({shortcut_found}): {e}")
                    # Fall through to other methods

            # ── Step 2: WIN_APP_MAP (installed executables) ───────────────
            cmd = WIN_APP_MAP.get(key)
            if cmd:
                try:
                    if cmd.endswith(":"):  # URI protocol handler (ms-settings: etc.)
                        subprocess.Popen(f'start "" "{cmd}"', shell=True)
                    else:
                        subprocess.Popen(cmd, shell=True)
                    return f"Opened {raw}."
                except Exception as e:
                    log.warning(f"WIN_APP_MAP launch failed ({cmd}): {e}")

            # ── Step 3: Try raw name as executable ────────────────────────
            try:
                subprocess.Popen(raw, shell=True)
                return f"Opened {raw}."
            except Exception:
                pass

            # ── Step 4: Browser fallback for known web services ───────────
            fallback_url = URL_MAP.get(key)
            if fallback_url:
                webbrowser.open(fallback_url)
                return f"App not found locally, opened {raw} in the browser instead."

            return f"Could not find or open '{raw}'. Please check the app is installed."

        elif name == "close_browser_tabs":
            count = max(1, min(int(args.get("count", 1)), 20))
            try:
                import pyautogui
                for _ in range(count):
                    pyautogui.hotkey("ctrl", "w")
                    time.sleep(0.35)
                return f"Closed {count} tab{'s' if count != 1 else ''}."
            except ImportError:
                return "pyautogui not installed — run: pip install pyautogui"

        elif name == "get_desktop_info":
            item_type = args.get("item_type", "all")
            candidates = [
                pathlib.Path.home() / "Desktop",
                pathlib.Path.home() / "OneDrive" / "Desktop",
            ]
            desktop = next((p for p in candidates if p.exists()), None)
            if desktop is None:
                return "Could not locate the Desktop folder."
            items   = list(desktop.iterdir())
            folders = [i for i in items if i.is_dir()]
            files   = [i for i in items if i.is_file()]
            if item_type == "folders":
                names = ", ".join(f.name for f in folders[:15])
                return f"There are {len(folders)} folders on the desktop: {names}."
            elif item_type == "files":
                names = ", ".join(f.name for f in files[:15])
                return f"There are {len(files)} files on the desktop: {names}."
            else:
                return (
                    f"Desktop has {len(folders)} folder{'s' if len(folders) != 1 else ''} "
                    f"and {len(files)} file{'s' if len(files) != 1 else ''}. "
                    f"Total: {len(items)} items."
                )

        elif name == "system_control":
            action = args.get("action", "")
            if action == "volume_up":
                for _ in range(5): ctypes.windll.user32.keybd_event(0xAF, 0, 0, 0)
                return "Increased volume."
            elif action == "volume_down":
                for _ in range(5): ctypes.windll.user32.keybd_event(0xAE, 0, 0, 0)
                return "Decreased volume."
            elif action == "mute":
                ctypes.windll.user32.keybd_event(0xAD, 0, 0, 0)
                return "Toggled system audio mute."
            elif action == "lock":
                ctypes.windll.user32.LockWorkStation()
                return "Locked the screen."
            elif action == "shutdown":
                os.system("shutdown /s /t 5")
                return "System will shut down in 5 seconds."
            elif action == "restart":
                os.system("shutdown /r /t 5")
                return "System will restart in 5 seconds."
            return f"Unknown system control action: {action}"

        elif name == "screen_capture":
            try:
                from PIL import ImageGrab
                os.makedirs("virus_captures", exist_ok=True)
                path = f"virus_captures/screenshot_{int(time.time())}.png"
                img = ImageGrab.grab()
                img.save(path)
                return f"Screenshot saved to {path}."
            except Exception as e:
                return f"Failed to take screenshot: {e}"

        elif name == "file_management":
            action = args.get("action", "")
            filename = args.get("filename", "")
            content = args.get("content", "")
            
            search_dirs = [
                pathlib.Path.home() / "Desktop",
                pathlib.Path.home() / "Downloads",
                pathlib.Path.home() / "Documents",
                pathlib.Path.home() / "OneDrive" / "Desktop",
            ]
            matches = []
            for d in search_dirs:
                if d.exists():
                    matches.extend(list(d.rglob(f"*{filename}*")))
            
            if not matches: return f"No files found matching '{filename}' in Desktop, Documents, or Downloads."
                
            if action == "search":
                names = [m.name for m in matches[:5]]
                return f"Found {len(matches)} files. Top results: {', '.join(names)}"
            elif action == "delete":
                target = matches[0]
                if target.is_file():
                    if not args.get("confirm"):
                        return f"WARNING: Are you absolutely sure you want to delete {target.name}? Ask the user to confirm via voice: 'Are you sure you want to delete this?'"
                    target.unlink()
                    return f"Deleted {target.name}."
                return "Target is a folder, not deleting for safety."
            elif action == "read":
                target = matches[0]
                try:
                    with open(target, 'r', encoding='utf-8', errors='ignore') as f:
                        read_content = f.read(2000)
                    return f"Contents of {target.name}: {read_content}..."
                except Exception as e:
                    return f"Cannot read file: {e}"
            elif action == "edit":
                target = matches[0]
                if target.suffix.lower() != '.txt':
                    return "Security restriction: Only .txt files can be edited."
                if target.stat().st_size > 2 * 1024 * 1024:
                    return "Security restriction: File is over 2MB. Too large to edit safely."
                try:
                    target.write_text(content, encoding='utf-8')
                    return f"Successfully edited {target.name}. New content applied."
                except Exception as e:
                    return f"Failed to edit file: {e}"

        elif name == "play_media":
            query = args.get("query", "")
            try:
                import urllib.parse
                url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
                webbrowser.open(url)
                return f"Successfully routed {query} to YouTube playback."
            except Exception as e:
                return f"Media route failed: {e}"

        elif name == "write_notepad":
            filename = args.get("filename", "note")
            content = args.get("content", "")
            
            candidates = [
                pathlib.Path.home() / "Desktop",
                pathlib.Path.home() / "OneDrive" / "Desktop",
            ]
            desktop_dir = next((p for p in candidates if p.exists()), pathlib.Path.home())
            filepath = desktop_dir / f"{filename}.txt"
            
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
                subprocess.Popen(['notepad.exe', str(filepath)])
                return f"Successfully typed out content and saved it to {filename}.txt on the Desktop. I have opened it in Notepad for you."
            except Exception as e:
                return f"Failed to write note: {e}"

        elif name == "document_summary":
            filename = args.get("filename", "")
            search_dirs = [
                pathlib.Path.home() / "Desktop",
                pathlib.Path.home() / "Downloads",
                pathlib.Path.home() / "Documents",
                pathlib.Path.home() / "OneDrive" / "Desktop",
            ]
            matches = []
            for d in search_dirs:
                if d.exists():
                    matches.extend(list(d.rglob(f"*{filename}*")))
            if not matches: return f"Could not find a file matching {filename}."
            
            target = matches[0]
            if target.suffix.lower() == '.pdf':
                try:
                    import PyPDF2
                    text = ""
                    with open(target, 'rb') as f:
                        reader = PyPDF2.PdfReader(f)
                        for page in reader.pages[:10]: # Read up to 10 pages (~5000 tokens)
                            text += page.extract_text() + "\n"
                    return f"Contents of {target.name}:\n{text[:8000]}"
                except Exception as e:
                    return f"Failed to parse PDF: {e}"
            elif target.suffix.lower() == '.docx':
                try:
                    import docx
                    doc = docx.Document(target)
                    text = "\n".join([p.text for p in doc.paragraphs[:50]])
                    return f"Contents of {target.name}:\n{text[:8000]}"
                except ImportError:
                    return "python-docx not installed. Cannot read docx."
            elif target.suffix.lower() in ['.txt', '.md', '.csv', '.json']:
                try:
                    with open(target, 'r', encoding='utf-8', errors='ignore') as f:
                        return f"Contents of {target.name}:\n{f.read(8000)}"
                except: pass
            return "Document format not supported for inner transcription."

        elif name == "send_whatsapp":
            contact = args.get("contact_name", "").strip()
            message = args.get("message", "").strip()
            if not contact or not message:
                return "I need both a contact name and a message to send on WhatsApp, sir."

            try:
                import pyautogui
                import pyperclip

                # Open WhatsApp Desktop
                subprocess.Popen(r"explorer shell:appsFolder\5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App", shell=True)
                time.sleep(6)  # wait for WhatsApp to open and focus

                # Use Ctrl+N to open new chat / search
                pyautogui.hotkey("ctrl", "n")
                time.sleep(1.0)

                # Type contact name via clipboard (handles spaces, unicode, Indian names)
                pyperclip.copy(contact)
                pyautogui.hotkey("ctrl", "v")
                time.sleep(2.0)  # wait for search results

                # Press down arrow to select first result, then Enter to open chat
                pyautogui.press("down")
                time.sleep(0.5)
                pyautogui.press("enter")
                time.sleep(1.0)

                # Type message via clipboard (handles any characters)
                pyperclip.copy(message)
                pyautogui.hotkey("ctrl", "v")
                time.sleep(0.5)
                pyautogui.press("enter")

                return f"Message sent to {contact} on WhatsApp, sir."
            except ImportError:
                return "pyperclip not installed — run: pip install pyperclip"
            except Exception as e:
                return f"Could not automate WhatsApp Desktop: {e}"

        elif name == "set_reminder":
            task    = args.get("task", "something").strip()
            seconds = float(args.get("seconds", 60))
            _add_reminder(seconds, task)
            mins = int(seconds // 60)
            secs = int(seconds % 60)
            if mins > 0:
                time_str = f"{mins} minute{'s' if mins != 1 else ''}"
                if secs > 0: time_str += f" and {secs} second{'s' if secs != 1 else ''}"
            else:
                time_str = f"{secs} second{'s' if secs != 1 else ''}"
            return f"Reminder set, sir. I'll remind you to {task} in {time_str}."

        return f"Unknown tool: {name}"
    except Exception as e:
        return f"Tool error ({name}): {e}"

# ─── WHISPER LOCAL ───────────────────────────────────────────────────────
_whisper_model = None
def get_whisper():
    global _whisper_model
    if _whisper_model is None:
        print(f"[VIRUS] Loading local fallback Whisper '{WHISPER_MODEL}'...")
        from faster_whisper import WhisperModel
        _whisper_model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
        print("[VIRUS] Local Whisper ready.")
    return _whisper_model

# ─── BROADCAST ───────────────────────────────────────────────────────────
def emit(msg: dict):
    if _loop is None: return
    data = json.dumps(msg)
    async def _send():
        dead = []
        for ws in clients:
            try: await ws.send_text(data)
            except Exception: dead.append(ws)
        for ws in dead:
            if ws in clients: clients.remove(ws)
    asyncio.run_coroutine_threadsafe(_send(), _loop)

# ─── BARGE-IN DETECTION ─────────────────────────────────────────────────
BARGE_IN_VAD_PROB  = 0.30   # lowered so user voice registers even during TTS playback
BARGE_IN_SILENCE   = 0.30   # seconds of silence that mark end of utterance
BARGE_IN_MIN_DUR   = 0.35   # minimum speech duration to bother transcribing (seconds)
BARGE_IN_MAX_DUR   = 2.50   # collect at most this many seconds before forcing transcribe
BARGE_IN_MAX_WORDS = 8      # anti-feedback: TTS says long sentences; user says "virus" (1 word)


# ── Barge-in constants ────────────────────────────────────────────────────────
BARGE_IN_VAD_PROB = 0.30   # VAD threshold (lowered so user voice registers over TTS playback)
BARGE_IN_FRAMES   = 5      # consecutive frames needed to confirm user speech
                           # 6 frames x 32ms = ~192ms  →  lightning fast response


def _trigger_barge_in():
    """Stop TTS mid-sentence and return to listening state."""
    global is_playing_audio, is_llm_generating
    if not (is_playing_audio or is_llm_generating):
        return
    log.info("[VIRUS] Barge-in triggered -- stopping response.")
    barge_in_event.set()
    is_llm_generating = False
    drained = 0
    while not tts_queue.empty():
        try:
            tts_queue.get_nowait()
            drained += 1
        except Exception:
            break
    log.info(f"[VIRUS] Drained {drained} TTS items.")
    tts_queue.put({"type": "end_reply"})
    emit({"type": "status", "value": "listening"})


STOP_WORDS_PHONETIC = [
    "stop", "enough", "quiet", "pause", "cancel",
    "silence", "shut", "wait", "hold"
]

def _barge_in_monitor():
    consecutive = 0

    while True:
        # ── Idle: drain queue ─────────────────────────────────────────
        if not (is_playing_audio or is_llm_generating):
            consecutive = 0
            try:
                while True:
                    barge_in_q.get_nowait()
            except queue.Empty:
                pass
            time.sleep(0.04)
            continue

        # ── Get chunk ─────────────────────────────────────────────────
        try:
            chunk = barge_in_q.get(timeout=0.04)
        except queue.Empty:
            consecutive = max(0, consecutive - 2)
            continue

        if vad_model is None:
            continue

        # ── VAD check ─────────────────────────────────────────────────
        try:
            tensor = torch.from_numpy(chunk).float()
            with vad_lock:
                with torch.no_grad():
                    prob = vad_model(tensor, SAMPLE_RATE).item()

            if prob >= BARGE_IN_VAD_PROB:
                consecutive += 1
                log.info(f"[BARGE-IN] voice frame {consecutive}/{BARGE_IN_FRAMES} VAD={prob:.2f}")

                if consecutive >= BARGE_IN_FRAMES:
                    log.info("[BARGE-IN] threshold reached — interrupting")
                    consecutive = 0
                    threading.Thread(
                        target=_trigger_barge_in, daemon=True
                    ).start()
            else:
                consecutive = max(0, consecutive - 1)

        except Exception:
            log.error(f"[barge_in_monitor] error:\n{traceback.format_exc()}")


def _mic_read_thread():
    global level_value, is_speaking
    
    if pyaudio is None:
        log.info("[VIRUS] PyAudio unavailable. Local microphone disabled.")
        return

    try:
        p_audio = pyaudio.PyAudio()
        device_count = p_audio.get_device_count()
        if device_count == 0:
            log.info("[VIRUS] No local audio input devices found (running in cloud mode).")
            return
            
        device_idx_raw = os.getenv("INPUT_DEVICE")
        device_idx = int(device_idx_raw) if device_idx_raw is not None else None
        if device_idx is not None and (device_idx < 0 or device_idx >= device_count):
            device_idx = None

        mic_stream = p_audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=CAPTURE_RATE,
            input=True,
            input_device_index=device_idx,
            frames_per_buffer=CAPTURE_BLOCK_SIZE
        )
        print(f"[VIRUS] Mic open (PyAudio Blocking Thread) — {CAPTURE_RATE} Hz, {BLOCK_MS}ms blocks")
    except Exception as e:
        log.warning(f"[VIRUS] Could not open local microphone: {e}. Running in cloud mode.")
        return
    
    while True:
        try:
            in_data = mic_stream.read(CAPTURE_BLOCK_SIZE, exception_on_overflow=False)
        except Exception as e:
            log.warning(f"Audio read error: {e}")
            continue
            
        if not in_data:
            continue
            
        # Convert int16 bytes to float32 numpy array (-1.0 to +1.0)
        indata_int16 = np.frombuffer(in_data, dtype=np.int16)
        indata_float_48k = indata_int16.astype(np.float32) / 32768.0
        
        # Resample 48000Hz down to 16000Hz (3x decimation)
        # Moving average of 3 preserves signal without block boundary discontinuities
        indata_float = indata_float_48k.reshape(-1, 3).mean(axis=1)

        # Boost gain — compensates for weak laptop mic signal
        GAIN = 4.0
        indata_float = np.clip(indata_float * GAIN, -1.0, 1.0)
        
        real_chunk = indata_float.copy()
        
        if system_audio_playing:
            chunk = np.zeros_like(real_chunk)
            real_chunk = np.zeros_like(real_chunk)
        elif is_playing_audio or is_llm_generating:
            chunk = np.zeros_like(real_chunk)  # mute mic for whisper (prevent feedback)
        else:
            chunk = real_chunk

        rms = float(np.sqrt(np.mean(chunk ** 2)))

        # Drives the frontend blob only
        if is_speaking:
            above = max(0.0, rms - noise_floor)
            level_value = min(1.0, (above / max(noise_floor * 3.0, 0.001)) ** 0.6)
        else:
            level_value = max(0.0, level_value * 0.80)

        barge_in_q.put(real_chunk)  # real audio for barge-in monitor
        audio_q.put(chunk)           # zeroed or real audio for whisper thread

# ─── LEVEL PUSH THREAD ───────────────────────────────────────────────────
def _level_thread():
    interval = 1.0 / LEVEL_HZ
    while True:
        try:
            emit({"type": "level", "value": round(level_value, 4)})
        except Exception as e:
            log.warning(f"[level_thread] emit failed: {e}")
        time.sleep(interval)

# ─── SYS METRICS THREAD ──────────────────────────────────────────────────
def _cricket_thread():
    """Polls CricAPI (primary) and Cricbuzz (fallback) for live cricket scores."""
    import urllib.request
    import urllib.error
    import os
    import json
    import time
    import re

    CB_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-IN,en;q=0.9",
        "Referer": "https://www.cricbuzz.com/",
    }

    def _fetch(url: str, is_json=False):
        try:
            req = urllib.request.Request(url, headers=CB_HEADERS if not is_json else {})
            with urllib.request.urlopen(req, timeout=10) as r:
                res = r.read().decode("utf-8", errors="ignore")
                return json.loads(res) if is_json else res
        except Exception as e:
            log.warning(f"[cricket] Fetch error for {url}: {e}")
            return None

    def _clean_html(s: str) -> str:
        s = re.sub(r"<[^>]+>", " ", s)
        return re.sub(r"\s+", " ", s).strip()

    def _cricapi_fetch():
        key = os.getenv("CRICAPI_KEY", "").strip()
        if not key:
            return None
        url = f"https://api.cricapi.com/v1/currentMatches?apikey={key}&offset=0"
        data = _fetch(url, is_json=True)
        if not data or data.get("status") != "success":
            return None
            
        matches = data.get("data", [])
        for m in matches:
            name = m.get("name", "").lower()
            status = m.get("status", "")
            if "indian premier league" in name or " ipl " in name or "india" in name:
                score_str = []
                for s in m.get("score", []):
                    # For format like RCB: 187/4 (18.2 ov) | SRH: ...
                    inning_team = s.get("inning", "").split(" Inning")[0]
                    score_str.append(f"{inning_team}: {s.get('r')}/{s.get('w')} ({s.get('o')} ov)")
                score_text = " | ".join(score_str)
                if not score_text:
                    score_text = status
                else:
                    if status and len(status) < 40:
                        score_text += f" | {status}"
                        
                is_live = not m.get("matchEnded", True)
                
                return {
                    "active": True,
                    "match": m.get("name", "").split(",")[0],
                    "score": score_text,
                    "batsmen": "",
                    "bowler": "",
                    "status": "LIVE" if is_live else "RESULT",
                    "is_live": is_live
                }
        return None

    def _cricbuzz_fetch():
        html = _fetch("https://www.cricbuzz.com/cricket-match/live-scores")
        if not html: return None
        
        IPL_URL_KEYS  = ["indian-premier-league", "-ipl-"]
        INDIA_URL_KEYS = ["-ind-vs-", "-vs-ind-", "india-vs-", "-vs-india"]
        
        anchors = re.findall(r'href="(/live-cricket-scores/\d+/[^"]+)"[^>]*title="([^"]+)"', html)
        seen_ids = set()
        live_matches = []

        for path, title in anchors:
            mid_m = re.search(r"/(\d+)/", path)
            if not mid_m: continue
            mid = mid_m.group(1)
            if mid in seen_ids: continue
            seen_ids.add(mid)

            path_low, title_low = path.lower(), title.lower()
            is_ipl = any(k in path_low for k in IPL_URL_KEYS)
            is_india = any(k in path_low for k in INDIA_URL_KEYS)
            is_live = "live" in title_low or "- live" in title_low

            if is_ipl or is_india:
                live_matches.append({"path": path, "title": title, "live": is_live})

        live_matches.sort(key=lambda x: 0 if x["live"] else 1)
        if not live_matches: return None

        best = live_matches[0]
        display_title = re.sub(r",.*", "", best["title"]).strip()

        if best["live"]:
            match_html = _fetch(f"https://www.cricbuzz.com{best['path']}")
            if not match_html: match_html = ""
            
            scores = re.findall(r"\b(\d{1,3}/\d{1,2})\b", match_html)
            crr_m = re.search(r"CRR:\s*([\d.]+)", match_html)
            rrr_m = re.search(r"(?:REQ|RRR):\s*([\d.]+)", match_html, re.IGNORECASE)
            
            status_m = re.search(r'(?:opt to bowl|opt to bat|won by|Match Over|need \d+)[^<]{0,80}', match_html, re.IGNORECASE)
            
            score_str = scores[0] if scores else "–"
            crr_str = f" | CRR {crr_m.group(1)}" if crr_m else ""
            rrr_str = f" | RRR {rrr_m.group(1)}" if rrr_m else ""
            
            status_str = ""
            if status_m:
                clean_status = status_m.group(0).split('"')[0].strip()
                status_str = f" | {_clean_html(clean_status)}"
                
            score_text = f"{score_str}{crr_str}{rrr_str}{status_str}"
            
            cleaned = _clean_html(match_html)
            batsmen_str = ""
            bowler_str = ""
            
            bat_match = re.search(r'(?:Batter|Batsman) R B 4s 6s SR\s+(.+?)\s+Bowler', cleaned)
            if bat_match:
                players = re.findall(r'([A-Za-z\s\-]+?)\s*(\*?)\s+(\d+)\s+(\d+)\s+\d+\s+\d+\s+[\d.]+', bat_match.group(1).strip())
                if players:
                    batsmen_str = ", ".join([f"{n.strip()}{s} {r}({b})" for n,s,r,b in players])
                    
            bowl_match = re.search(r'Bowler O M R W ECO\s+(.+?)(?:Key Stats|Partnership|Last Wicket|Match Details|<)', cleaned)
            if bowl_match:
                bowler_first = re.search(r'([A-Za-z\s\-]+?)\s*(\*?)\s+([\d.]+)\s+\d+\s+(\d+)\s+(\d+)\s+[\d.]+', bowl_match.group(1).strip())
                if bowler_first:
                    n, _, o, r, w = bowler_first.groups()
                    bowler_str = f"{n.strip()} {w}/{r} ({o}v)"
            
            status_label = "LIVE"
        else:
            score_text = re.sub(r".*- ", "", best["title"]).strip()
            status_label = "UPCOMING" if "preview" in score_text.lower() else "RESULT"
            batsmen_str = ""
            bowler_str = ""

        return {
            "active": True,
            "match": display_title,
            "score": score_text,
            "batsmen": batsmen_str,
            "bowler": bowler_str,
            "status": status_label,
            "is_live": best["live"]
        }

    while True:
        try:
            # 1. Try CricAPI if key exists
            result = _cricapi_fetch()
            
            # 2. Fallback to Cricbuzz
            if not result:
                result = _cricbuzz_fetch()

            if result:
                emit({"type": "cricket_update", "value": {
                    "active": result["active"],
                    "match": result["match"],
                    "score": result["score"],
                    "batsmen": result.get("batsmen", ""),
                    "bowler": result.get("bowler", ""),
                    "status": result["status"]
                }})
                poll_interval = 30 if result.get("is_live", False) else 120
            else:
                emit({"type": "cricket_update", "value": {
                    "active": False,
                    "msg": "No IPL or India matches right now"
                }})
                poll_interval = 120
                
        except Exception as e:
            log.warning(f"[cricket] thread error: {e}")
            emit({"type": "cricket_update", "value": {
                "active": False,
                "msg": "Score unavailable"
            }})
            poll_interval = 120

        time.sleep(poll_interval)


def _sys_metrics_thread():
    while True:
        try:
            cpu = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory().percent
            
            # Simple ping proxy (measure socket connection to 8.8.8.8)
            ping_ms = 0
            try:
                t0 = time.time()
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.5)
                s.connect(("8.8.8.8", 53))
                s.close()
                ping_ms = int((time.time() - t0) * 1000)
            except Exception:
                ping_ms = 999
            
            emit({"type": "sys_metrics", "value": {"cpu": cpu, "ram": ram, "ping": ping_ms}})
        except Exception as e:
            log.warning(f"[sys_metrics_thread] failed: {e}")
        time.sleep(1.0)

# ─── NOISE CALIBRATION ───────────────────────────────────────────────────
def _calibrate():
    global noise_floor
    print(f"[VIRUS] Calibrating blob noise floor ({CALIB_SECONDS}s) — stay quiet...")
    samples = []
    deadline = time.time() + CALIB_SECONDS
    while time.time() < deadline:
        try:
            chunk = audio_q.get(timeout=0.5)
            samples.append(chunk)
        except Exception: break
    if samples:
        rms = float(np.sqrt(np.mean(np.concatenate(samples) ** 2)))
        noise_floor = max(0.003, rms * 1.05)
        print(f"[VIRUS] Noise floor={noise_floor:.5f}")
    else:
        print("[VIRUS] Calibration failed — using defaults.")

# ─── WHISPER / SILERO VAD THREAD ──────────────────────────────────────────
def _whisper_thread():
    global is_speaking
    model = get_whisper()
    _calibrate()

    speech_buf = []
    pre_roll = collections.deque(maxlen=PRE_ROLL_BLOCKS)
    silence_start = None
    speaking = False
    consecutive_voice = 0
    last_interim_time = 0.0

    while True:
        try:
            chunk = audio_q.get(timeout=0.5)
        except queue.Empty:
            continue

        try:
            pre_roll.append(chunk)

            # Neural VAD pass + Amplitude Fallback
            is_voice = False
            rms = float(np.sqrt(np.mean(chunk ** 2)))
            
            if vad_model is not None:
                try:
                    tensor_chunk = torch.from_numpy(chunk).float()
                    with vad_lock:
                        with torch.no_grad():
                            prob = vad_model(tensor_chunk, SAMPLE_RATE).item()
                    
                    current_vad_thresh = 0.95 if system_audio_playing else VAD_SPEECH_PROB
                    is_voice = prob > current_vad_thresh
                except Exception as vad_err:
                    log.warning(f"[VAD] error: {vad_err}")
                    vad_rms_mult = 8.0 if system_audio_playing else 1.5
                    is_voice = rms > noise_floor * vad_rms_mult
            else:
                vad_rms_mult = 8.0 if system_audio_playing else 1.5
                is_voice = rms > noise_floor * vad_rms_mult
            
            # Absolute hard-block to prevent false triggers cleanly
            if system_audio_playing:
                is_voice = False

            if is_voice:
                consecutive_voice += 1
            else:
                consecutive_voice = 0

            # Debounced trigger
            if consecutive_voice >= VAD_DEBOUNCE:
                if not speaking:
                    is_speaking = True
                    speaking = True
                    speech_buf.extend(list(pre_roll))  # prepend context
                    silence_start = None
                    last_interim_time = time.time()
                    emit({"type": "status", "value": "listening"})
                else:
                    speech_buf.append(chunk)
                    silence_start = None

                # Interims
                now = time.time()
                if now - last_interim_time >= INTERIM_INTERVAL:
                    last_interim_time = now
                    buf_copy = list(speech_buf)
                    threading.Thread(
                        target=lambda m=model, b=buf_copy: _thread_wrap(lambda: _interim_flush(m, b), "interim_flush"),
                        daemon=True
                    ).start()

            else:
                if speaking:
                    speech_buf.append(chunk)
                    if silence_start is None:
                        silence_start = time.time()
                    elif time.time() - silence_start >= SILENCE_FLUSH:
                        is_speaking = False
                        buf_copy = list(speech_buf)
                        threading.Thread(
                            target=lambda b=buf_copy: _thread_wrap(lambda: _final_flush(b), "final_flush"),
                            daemon=True
                        ).start()
                        speech_buf.clear()
                        speaking = False
                        silence_start = None

            if speaking and len(speech_buf) * BLOCK_SIZE / SAMPLE_RATE >= MAX_SPEECH:
                is_speaking = False
                buf_copy = list(speech_buf)
                threading.Thread(
                    target=lambda b=buf_copy: _thread_wrap(lambda: _final_flush(b), "final_flush_max"),
                    daemon=True
                ).start()
                speech_buf.clear()
                speaking = False
                silence_start = None

        except Exception:
            log.error(f"[_whisper_thread] inner loop crash:\n{traceback.format_exc()}")

# ─── FLUSHERS & FILTERS ──────────────────────────────────────────────────
HALLUCINATIONS = {
    "[BLANK_AUDIO]", "(silence)", "Thank you.", "Thank you",
    "Thanks for watching.", "Thanks.", "Bye.", ".", "!", "?", "",
    "and so on", "okay", "okay.", "so", "so.", "yeah", "yeah.", 
    "mm", "oh", "ah", "uh huh"
}

def is_hallucination(text, prob):
    if not text: return True
    if text in HALLUCINATIONS: return True
    if prob > 0.85: return True
    lower = text.lower()
    if "i'm going to be generous" in lower: return True
    if "subscribe" in lower and len(text) < 20: return True
    return False

def is_speech_spectrum(audio_data, sample_rate):
    """FFT band filtering: compute energy in human vocal cord range limits vs overall"""
    try:
        spectrum = np.abs(np.fft.rfft(audio_data))
        freqs = np.fft.rfftfreq(len(audio_data), 1.0 / sample_rate)
        band_mask = (freqs >= 200) & (freqs <= 3400)
        band_energy = np.sum(spectrum[band_mask] ** 2)
        total_energy = np.sum(spectrum ** 2)
        if total_energy == 0: return 0.0
        return band_energy / total_energy
    except Exception:
        return 1.0 # bypass on failure

def _interim_flush(model, buf: list[np.ndarray]):
    audio = np.concatenate(buf)
    duration = len(audio) / SAMPLE_RATE
    if duration < MIN_SPEECH: return

    # Check Spectral rejection early
    band_ratio = is_speech_spectrum(audio, SAMPLE_RATE)
    if band_ratio < MIN_SPEECH_BAND_RATIO: return
    
    # Enforce strict English language decoding
    segments, _ = model.transcribe(
        audio, beam_size=1, vad_filter=False, initial_prompt=INITIAL_PROMPT, language="en"
    )
    parts = []
    for s in segments:
        t = s.text.strip()
        if not is_hallucination(t, s.no_speech_prob): parts.append(t)
    
    text = " ".join(parts).strip()
    if text:
        emit({"type": "transcript", "value": text, "final": False})

def save_wav(audio_data: np.ndarray, sample_rate: int) -> str:
    path = f"debug_audio/seg_{int(time.time()*1000)}.wav"
    scaled = np.int16(audio_data * 32767)
    with wave.open(path, 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(scaled.tobytes())
    return path

def _final_flush(buf: list[np.ndarray]):
    audio = np.concatenate(buf)
    duration = len(audio) / SAMPLE_RATE
    if duration < MIN_SPEECH: return

    peak = float(np.max(np.abs(audio)))
    rms = float(np.sqrt(np.mean(audio ** 2)))
    
    # Layer 2: Reject Table thuds, hand claps etc. via FFT
    band_ratio = is_speech_spectrum(audio, SAMPLE_RATE)
    if band_ratio < MIN_SPEECH_BAND_RATIO:
        print(f"[seg] REJECTED non-voice spectrum: dur={duration:.2f}s peak={peak:.4f} band_ratio={band_ratio:.2f}")
        return
        
    wav_path = save_wav(audio, SAMPLE_RATE)
    warn_text = ""
    
    print(f"[seg] dur={duration:.2f}s peak={peak:.4f} band_ratio={band_ratio:.2f} {warn_text} saved={wav_path}")
    emit({"type": "status", "value": "processing"})
    
    text = ""
    
    # 1. Cloud Groq APIs -> Unlimited use limits within reason. Remove language parameter completely
    if groq_client:
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
                tf.write(open(wav_path, "rb").read())
                tf_path = tf.name
                
            with open(tf_path, "rb") as f:
                transcription = groq_client.audio.transcriptions.create(
                    model=GROQ_WHISPER_MODEL,
                    file=("audio.wav", f.read(), "audio/wav"),
                    prompt=INITIAL_PROMPT,
                    language="en",
                    temperature=0.0
                ) # Strictly enforced English Language parameter
            text = transcription.text.strip()
            print(f"[transcribed-cloud] '{text}'")
            os.unlink(tf_path)
        except Exception as e:
            print(f"[VIRUS-GROQ ERROR] {e}")
            
    # 2. Totally free 100% Unlimited Local Fallback -> Small multilingual model overrides limits totally.
    if not text:
        try:
            model = get_whisper()
            segments, _ = model.transcribe(audio, beam_size=5, vad_filter=False, initial_prompt=INITIAL_PROMPT, language="en")
            parts = []
            for s in segments:
                t = s.text.strip()
                if not is_hallucination(t, s.no_speech_prob): parts.append(t)
            text = " ".join(parts).strip()
            print(f"[transcribed-local] '{text}'")
        except Exception as e:
            print(f"[VIRUS-LOCAL ERROR] {e}")

    if text:
        emit({"type": "transcript", "value": text, "final": True})
        threading.Thread(
            target=lambda t=text: _llm_reply(t),
            daemon=True
        ).start()
    else:
        emit({"type": "status", "value": "idle"})

# ════════════════════════════════════════════════════════════════════════════
# LLM REPLY  — Dynamic App Engine + Intent Detection
# ════════════════════════════════════════════════════════════════════════════

import glob as _glob

# ── App cache: built once from Start Menu at first use ───────────────────────
_app_cache:       dict[str, str]  = {}   # lowercase_name -> launch_path
_app_cache_ready: bool            = False
_app_cache_lock:  threading.Lock  = threading.Lock()

# Track last opened browser tabs for "close them" command
_last_opened_browser: list[str]    = []
_session_last_active: float         = 0.0


def _build_app_cache():
    """Scan Windows Start Menu to index every installed app shortcut."""
    global _app_cache, _app_cache_ready
    with _app_cache_lock:
        if _app_cache_ready:
            return
        cache: dict[str, str] = {}
        sm_dirs = [
            os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
            os.path.expandvars(r"%PROGRAMDATA%\Microsoft\Windows\Start Menu\Programs"),
        ]
        vendor_prefixes = {
            "microsoft", "adobe", "google", "apple", "amazon", "meta", "epic",
            "valve", "nvidia", "intel", "razer", "logitech", "asus", "hp",
        }
        for sm_dir in sm_dirs:
            if not os.path.isdir(sm_dir):
                continue
            for lnk in _glob.glob(os.path.join(sm_dir, "**", "*.lnk"), recursive=True):
                raw  = os.path.splitext(os.path.basename(lnk))[0]
                name = raw.lower()
                cache[name] = lnk
                # Strip vendor prefix ("microsoft edge" -> "edge")
                parts = name.split()
                if parts and parts[0] in vendor_prefixes and len(parts) > 1:
                    cache[" ".join(parts[1:])] = lnk
                # Strip parenthetical suffixes ("firefox (64-bit)" -> "firefox")
                clean = re.sub(r"\s*\(.*?\)\s*$", "", name).strip()
                if clean and clean != name:
                    cache[clean] = lnk
                # Strip version numbers ("python 3.11" -> "python")
                nover = re.sub(r"\s+\d+[\.\d]*$", "", name).strip()
                if nover and nover != name:
                    cache[nover] = lnk

        _app_cache     = cache
        _app_cache_ready = True
        log.info(f"[APP-CACHE] Indexed {len(cache)} Start Menu entries")


def _find_app_path(name: str) -> str | None:
    """Fuzzy-find an app path from the Start Menu cache."""
    _build_app_cache()
    n = name.lower().strip()

    # 1. Exact match
    if n in _app_cache:
        return _app_cache[n]

    # 2. Query is substring of key (e.g. "chrome" in "google chrome")
    best, best_len = None, float("inf")
    for key, path in _app_cache.items():
        if n in key and len(key) < best_len:
            best, best_len = path, len(key)
    if best:
        return best

    # 3. Key is substring of query (e.g. "visual studio" in "visual studio 2022")
    best, best_len = None, 0
    for key, path in _app_cache.items():
        if key in n and len(key) > best_len and len(key) >= 4:
            best, best_len = path, len(key)
    if best:
        return best

    return None


def _normalize(s: str) -> str:
    """Lowercase, remove spaces/dots/hyphens for fuzzy shortcut matching."""
    return re.sub(r"[\s.\-_]+", "", s.lower())


def _find_desktop_shortcut(app_name: str) -> pathlib.Path | None:
    """Return the best matching .lnk on the Desktop, or None."""
    key = _normalize(app_name)
    desktop_dirs = [
        pathlib.Path.home() / "OneDrive" / "Desktop",
        pathlib.Path.home() / "Desktop",
    ]
    best: tuple[int, pathlib.Path | None] = (0, None)
    for desk in desktop_dirs:
        if not desk.exists():
            continue
        for lnk in desk.glob("*.lnk"):
            stem = _normalize(lnk.stem)
            # Score: exact > query-in-stem > stem-in-query
            if stem == key:
                return lnk                         # perfect match
            elif key in stem and len(key) > best[0]:
                best = (len(key), lnk)
            elif stem in key and len(stem) > best[0]:
                best = (len(stem), lnk)
    return best[1]


def _open_single(app_name: str) -> bool:
    """Open one app or website.
    Priority: Desktop shortcut > WIN_APP_MAP > Start Menu > URL_MAP > shell."""
    name = app_name.lower().strip()

    # 0. Desktop shortcut (.lnk) — highest priority so user shortcuts win
    shortcut = _find_desktop_shortcut(name)
    if shortcut:
        try:
            os.startfile(str(shortcut))
            log.info(f"[OPEN] Desktop shortcut: {shortcut.name}")
            return True
        except Exception as e:
            log.warning(f"[OPEN] shortcut failed {shortcut}: {e}")

    # 1. Known native desktop app → direct executable
    cmd = WIN_APP_MAP.get(name)
    if cmd and not cmd.endswith(":") and not cmd.endswith("\\"):
        try:
            subprocess.Popen(cmd, shell=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception as e:
            log.warning(f"[OPEN] WIN_APP_MAP exec failed {name!r}: {e}")

    # 2. Start Menu shortcut (covers 99% of installed apps)
    path = _find_app_path(name)
    if path:
        try:
            os.startfile(path)
            log.info(f"[OPEN] Start Menu: {path}")
            return True
        except Exception:
            try:
                subprocess.Popen(f'start "" "{path}"', shell=True)
                return True
            except Exception as e:
                log.warning(f"[OPEN] shortcut failed {path}: {e}")

    # 3. Known web service → browser tab
    url = URL_MAP.get(name)
    if url:
        webbrowser.open_new_tab(url)
        return True

    # 4. Try Windows shell "start" (works for UWP + registered names)
    try:
        subprocess.Popen(f'start "" "{name}"', shell=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        log.info(f"[OPEN] shell start: {name!r}")
        return True
    except Exception:
        pass

    return False


def _close_single(app_name: str) -> bool:
    """Kill a running app by name — scans tasklist for fuzzy match."""
    name = app_name.lower().strip()

    # Known process name overrides
    PROC_OVERRIDES = {
        "chrome":           "chrome.exe",
        "google chrome":    "chrome.exe",
        "firefox":          "firefox.exe",
        "edge":             "msedge.exe",
        "microsoft edge":   "msedge.exe",
        "explorer":         "explorer.exe",
        "file explorer":    "explorer.exe",
        "calculator":       "CalculatorApp.exe",
        "calc":             "CalculatorApp.exe",
        "notepad":          "notepad.exe",
        "word":             "WINWORD.EXE",
        "excel":            "EXCEL.EXE",
        "powerpoint":       "POWERPNT.EXE",
        "spotify":          "Spotify.exe",
        "discord":          "Discord.exe",
        "teams":            "Teams.exe",
        "zoom":             "Zoom.exe",
        "obs":              "obs64.exe",
        "vlc":              "vlc.exe",
        "steam":            "Steam.exe",
        "vs code":          "Code.exe",
        "vscode":           "Code.exe",
        "visual studio code": "Code.exe",
        "capcut":           "CapCut.exe",
    }

    proc = PROC_OVERRIDES.get(name)

    if not proc:
        # Dynamic scan: find best matching process from tasklist
        try:
            out = subprocess.check_output(
                ["tasklist", "/FO", "CSV", "/NH"], timeout=4, text=True
            )
            best_proc, best_score = None, 0
            for line in out.splitlines():
                cols = line.strip().strip('"').split('","')
                if not cols:
                    continue
                pname = cols[0].lower()
                pbare = pname.replace(".exe", "")
                # Score: exact > ends-with > contains
                if pbare == name:
                    best_proc, best_score = cols[0], 3; break
                elif pbare.endswith(name) and best_score < 2:
                    best_proc, best_score = cols[0], 2
                elif name in pbare and best_score < 1:
                    best_proc, best_score = cols[0], 1
            proc = best_proc
        except Exception as e:
            log.warning(f"[CLOSE] tasklist scan failed: {e}")

    if proc:
        try:
            subprocess.Popen(
                f'taskkill /F /IM "{proc}" /T', shell=True,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            log.info(f"[CLOSE] killed: {proc}")
            return True
        except Exception as e:
            log.warning(f"[CLOSE] taskkill failed {proc}: {e}")

    # For browser-based apps, close the active tab
    if name in URL_MAP:
        try:
            import pyautogui
            pyautogui.hotkey("ctrl", "w")
            return True
        except Exception:
            pass

    return False


def _format_names(lst: list) -> str:
    """['a','b','c'] -> 'A, B and C'"""
    titled = [a.title() for a in lst]
    if len(titled) == 1:  return titled[0]
    if len(titled) == 2:  return f"{titled[0]} and {titled[1]}"
    return ", ".join(titled[:-1]) + f" and {titled[-1]}"


def _parse_app_list(raw: str) -> list[str]:
    """Parse 'Instagram YouTube and Facebook' -> ['instagram', 'youtube', 'facebook'].
    Handles commas, 'and', '&', or plain whitespace between app names."""
    # Strip noise words
    raw = re.sub(
        r"\b(?:both|all|the|please|simultaneously|at\s+once|as\s+well|too|also|me|my)\b",
        " ", raw, flags=re.IGNORECASE
    ).strip()

    # Step 1: split on commas and 'and' / '&'
    parts = re.split(r",\s*|\s+and\s+|\s*&\s*", raw, flags=re.IGNORECASE)
    tokens = [p.strip().lower().rstrip(".,!?") for p in parts if p.strip()]

    if not tokens:
        return []

    # Step 2: for each token that isn't a known app, try splitting by whitespace
    _known = set(URL_MAP.keys()) | set(WIN_APP_MAP.keys())
    result: list[str] = []
    for token in tokens:
        if token in _known:
            result.append(token)
            continue
        # Try word-by-word splitting
        words = token.split()
        i, found = 0, False
        while i < len(words):
            # Try two-word combo first
            if i + 1 < len(words):
                two = f"{words[i]} {words[i+1]}"
                if two in _known:
                    result.append(two); i += 2; found = True; continue
            # Single word
            if words[i] in _known:
                result.append(words[i]); i += 1; found = True
            else:
                # Not in static maps — keep as-is for dynamic lookup
                result.append(words[i]); i += 1; found = True
        if not found:
            result.append(token)
    return list(dict.fromkeys(result))   # deduplicate preserving order


def _detect_and_execute_intent(text: str) -> str | None:
    """Parse user intent and execute locally. Returns spoken reply or None."""
    global _last_opened_browser, _session_last_active
    t = text.lower().strip()

    fast_cmd_prefix = r"^(?:(?:alright|okay|ok|sure|hey|hi|hello|virus|jarvis|can\s+you|could\s+you|would\s+you|please|just|kindly|let's|lets|now|i\s+want\s+to|i\s+need\s+to|i'd\s+like\s+to|can\s+we)\s*[,.]?\s*)*"

    # ── OPEN command ─────────────────────────────────────────────────────────
    open_match = re.search(
        fast_cmd_prefix + 
        r"(?:open|launch|start|pull\s+up|bring\s+up|load|run)\s+"
        r"(.+?)(?:\s+(?:in|on|with|for|using)\s+.*)?[.!?]?$",
        t, re.IGNORECASE
    )
    if open_match:
        raw  = open_match.group(1).strip().rstrip(".,!?")
        apps = _parse_app_list(raw)
        if not apps:
            return None

        opened_browser, opened_native, failed = [], [], []

        for app in apps:
            in_url = app in URL_MAP
            ok = _open_single(app)
            if ok:
                (opened_browser if in_url else opened_native).append(app)
            else:
                failed.append(app)

        all_opened = opened_browser + opened_native
        if not all_opened:
            return None   # let LLM handle (might not be an app open request)

        if opened_browser:
            _last_opened_browser = opened_browser[:]
        _session_last_active = time.time()

        phrases = [
            f"On it, sir. Launching {_format_names(all_opened)} right now.",
            f"Opening {_format_names(all_opened)} for you, sir.",
            f"{_format_names(all_opened)} coming right up, sir.",
            f"Done. {_format_names(all_opened)} should be up in a moment, sir.",
            f"Getting {_format_names(all_opened)} open for you now, sir.",
            f"Already on it, sir. {_format_names(all_opened)} loading now.",
        ]
        msg = random.choice(phrases)
        if failed:
            msg += f" Couldn't track down {_format_names(failed)} though, sir."
        return msg

    # ── CLOSE command ─────────────────────────────────────────────────────────
    close_match = re.search(
        fast_cmd_prefix + 
        r"(?:close|shut|exit|quit|kill|terminate)\s+(.+?)[.!?]?$",
        t, re.IGNORECASE
    )
    if close_match:
        raw = close_match.group(1).strip().rstrip(".,!?")

        if re.search(r"\b(all|them|everything|these)\b", raw):
            apps_to_close = _last_opened_browser[:] if _last_opened_browser else []
        else:
            apps_to_close = _parse_app_list(raw)

        if not apps_to_close:
            # Fallback: "close N tabs"
            if re.search(r"\d+\s*tabs?|tab", raw):
                count_m = re.search(r"(\d+)", raw)
                count   = int(count_m.group(1)) if count_m else 1
                try:
                    import pyautogui
                    for _ in range(min(count, 20)):
                        pyautogui.hotkey("ctrl", "w"); time.sleep(0.25)
                    return f"Closed {count} tab{'s' if count != 1 else ''}, sir."
                except Exception as e:
                    return f"Couldn't close tabs: {e}"
            return None

        closed, errors = [], []
        browser_apps = [a for a in apps_to_close if a in URL_MAP]
        other_apps   = [a for a in apps_to_close if a not in URL_MAP]

        # Close browser tabs
        if browser_apps:
            try:
                import pyautogui
                for _ in range(len(browser_apps)):
                    pyautogui.hotkey("ctrl", "w"); time.sleep(0.25)
                closed.extend(browser_apps)
            except ImportError:
                errors.extend(browser_apps)

        # Kill native apps
        for app in other_apps:
            ok = _close_single(app)
            (closed if ok else errors).append(app)

        _last_opened_browser.clear()

        if closed:
            phrases = [
                f"Closed {_format_names(closed)}, sir.",
                f"Done — {_format_names(closed)} shut down, sir.",
                f"All wrapped up. {_format_names(closed)} is gone, sir.",
                f"{_format_names(closed)} closed. Anything else, sir?",
                f"Took care of it — {_format_names(closed)} is closed, sir.",
            ]
            msg = random.choice(phrases)
            if errors:
                msg += f" Couldn't get {_format_names(errors)} to close, sir."
            return msg
        return None

    # ── PLAY command ─────────────────────────────────────────────────────────
    play_match = re.search(
        fast_cmd_prefix + 
        r"(?:play|put\s+on|stream)\s+(.+?)(?:\s+on\s+youtube)?[.!?]?$",
        t, re.IGNORECASE
    )
    if play_match:
        song_name = play_match.group(1).strip().rstrip(".,!?")
        import urllib.parse
        url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(song_name)}"
        webbrowser.open(url)

        phrases = [
            f"Pulling up {song_name} for you, sir.",
            f"Playing {song_name} right away, sir.",
            f"Got it, sir. Putting on {song_name}.",
            f"Streaming {song_name} now, sir.",
        ]
        return random.choice(phrases)

    return None   # no intent matched — let the LLM handle it


def _stream_to_tts(stream) -> str:
    """Consume a streaming Groq response, pushing sentences to TTS queue."""
    full = ""
    buf  = ""
    try:
        for chunk in stream:
            try:
                delta = chunk.choices[0].delta.content
            except Exception:
                continue
            if delta:
                full += delta
                buf  += delta
                if any(p in delta for p in [".", "!", "?", "\n"]):
                    if buf.strip():
                        tts_queue.put(buf.strip())
                        buf = ""
        if buf.strip():
            tts_queue.put(buf.strip())
    except Exception:
        log.error(f"[stream_to_tts] error:\n{traceback.format_exc()}")
        if buf.strip():
            tts_queue.put(buf.strip())
    return full


def _llm_reply(text: str):
    global is_llm_generating, _session_last_active
    if not groq_client:
        emit({"type": "reply_chunk", "value": "Groq AI is ready, sir."})
        emit({"type": "reply_end"})
        emit({"type": "status", "value": "idle"})
        return
    is_llm_generating = True
    emit({"type": "status", "value": "processing"})
    log.info(f"[LLM] processing: {text!r}")

    try:
        # 1. Check for local quick intent
        intent_result = _detect_and_execute_intent(text)
        if intent_result:
            log.info(f"[LLM] intent handled locally: {intent_result!r}")
            emit({"type": "status", "value": "speaking"})
            emit({"type": "reply_chunk", "value": intent_result})
            emit({"type": "reply_end"})
            emit({"type": "status", "value": "idle"})
            _add_memory("user", text)
            _add_memory("assistant", intent_result)
            return

        # 2. Ultra-fast streaming LLM via Groq llama-3.1-8b-instant (~60ms response)
        _add_memory("user", text)
        recent_memory = list(conversation_memory)[-6:] if len(conversation_memory) > 6 else list(conversation_memory)
        messages = [{"role": "system", "content": _get_system_prompt()}] + recent_memory

        log.info("[LLM] streaming fast response from Groq...")
        emit({"type": "status", "value": "speaking"})

        response_stream = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages,
            stream=True,
            temperature=0.6,
            max_tokens=250
        )

        full_reply = ""
        for chunk in response_stream:
            delta = chunk.choices[0].delta.content or ""
            if delta:
                full_reply += delta
                emit({"type": "reply_chunk", "value": delta})

        _add_memory("assistant", full_reply)
        emit({"type": "reply", "value": full_reply})
        emit({"type": "reply_end"})
        emit({"type": "status", "value": "idle"})
        _session_last_active = time.time()
        log.info(f"[LLM] Fast streaming complete: {len(full_reply)} chars")

    except Exception as e:
        log.error(f"[LLM] stream error: {e}")
        emit({"type": "reply_chunk", "value": "I am online and monitoring all systems, sir."})
        emit({"type": "reply_end"})
        emit({"type": "status", "value": "idle"})
    finally:
        is_llm_generating = False



# --- TTS WORKER THREAD ---
def _tts_worker():
    global is_playing_audio, is_llm_generating

    tts_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tts_player.py")
    player_proc = None
    _msg_q = queue.Queue()        # receives JSON messages from tts_player stdout

    def _reader_thread(proc):
        """Persistent thread: reads tts_player stdout into _msg_q."""
        try:
            for line in proc.stdout:
                line = line.strip()
                if line:
                    try:
                        _msg_q.put(json.loads(line))
                    except Exception:
                        pass
        except Exception:
            pass

    def _start_player():
        p = subprocess.Popen(
            [sys.executable, tts_script],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        # Drain stale messages
        while not _msg_q.empty():
            try: _msg_q.get_nowait()
            except Exception: pass
        # Start persistent reader
        threading.Thread(target=_reader_thread, args=(p,), daemon=True).start()
        # Wait for ready
        try:
            msg = _msg_q.get(timeout=15)
            log.info(f"[TTS-proc] started: {msg}")
        except queue.Empty:
            log.error("[TTS-proc] timed out waiting for ready")
        return p

    def _send(p, msg):
        try:
            p.stdin.write(json.dumps(msg) + "\n")
            p.stdin.flush()
        except Exception as e:
            log.warning(f"[TTS-proc] send error: {e}")

    def _play_text(p, text) -> bool:
        """Send play cmd; poll for done/stopped while checking barge_in_event.
        Returns True if barge-in interrupted, False if finished naturally."""
        # Drain any stale messages before starting
        while not _msg_q.empty():
            try: _msg_q.get_nowait()
            except Exception: pass

        _send(p, {"cmd": "play", "text": text})

        while True:
            # ── Check barge-in first ──────────────────────────────────────
            if barge_in_event.is_set():
                log.info("[TTS] barge-in event set -- sending stop to player")
                _send(p, {"cmd": "stop"})
                # Drain until player confirms stopped/done
                deadline = time.time() + 2.0
                while time.time() < deadline:
                    try:
                        ack = _msg_q.get(timeout=0.1)
                        if ack.get("type") in ("done", "stopped"):
                            break
                    except queue.Empty:
                        pass
                return True

            # ── Poll for player message ───────────────────────────────────
            try:
                msg = _msg_q.get(timeout=0.05)
                t = msg.get("type")
                if t == "playing":
                    continue          # audio started, keep looping
                elif t == "done":
                    return False      # finished naturally
                elif t == "stopped":
                    return True       # externally stopped
                elif t == "error":
                    log.error(f"[TTS-proc] {msg.get('msg','?')}")
                    return False
            except queue.Empty:
                continue

def _tts_worker():
    global is_playing_audio, player_proc

    if not HAS_PHYSICAL_AUDIO:
        log.info("[TTS] Cloud server mode active — streaming text directly to WebSocket.")
        while True:
            item = tts_queue.get()
            if item is None:
                break
            if isinstance(item, dict):
                if item.get("type") == "error":
                    emit({"type": "reply_chunk", "value": item.get("message", "Error") + " "})
                    continue
                if item.get("type") == "end_reply":
                    emit({"type": "reply_end"})
                    emit({"type": "status", "value": "idle"})
                    continue
            text = str(item).strip()
            if text:
                emit({"type": "status", "value": "speaking"})
                emit({"type": "reply_chunk", "value": text + " "})
                time.sleep(0.04)
        return

    try:
        player_proc = _start_player()
    except Exception:
        log.error(f"[TTS] Failed to start tts_player:\n{traceback.format_exc()}")
        return

    while True:
        item = tts_queue.get()
        if item is None:
            break

        is_playing_audio = True

        if isinstance(item, dict):
            if item.get("type") == "error":
                emit({"type": "reply_chunk", "value": item.get("message", "Error") + " "})
                continue
            if item.get("type") == "end_reply":
                emit({"type": "reply_end"})
                if tts_queue.empty() and not is_llm_generating:
                    time.sleep(0.3)
                    is_playing_audio = False
                    emit({"type": "status", "value": "idle"})
                continue

        text = item
        safe_text = text.replace('"', '').replace("'", "").strip()
        if not safe_text:
            if tts_queue.empty() and not is_llm_generating:
                time.sleep(0.3)
                is_playing_audio = False
                emit({"type": "status", "value": "idle"})
            continue

        try:
            if player_proc.poll() is not None:
                log.warning("[TTS] player died -- restarting")
                player_proc = _start_player()

            # Emit text to UI immediately — don't wait for synthesis
            emit({"type": "status", "value": "speaking"})
            emit({"type": "reply_chunk", "value": safe_text + " "})

            barged = _play_text(player_proc, safe_text)
            barge_in_event.clear()

            if barged:
                log.info("[TTS] barge-in -- draining queue")
                while not tts_queue.empty():
                    try: tts_queue.get_nowait()
                    except Exception: break

        except Exception:
            log.error(f"[TTS] error:\n{traceback.format_exc()}")
            try: player_proc.kill()
            except Exception: pass
            try: player_proc = _start_player()
            except Exception: log.error("[TTS] could not restart player")
        finally:
            if tts_queue.empty() and not is_llm_generating:
                time.sleep(0.3)
                is_playing_audio = False
                emit({"type": "status", "value": "idle"})

    try:
        _send(player_proc, {"cmd": "quit"})
        player_proc.wait(timeout=3)
    except Exception:
        try: player_proc.kill()
        except Exception: pass



@app.on_event("startup")
async def on_startup():
    global _loop
    _loop = asyncio.get_running_loop()
    
    if HAS_PHYSICAL_AUDIO:
        print("[VIRUS] Physical audio hardware detected. Starting local mic listener...")
        await asyncio.sleep(1.0)
        threading.Thread(target=_thread_wrap, args=(_mic_read_thread,  "mic_read_thread"),  daemon=True).start()
        threading.Thread(target=_thread_wrap, args=(_whisper_thread,   "whisper_thread"),   daemon=True).start()
        threading.Thread(target=_thread_wrap, args=(_barge_in_monitor, "barge_in_monitor"), daemon=True).start()
    else:
        log.info("[VIRUS] Headless cloud server detected. Running in cloud mode.")

    threading.Thread(target=_thread_wrap, args=(_level_thread,     "level_thread"),     daemon=True).start()
    threading.Thread(target=_thread_wrap, args=(_sys_metrics_thread,"sys_metrics_thread"), daemon=True).start()
    threading.Thread(target=_thread_wrap, args=(_cricket_thread,   "cricket_thread"),   daemon=True).start()
    threading.Thread(target=_thread_wrap, args=(_tts_worker,       "tts_worker"),       daemon=True).start()
    log.info("[VIRUS] All active background threads started.")

# ─── WEBSOCKET ───────────────────────────────────────────────────────────
@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    clients.append(ws)
    try:
        # Immediately emit active status and system metrics to connected client
        await ws.send_text(json.dumps({"type": "status", "value": "idle"}))
        await ws.send_text(json.dumps({
            "type": "sys_metrics", 
            "value": {
                "cpu": psutil.cpu_percent(interval=None) if 'psutil' in sys.modules else 0,
                "ram": psutil.virtual_memory().percent if 'psutil' in sys.modules else 0,
                "ping": 12
            }
        }))
        while True:
            msg = await ws.receive_text()
            if msg == "clear_memory":
                _clear_memory()
            elif msg.startswith("{"):
                try:
                    data = json.loads(msg)
                    if data.get("type") == "user_text":
                        threading.Thread(target=lambda t=data.get("text", ""): _llm_reply(t), daemon=True).start()
                except Exception as e:
                    log.warning(f"WebSocket parse error: {e}")
    except WebSocketDisconnect:
        if ws in clients:
            clients.remove(ws)

# ─── ENTRY POINT ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("virus_server:app", host="0.0.0.0", port=8000, reload=False)
