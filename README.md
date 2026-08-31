# V.I.R.U.S. — Voice Intelligence & Real-time Utility System

> A fast, voice-controlled AI desktop companion for Windows with a Cyberpunk-style HUD, hands-free wake word detection, and full system control.

---

## What is V.I.R.U.S.?

V.I.R.U.S. is a personal AI assistant built for Windows that bridges natural conversation with real desktop automation. 

Instead of just chatting in a browser tab, V.I.R.U.S. lives on your machine. You can talk to it to launch apps, manage system settings (brightness, volume, Wi-Fi), take notes directly to your desktop, play music on YouTube, get web search summaries, set timed voice reminders, and keep track of live cricket scores — all visualized through a real-time reactive 3D plasma orb and modular HUD widgets.

---

## How It Works (For Beginners)

If you're new to AI or desktop automation, here is the simple breakdown of what happens when you speak:

```
  [ Your Voice / Clap ]
           │
           ▼
  [ Silero VAD + Faster-Whisper ]  ──► Listens and converts speech to text locally & in the cloud
           │
           ▼
  [ Groq API (Llama 3.1-8b) ]     ──► Understands your intent & decides what action/tool to run
           │
           ▼
  [ Python Desktop Engine ]       ──► Performs the Windows action (opens app, sets volume, writes note)
           │
           ▼
  [ Edge-TTS + Audio Player ]     ──► Speaks the natural response back to you (with barge-in interrupt)
           │
           ▼
  [ React + Three.js Plasma HUD ] ──► Visualizes the voice frequencies & status in real-time
```

1. **Hearing you**: Silero VAD detects when you start and stop talking, while Faster-Whisper and Groq Whisper translate your speech to text in real time.
2. **Thinking**: Groq's high-speed Llama 3.1 model processes your request and chooses whether to just answer your question or execute a system tool.
3. **Acting**: The Python FastAPI backend executes the task on your Windows machine (like creating a file or adjusting volume).
4. **Speaking & Visualizing**: Microsoft Edge-TTS delivers clean speech, while a React + Three.js frontend pulses an audio-reactive plasma orb and updates the dashboard widgets.

---

## Key Features

### 🎙️ Smart Voice & Hands-Free Wake
- **Two-stage wake trigger**: Wake it up with a simple hand clap followed by *"hey virus"* (or trigger it directly from the system tray).
- **Fast speech-to-text**: Dual transcription engine using local Faster-Whisper + Groq cloud Whisper for low latency.
- **Barge-in interruption**: If V.I.R.U.S. is speaking and you start talking again, it immediately stops playback to listen to you.
- **Short-term memory**: Keeps context of your recent conversation in a local SQLite database (`virus_brain.db`).

### 💻 Windows Desktop Automation
- **App & site launcher**: Say *"open VS Code"*, *"launch Spotify"*, *"open YouTube"*, or *"open WhatsApp"* — it tries native desktop apps first and falls back to web browsers automatically.
- **Hardware & system controls**: Adjust volume (up/down/mute), adjust screen brightness, jump into Wi-Fi or Bluetooth settings, lock your screen, or shut down/restart.
- **Notification manager**: Check pending notifications or clear them silently with your voice.
- **Browser helper**: Close tabs hands-free (*"close 2 tabs"*).

### 📝 Productivity & Research
- **Voice-to-Notepad**: Say *"write a note called shopping list: milk, eggs, bread"* and it will save the file right onto your Desktop and open it.
- **Web search & summaries**: Ask about current events, movies, or research topics; it queries the web and reads back the top findings (and can save them to a text file on demand).
- **Spoken reminders**: Ask *"remind me to check the oven in 10 minutes"* and V.I.R.U.S. will speak when the timer is up.
- **Document reader**: Summarize or extract information from PDFs and text files in your Documents folder.

### 🌐 Cyberpunk Glassmorphism HUD
- **Audio-reactive 3D plasma orb**: Rendered with Three.js shaders that morph and glow with your voice and the assistant's speech.
- **Modular draggable widgets**:
  - 📍 **Location & Weather**: City, date, and local time.
  - ⚡ **Hardware Stats**: Live CPU load, RAM usage, and WebSocket latency ping.
  - 🏏 **Cricket Scores**: Real-time cricket score updates.
  - 📊 **Activity Monitor**: Command count and uptime tracker.
  - 💻 **Live Terminal**: Glowing log stream showing live transcription and backend events.

---

## Tech Stack

- **Backend**: Python 3.10+, FastAPI, Uvicorn, WebSockets, PyAudio, SoundCard, PyAutoGUI, SQLite
- **AI Models & Speech**: Groq API (Llama 3.1-8b-instant, Whisper-large-v3), Faster-Whisper, Silero VAD, Edge-TTS, Pygame
- **Frontend**: React 18, Three.js / WebGL, HTML5 WebSockets, CSS Glassmorphism
- **System Integration**: Python Win32 APIs, PowerShell automation, Windows Task Scheduler / System Tray (`pystray`)

---

## Quick Start (Step-by-Step)

### Prerequisites

