"""
tts_player.py - Standalone TTS + audio subprocess
==================================================
Main thread reads JSON commands from stdin.
Each "play" command launches a background thread — so "stop" from stdin
is received instantly while audio is playing.
"""
import sys, asyncio, os, json, time, tempfile, traceback, threading

if sys.platform == "win32":
    os.environ.setdefault("SDL_AUDIODRIVER", "directsound")
else:
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import edge_tts

try:
    import pygame
    pygame.mixer.pre_init(44100, -16, 1, 1024)
    pygame.mixer.init()
except Exception as e:
    pygame = None

_stop_event = threading.Event()   # set to interrupt current playback
_play_lock  = threading.Lock()    # only one play at a time


def send(msg: dict):
    print(json.dumps(msg), flush=True)


async def _gen(text: str, path: str):
    c = edge_tts.Communicate(text, voice="en-US-JennyNeural", rate="+10%")
    await c.save(path)


def _play_thread(text: str):
    """Run in a daemon thread. Checks _stop_event every 30 ms."""
    with _play_lock:
        _stop_event.clear()
        tmp = tempfile.mktemp(suffix=".mp3")
        try:
            asyncio.run(_gen(text, tmp))

            if not os.path.exists(tmp):
                send({"type": "error", "msg": "mp3 not generated"})
                return

            if pygame and pygame.mixer.get_init():
                pygame.mixer.music.load(tmp)
                pygame.mixer.music.play()
                send({"type": "playing"})

                while pygame.mixer.music.get_busy():
                    if _stop_event.is_set():
                        pygame.mixer.music.stop()
                        break
                    time.sleep(0.03)

            send({"type": "done"})

        except Exception:
            send({"type": "error", "msg": traceback.format_exc()})
        finally:
            if pygame and pygame.mixer.get_init():
                try: pygame.mixer.music.stop()
                except Exception: pass
            try:
                os.remove(tmp)
            except Exception:
                pass


send({"type": "ready"})

_current_thread: threading.Thread | None = None

for raw_line in sys.stdin:
    raw_line = raw_line.strip()
    if not raw_line:
        continue
    try:
        msg = json.loads(raw_line)
    except Exception:
        continue

    cmd = msg.get("cmd")

    if cmd == "play":
        # Stop any running playback first
        _stop_event.set()
        if _current_thread and _current_thread.is_alive():
            _current_thread.join(timeout=1.0)
        _current_thread = threading.Thread(
            target=_play_thread, args=(msg.get("text", ""),), daemon=True
        )
        _current_thread.start()

    elif cmd == "stop":
        _stop_event.set()
        pygame.mixer.music.stop()
        send({"type": "stopped"})

    elif cmd == "quit":
        _stop_event.set()
        break

pygame.mixer.quit()
