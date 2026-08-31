# V.I.R.U.S. Wake System — Setup Guide

## What Was Built

```
V.I.R.U.S\
├── backend\
│   ├── wake_listener.py       ← Two-stage wake: clap + "hey virus"
│   └── virus_supervisor.py   ← Boot manager + system tray
├── tauri-app\
│   ├── package.json
│   └── src-tauri\
│       ├── Cargo.toml
│       ├── tauri.conf.json
│       └── src\main.rs       ← Kills backend on window close
├── launch_virus.bat           ← Full launch sequence
└── install_autostart.bat      ← One-time Windows boot hook
```

---

## Do These Steps IN ORDER

### Step 1 — Install Rust (one-time, ~5 min)

Open PowerShell and run:
```powershell
winget install Rustlang.Rustup
```
Then restart your terminal. Verify with:
```powershell
rustc --version
```

### Step 2 — Install VS Build Tools (if you don't have them)

Download from: https://visualstudio.microsoft.com/visual-cpp-build-tools/
Install the **"Desktop development with C++"** workload. (~2GB, one-time)

### Step 3 — Install Tauri CLI

```powershell
cd C:\Users\aakas\OneDrive\Desktop\V.I.R.U.S\tauri-app
npm install
```

### Step 4 — TEST THE WAKE LISTENER FIRST

```powershell
cd C:\Users\aakas\OneDrive\Desktop\V.I.R.U.S\backend
python wake_listener.py
```

- Clap once → should print `[CLAP DETECTED]`
- Say "hey virus" → should print `[WAKE CONFIRMED]`
- Say something else after clap → should print `[FALSE TRIGGER]`

**Do not move on until this passes.** If clap isn't detected, lower `CLAP_THRESHOLD` in `.env`.

### Step 5 — Build the Tauri exe (~8 min first time)

```powershell
cd C:\Users\aakas\OneDrive\Desktop\V.I.R.U.S\frontend
npm run build

cd C:\Users\aakas\OneDrive\Desktop\V.I.R.U.S\tauri-app
npx tauri build
```

The exe will be at:
```
tauri-app\src-tauri\target\release\v-i-r-u-s.exe
```

### Step 6 — TEST THE FULL CYCLE

Open a terminal and run:
```powershell
python C:\Users\aakas\OneDrive\Desktop\V.I.R.U.S\backend\virus_supervisor.py
```

Then:
1. Clap + say "virus" → V.I.R.U.S. should launch fully
2. Close the window → supervisor should restart the wake listener
3. Clap + say "virus" again → second launch works

**Do not install autostart until this passes.**

### Step 7 — Register autostart (one-time)

Double-click `install_autostart.bat`

Then log out and back in. The tray icon (coloured dot) should appear without you doing anything.

---

## .env Settings

Add these to `backend\.env`:

```
WAKE_PHRASE=virus
CLAP_THRESHOLD=0.15
WAKE_LISTEN_SECONDS=4
WAKE_COOLDOWN=2
```

Tuning:
- `CLAP_THRESHOLD=0.08` → very sensitive (soft clap)
- `CLAP_THRESHOLD=0.25` → needs loud clap (prevents false triggers from music)
- `WAKE_PHRASE=hey virus` → checks for the full phrase instead of just "virus"

---

## Tray Icon Colors

| Color  | Meaning                          |
|--------|----------------------------------|
| 🟢 Green | Listening for clap               |
| 🔵 Blue  | V.I.R.U.S. is active             |
| ⚫ Grey  | Listener paused                   |

Right-click the tray icon for: **Launch Now**, **Pause/Resume**, **Quit**

---

## Troubleshooting

**Clap not detecting:**
Lower `CLAP_THRESHOLD` to `0.08` in `.env`

**"virus" not being heard:**
Lower your mic sensitivity in Windows Sound Settings → Recording → Properties → Levels.
Speak clearly and not too fast after the clap.

**Tauri build fails with "MSVC not found":**
You need VS Build Tools. Run the installer from Step 2 again.

**Backend doesn't start:**
The launch bat polls `http://localhost:8000/` — if your backend doesn't have a root GET endpoint it will time out after 30s but still open the window. V.I.R.U.S. will still work.

**To remove autostart:**
```powershell
schtasks /delete /tn "VIRUS_Supervisor" /f
```
