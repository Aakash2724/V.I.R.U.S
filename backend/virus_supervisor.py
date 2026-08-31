"""
V.I.R.U.S. Supervisor
=====================
Runs silently at Windows boot (registered via Task Scheduler).

Responsibilities:
  1. Start wake_listener.py on launch.
  2. Poll port 8000 every 5 s to watch if the backend is alive.
  3. When backend goes offline  → wait 3 s → restart wake listener.
  4. If listener dies unexpectedly → restart it.
  5. System-tray icon with right-click menu:
       • V.I.R.U.S. Status (label)
       • Launch Now (skip wake word)
       • Pause / Resume Listener
       • Quit Supervisor
"""

import os, sys, time, socket, threading, subprocess, pathlib

BACKEND_PORT   = 8000
POLL_INTERVAL  = 5      # seconds between health checks
RESTART_DELAY  = 3      # seconds to wait after backend goes down before relaunching listener

BACKEND_DIR  = pathlib.Path(__file__).parent
PROJECT_ROOT = BACKEND_DIR.parent
WAKE_SCRIPT  = BACKEND_DIR / "wake_listener.py"
LAUNCH_BAT   = PROJECT_ROOT / "launch_virus.bat"
PYTHON       = sys.executable

# ── State ─────────────────────────────────────────────────────────────────
listener_proc:      subprocess.Popen | None = None
backend_was_active: bool = False
paused:             bool = False
tray_icon                = None   # pystray icon or None if not available

# ── Optional tray dependencies ─────────────────────────────────────────────
try:
    import pystray
    from PIL import Image, ImageDraw
    HAS_TRAY = True
except ImportError:
    HAS_TRAY = False
    print("[SUPERVISOR] pystray / Pillow not installed — no tray icon. "
          "Install with:  pip install pystray Pillow")


# ── Port check ────────────────────────────────────────────────────────────
def is_port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return True
    except OSError:
        return False


# ── Listener management ────────────────────────────────────────────────────
def _listener_running() -> bool:
    global listener_proc
    return listener_proc is not None and listener_proc.poll() is None


def start_listener():
    global listener_proc
    if _listener_running():
        return
    print("[SUPERVISOR] Starting wake listener ...")
    listener_proc = subprocess.Popen(
        [PYTHON, str(WAKE_SCRIPT)],
        # Hide terminal window on Windows
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    print(f"[SUPERVISOR] Wake listener PID={listener_proc.pid}")
    _set_tray_state("listening")


def stop_listener():
    global listener_proc
    if _listener_running():
        listener_proc.terminate()
        try:
            listener_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            listener_proc.kill()
    listener_proc = None
    _set_tray_state("paused")


# ── Monitor loop (background thread) ──────────────────────────────────────
def _monitor():
    global backend_was_active, paused

    while True:
        time.sleep(POLL_INTERVAL)
        if paused:
            continue

        alive = is_port_open(BACKEND_PORT)

        if alive and not backend_was_active:
            print("[SUPERVISOR] Backend came online.")
            backend_was_active = True
            _set_tray_state("active")

        elif not alive and backend_was_active:
            print(f"[SUPERVISOR] Backend went offline. Waiting {RESTART_DELAY}s ...")
            time.sleep(RESTART_DELAY)
            backend_was_active = False
            if not paused:
                print("[SUPERVISOR] Restarting wake listener.")
                start_listener()

        elif not alive and not _listener_running() and not paused:
            # Listener died for some reason — revive it
            print("[SUPERVISOR] Wake listener died unexpectedly — restarting.")
            start_listener()


# ── Tray helpers ───────────────────────────────────────────────────────────
_TRAY_COLORS = {
    "listening": (0, 210, 120, 255),    # green
    "active":    (0, 102, 255, 255),    # blue
    "paused":    (80,  80, 80,  255),   # grey
}

def _make_icon(state: str):
    color = _TRAY_COLORS.get(state, (80, 80, 80, 255))
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d   = ImageDraw.Draw(img)
    d.ellipse([4, 4, 60, 60], fill=color)
    return img

def _set_tray_state(state: str):
    if HAS_TRAY and tray_icon is not None:
        try:
            tray_icon.icon = _make_icon(state)
        except Exception:
            pass


# ── Tray menu handlers ─────────────────────────────────────────────────────
def _launch_now(icon=None, item=None):
    stop_listener()
    subprocess.Popen(
        ["cmd", "/c", str(LAUNCH_BAT)],
        creationflags=subprocess.CREATE_NEW_CONSOLE,
    )

def _toggle_pause(icon=None, item=None):
    global paused
    if paused:
        paused = False
        start_listener()
        print("[SUPERVISOR] Listener resumed.")
    else:
        paused = True
        stop_listener()
        print("[SUPERVISOR] Listener paused.")

def _quit(icon=None, item=None):
    stop_listener()
    if HAS_TRAY and tray_icon is not None:
        tray_icon.stop()
    os._exit(0)


# ── Tray creation (blocks main thread — must run last) ─────────────────────
def _run_tray():
    global tray_icon
    menu = pystray.Menu(
        pystray.MenuItem("V.I.R.U.S.  Supervisor", None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Launch Now  (skip wake word)", _launch_now),
        pystray.MenuItem("Pause / Resume  Listener",     _toggle_pause),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit Supervisor",               _quit),
    )
    tray_icon = pystray.Icon(
        name   = "VIRUS_Supervisor",
        icon   = _make_icon("listening"),
        title  = "V.I.R.U.S.  Supervisor  —  Listening",
        menu   = menu,
    )
    tray_icon.run()   # blocks


# ── Entry point ────────────────────────────────────────────────────────────
def main():
    print("[SUPERVISOR] V.I.R.U.S.  Supervisor  starting ...")

    # Start the wake listener immediately
    start_listener()

    # Health-monitor loop runs in a daemon thread
    t = threading.Thread(target=_monitor, daemon=True)
    t.start()

    if HAS_TRAY:
        _run_tray()          # blocks main thread (tray runs the message loop)
    else:
        print("[SUPERVISOR] Running headless (no tray). Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            _quit()


if __name__ == "__main__":
    main()
