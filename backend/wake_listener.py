"""
V.I.R.U.S. Wake Listener
========================
Two-stage wake engine:
  Stage 1 - Listens for a sharp clap (energy spike) with near-zero CPU.
  Stage 2 - Records 4 seconds of audio, transcribes with faster-whisper
             (tiny model), checks if the word "virus" was spoken.
  On confirm - runs launch_virus.bat and exits cleanly so the backend can own
               the microphone.

Configuration via .env:
  WAKE_PHRASE=virus               Word to detect after clap (default: virus)
  CLAP_THRESHOLD=0.07             RMS threshold 0.05 (quiet) -> 0.30 (loud clap)
  WAKE_LISTEN_SECONDS=4           Seconds to record for voice confirm
  WAKE_COOLDOWN=2                 Min seconds between clap detections
"""

import os, sys, time, wave, struct, tempfile, subprocess, pathlib, logging, socket

# ── Paths (resolved before anything else) ─────────────────────────────────────
BACKEND_DIR  = pathlib.Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
ENV_FILE     = BACKEND_DIR / ".env"
LAUNCH_BAT   = PROJECT_ROOT / "launch_virus.bat"
LOG_FILE     = BACKEND_DIR / "wake_listener.log"

# ── File logging (works even when launched by pythonw with no console) ─────────
logging.basicConfig(
    level=logging.INFO,          # INFO only — suppresses httpcore/whisper DEBUG spam
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),   # also print if console exists
    ],
)
# Silence noisy third-party loggers
for _noisy in ("httpcore", "httpx", "urllib3", "faster_whisper"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)
log = logging.getLogger("wake")

def _log_safe(msg: str, level=logging.INFO):
    try:
        log.log(level, msg)
    except Exception:
        pass


# ── Load .env explicitly ───────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=ENV_FILE, override=True)
    _log_safe(f".env loaded from {ENV_FILE}")
except Exception as e:
    _log_safe(f".env load failed: {e}", logging.WARNING)

# ── Config ────────────────────────────────────────────────────────────────────
WAKE_PHRASE         = os.getenv("WAKE_PHRASE",         "virus").lower().strip()
CLAP_THRESHOLD      = float(os.getenv("CLAP_THRESHOLD",    "0.07"))
WAKE_LISTEN_SECONDS = int(os.getenv("WAKE_LISTEN_SECONDS", "4"))
COOLDOWN_SECONDS    = float(os.getenv("WAKE_COOLDOWN",     "2"))

# Phonetic variants Whisper-tiny commonly produces instead of "virus"
# Extend this list if you notice new mishearings in the log.
_WAKE_VARIANTS = {
    # Direct matches
    "virus", "virus.", "virus!",
    # Common Whisper-tiny mishearings (observed in logs)
    "vairas", "viris", "vyrus", "vires", "virrus", "virous",
    "biris", "birus", "wirus", "waitress", "vieras", "viras",
    "virus,", "viruse", "viruses", "virusy",
}

# ── Audio settings ─────────────────────────────────────────────────────────────
RATE     = 16_000
CHUNK    = 512
CHANNELS = 1

import pyaudio
FORMAT = pyaudio.paInt16

# ── Whisper model (loaded once at startup, not per transcription) ──────────────
_whisper_model = None

def _get_whisper():
    global _whisper_model
    if _whisper_model is None:
        _log_safe("Loading faster-whisper tiny model (first run may download)...")
        from faster_whisper import WhisperModel
        _whisper_model = WhisperModel(
            "tiny",
            device="cpu",
            compute_type="int8",
            local_files_only=False,   # downloads if missing, cached after
        )
        _log_safe("Whisper model ready.")
    return _whisper_model


# ── Helpers ───────────────────────────────────────────────────────────────────
def rms(raw_bytes: bytes) -> float:
    """Root-mean-square energy of a 16-bit PCM chunk, normalised 0→1."""
    n = len(raw_bytes) // 2
    if n == 0:
        return 0.0
    samples = struct.unpack(f"{n}h", raw_bytes)
    mean_sq = sum(s * s for s in samples) / n
    return (mean_sq ** 0.5) / 32_768.0