Make sure you have the following installed on your Windows machine:
1. **Python 3.10 or newer** — [python.org](https://www.python.org/downloads/) *(make sure to check "Add Python to PATH" during installation)*
2. **Node.js 18 or newer** — [nodejs.org](https://nodejs.org/)
3. **A free Groq API Key** — [console.groq.com](https://console.groq.com/keys) *(free and fast)*

---

### Step 1 — Clone the Repository

Open PowerShell or Command Prompt:

```powershell
git clone https://github.com/Aakash2724/V.I.R.U.S.git
cd V.I.R.U.S
```

---

### Step 2 — Set Up the Backend

1. Move into the backend directory:
   ```powershell
   cd backend
   ```

2. Create and activate a Python virtual environment:
   ```powershell
   python -m venv venv
   .\venv\Scripts\activate
   ```

3. Install the dependencies:
   ```powershell
   pip install -r requirements.txt
   ```

4. Create your `.env` file:
   Copy `.env.example` to `.env` (or create a new file named `.env` in the `backend` folder) and add your keys:
   ```ini
   GROQ_API_KEY=gsk_your_actual_groq_api_key_here
   CLAP_THRESHOLD=0.15
   INPUT_DEVICE=1
   ```

---

### Step 3 — Set Up the Frontend

1. Open a new terminal window and navigate to the frontend folder:
   ```powershell
   cd frontend
   ```

2. Install the node packages:
   ```powershell
   npm install
   ```

---

### Step 4 — Run V.I.R.U.S.

#### Option A: Quick Launch Script (Recommended)
From the root folder, double-click **`launch_virus.bat`** or run:
```powershell
.\launch_virus.bat
```
This script automatically starts the backend server, launches the frontend, and opens the HUD in a clean standalone app window.

#### Option B: Manual Start (Terminal by Terminal)

1. **Start Backend**:
   ```powershell
   cd backend
   .\venv\Scripts\activate
   python -m uvicorn virus_server:app --host 0.0.0.0 --port 8000 --reload
   ```

2. **Start Frontend**:
   ```powershell
   cd frontend
   npm start
   ```
   Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## Example Voice Commands to Try

Once V.I.R.U.S. is running, speak naturally into your microphone:

| Category | Example Commands |
|---|---|
| **Conversation** | *"Who are you?"*, *"What time is it in Tokyo?"*, *"Explain quantum computing in two sentences."* |
| **App Launching** | *"Open VS Code"*, *"Launch Spotify"*, *"Open YouTube"*, *"Open Calculator"* |
| **System Control** | *"Increase volume"*, *"Mute audio"*, *"Set screen brightness to 70 percent"*, *"Lock screen"* |
| **Media Playback** | *"Play Interstellar soundtrack on YouTube"*, *"Play some relaxing lo-fi beats"* |
| **Notes & Files** | *"Write a note named project ideas with build a voice assistant"* |
| **Web Research** | *"Search the web for latest space discoveries and save it to notepad"* |
| **Reminders** | *"Remind me to drink water in 15 minutes"* |
| **Notifications** | *"Do I have any notifications?"*, *"Clear all notifications"* |

---

## Background Wake Listener & System Tray

V.I.R.U.S. includes a lightweight supervisor that can run quietly in your Windows system tray:

- **Green dot** 🟢: Listening for a hand clap / wake word.
- **Blue dot** 🔵: V.I.R.U.S. session is active.
- **Grey dot** ⚫: Listener is paused.

To test the wake listener directly:
```powershell
cd backend
python wake_listener.py
```
1. Clap once → `[CLAP DETECTED]`
2. Say *"hey virus"* → `[WAKE CONFIRMED]` and launches the HUD!

*(Optional: To run V.I.R.U.S. automatically every time you log into Windows, double-click `install_autostart.bat`.)*

---

## Project Structure

```
V.I.R.U.S/
├── backend/
│   ├── virus_server.py        # Core FastAPI backend, WebSocket engine & tool executor
│   ├── virus_supervisor.py    # Background process manager & system tray app
│   ├── wake_listener.py       # Two-stage wake word & clap detection
│   ├── tts_player.py          # Edge-TTS audio playback with barge-in support
│   ├── virus_brain.db         # SQLite persistent conversation memory
│   ├── requirements.txt       # Python dependencies
│   └── .env.example           # Environment template
│
├── frontend/
│   ├── public/                # Static assets
│   ├── src/
│   │   ├── component/         # React HUD widgets (Blob, Terminal, Hardware, Cricket, etc.)
│   │   ├── hooks/             # WebSocket and microphone audio hooks
│   │   ├── App.js             # Main dashboard layout and widget state
│   │   └── index.css          # Cyberpunk glassmorphism styling
│   └── package.json           # Frontend dependencies
│
├── launch_virus.bat           # One-click launcher for backend + frontend
├── install_autostart.bat      # Optional script to register Windows login startup
└── README.md
```

---

## Tuning & Customization

You can tune sensitivity settings inside `backend/.env`:

- `CLAP_THRESHOLD=0.15` — Sensitivity for clap detection (lower like `0.08` for soft claps, higher like `0.25` to ignore background noises).
- `WAKE_PHRASE=virus` — Set the wake phrase you want to use after clapping.
- `INPUT_DEVICE` — Select your preferred microphone device index (run `python backend/check_mic.py` to list your mics).

---

## Troubleshooting

- **Microphone not picking up anything**:
  - Run `python backend/check_mic.py` to see which device number Windows assigned to your active microphone, then update `INPUT_DEVICE` in `backend/.env`.
- **Groq errors or no spoken replies**:
  - Double-check that your `GROQ_API_KEY` in `backend/.env` is valid and has no extra spaces or quotes.
- **Port 8000 already in use**:
  - `launch_virus.bat` automatically frees port 8000. If running manually, open Task Manager and end any lingering Python or Uvicorn tasks.
- **Clap not detected**:
  - Lower the `CLAP_THRESHOLD` value in `backend/.env` (try `0.10` or `0.08`).

---

## Contributing & Feedback

Have ideas for new widgets, system tools, or optimizations? Feel free to open an issue or submit a pull request!

---

## Author

Created by **[Akash](https://github.com/Aakash2724)**  
*Building personal AI tools that make desktop computing feel like the future.*