def record_clip(stream, seconds: int) -> bytes:
    """Capture `seconds` of audio from the open stream."""
    frames = []
    chunks = int(RATE / CHUNK * seconds)
    for _ in range(chunks):
        frames.append(stream.read(CHUNK, exception_on_overflow=False))
    return b"".join(frames)


def _phrase_matched(transcript: str) -> bool:
    """Return True if any wake variant appears in the transcript."""
    cleaned = transcript.lower()
    # Filter out Whisper hallucinating the initial prompt
    prompt1 = f"the user will say the word {WAKE_PHRASE}."
    prompt2 = f"the user will say the word {WAKE_PHRASE}"
    cleaned = cleaned.replace(prompt1.lower(), "").replace(prompt2.lower(), "")
    
    words = cleaned.replace(",", " ").replace(".", " ").replace("!", " ").split()
    return bool(_WAKE_VARIANTS.intersection(words))


def transcribe_clip(raw_bytes: bytes) -> str:
    """Transcribe raw PCM using faster-whisper tiny (model cached at startup)."""
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    try:
        with wave.open(tmp.name, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(2)
            wf.setframerate(RATE)
            wf.writeframes(raw_bytes)
        tmp.close()

        model = _get_whisper()
        segments, info = model.transcribe(
            tmp.name,
            language="en",
            beam_size=3,
            initial_prompt=f"The user will say the word {WAKE_PHRASE}.",
            no_speech_threshold=0.6,      # discard hallucinations on silence
            condition_on_previous_text=False,
        )
        text = " ".join(seg.text for seg in segments).lower().strip()
        return text
    except Exception as e:
        _log_safe(f"Transcription error: {e}", logging.ERROR)
        return ""
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


def open_audio_stream(retries: int = 5, delay: float = 2.0):
    """Open PyAudio input stream with retry logic."""
    for attempt in range(1, retries + 1):
        try:
            audio = pyaudio.PyAudio()
            stream = audio.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK,
            )
            _log_safe(f"Microphone opened on attempt {attempt}.")
            return audio, stream
        except Exception as e:
            _log_safe(f"Mic open attempt {attempt}/{retries} failed: {e}", logging.WARNING)
            try:
                audio.terminate()
            except Exception:
                pass
            if attempt < retries:
                time.sleep(delay)
    _log_safe("Could not open microphone after all retries — exiting.", logging.ERROR)
    sys.exit(1)


# ── App-running check ─────────────────────────────────────────────────────────
BACKEND_PORT = int(os.getenv("BACKEND_PORT", "8000"))
BOOT_LOCK_FILE = BACKEND_DIR / ".boot_lock"

def is_app_running() -> bool:
    """Return True if the V.I.R.U.S. backend is already up on its port OR if it's currently launching."""
    if BOOT_LOCK_FILE.exists():
        return True
    try:
        with socket.create_connection(("127.0.0.1", BACKEND_PORT), timeout=0.5):
            return True
    except OSError:
        return False



# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    _log_safe("=" * 56)
    _log_safe("  V.I.R.U.S.  |  Wake Listener  |  Active")
    _log_safe(f"  Clap threshold : {CLAP_THRESHOLD}")
    _log_safe(f"  Wake phrase    : '{WAKE_PHRASE}'")
    _log_safe(f"  Listen window  : {WAKE_LISTEN_SECONDS}s after clap")
    _log_safe(f"  Launch script  : {LAUNCH_BAT}")
    _log_safe(f"  Log file       : {LOG_FILE}")
    _log_safe("=" * 56)

    # ── If V.I.R.U.S. is already open, wait until it closes before arming ──────
    if is_app_running():
        _log_safe(f"[STANDBY] V.I.R.U.S. backend already running on port {BACKEND_PORT}. "
                   "Waiting for it to close before arming wake listener...")
        while is_app_running():
            time.sleep(5)
        _log_safe("[STANDBY] Backend closed — wake listener now armed.")

    _log_safe("Listening for a clap...")

    audio, stream = open_audio_stream()
    last_trigger = 0.0
    last_app_check = time.time()

    try:
        while True:
            try:
                data  = stream.read(CHUNK, exception_on_overflow=False)
            except OSError as e:
                _log_safe(f"Stream read error: {e} — reopening mic...", logging.WARNING)
                try:
                    stream.stop_stream(); stream.close(); audio.terminate()
                except Exception:
                    pass
                time.sleep(2)
                audio, stream = open_audio_stream()
                last_trigger = 0.0
                last_app_check = time.time()
                continue

            level = rms(data)
            now   = time.time()

            if now - last_app_check > 2.0:
                last_app_check = now
                if is_app_running():
                    _log_safe("[STANDBY] App opened (periodic check). Releasing mic...")
                    stream.stop_stream(); stream.close(); audio.terminate()
                    while is_app_running():
                        time.sleep(5)
                    sys.exit(0)  # Supervisor restarts us in standby mode

            if level > CLAP_THRESHOLD and (now - last_trigger) > COOLDOWN_SECONDS:
                last_trigger = now
                _log_safe(f"[CLAP DETECTED] RMS={level:.4f} (threshold={CLAP_THRESHOLD}) "
                           f"→ Recording {WAKE_LISTEN_SECONDS}s for phrase match...")

                audio_bytes = record_clip(stream, WAKE_LISTEN_SECONDS)

                _log_safe("Transcribing audio clip...")
                transcript = transcribe_clip(audio_bytes)
                _log_safe(f'Heard: "{transcript}"')

                if _phrase_matched(transcript):
                    # ── Guard: don't re-launch if already running ──────────────
                    if is_app_running():
                        _log_safe("[BLOCKED] Wake confirmed but V.I.R.U.S. is already running — ignoring launch.")
                        _log_safe("[STANDBY] Waiting for app to close before re-arming...")
                        # Close mic, wait for app to close, then exit so supervisor
                        # can restart us cleanly in standby mode
                        stream.stop_stream()
                        stream.close()
                        audio.terminate()
                        while is_app_running():
                            time.sleep(5)
                        sys.exit(0)   # Supervisor will restart us in standby mode

                    _log_safe(f"[WAKE CONFIRMED] '{WAKE_PHRASE}' (or variant) detected! Launching V.I.R.U.S. ...")

                    # Release mic BEFORE backend starts (it needs the mic)
                    stream.stop_stream()
                    stream.close()
                    audio.terminate()

                    if LAUNCH_BAT.exists():
                        BOOT_LOCK_FILE.touch()
                        subprocess.Popen(
                            ["cmd", "/c", str(LAUNCH_BAT)],
                            creationflags=subprocess.CREATE_NEW_CONSOLE,
                        )
                        _log_safe("launch_virus.bat fired successfully and boot-lock established.")
                    else:
                        _log_safe(f"[ERROR] launch_virus.bat not found at {LAUNCH_BAT}", logging.ERROR)

                    sys.exit(0)   # Exit cleanly — supervisor will revive us later

                else:
                    # After any transcription, check if app opened in the meantime
                    if is_app_running():
                        _log_safe("[STANDBY] App just opened. Waiting for it to close...")
                        stream.stop_stream(); stream.close(); audio.terminate()
                        while is_app_running():
                            time.sleep(5)
                        sys.exit(0)   # Supervisor restarts us in standby mode
                    _log_safe(f"[FALSE TRIGGER] '{WAKE_PHRASE}' not matched in: '{transcript}' — resuming listen.")

    except KeyboardInterrupt:
        _log_safe("Stopped by user (KeyboardInterrupt).")
    except Exception as e:
        _log_safe(f"Unexpected error in main loop: {e}", logging.ERROR)
        raise
    finally:
        try:
            stream.stop_stream()
            stream.close()
            audio.terminate()
        except Exception:
            pass
        _log_safe("Wake listener exiting.")


if __name__ == "__main__":
    main()
