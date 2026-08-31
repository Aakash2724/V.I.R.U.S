"""patch_tts2.py — replaces _tts_worker with subprocess-IPC version"""
import sys

NEW_TTS = r'''# --- TTS WORKER THREAD ---
def _tts_worker():
    global is_playing_audio, is_llm_generating

    # Launch tts_player.py as a child process.
    # pygame/SDL lives in an isolated process -> no conflict with PortAudio mic.
    tts_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tts_player.py")
    player_proc = None

    def _start_player():
        p = subprocess.Popen(
            [sys.executable, tts_script],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        ready_line = p.stdout.readline().strip()
        log.info(f"[TTS-proc] started, got: {ready_line}")
        return p

    def _send(p, msg):
        try:
            p.stdin.write(json.dumps(msg) + "\n")
            p.stdin.flush()
        except Exception as e:
            log.warning(f"[TTS-proc] send error: {e}")

    def _play_text(p, text):
        """Send text to player, wait for done/stopped. Returns True if barged-in."""
        _send(p, {"cmd": "play", "text": text})
        while True:
            if barge_in_event.is_set():
                _send(p, {"cmd": "stop"})
                return True
            try:
                line = p.stdout.readline()
                if not line:
                    break
                msg = json.loads(line.strip())
                t = msg.get("type")
                if t in ("done", "stopped"):
                    return t == "stopped"
                if t == "error":
                    log.error(f"[TTS-proc] {msg.get('msg')}")
                    return False
            except Exception:
                time.sleep(0.02)
        return False

    try:
        player_proc = _start_player()
    except Exception:
        log.error(f"[TTS] Failed to start tts_player.py:\n{traceback.format_exc()}")
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
                log.warning("[TTS] player process died -- restarting")
                player_proc = _start_player()

            emit({"type": "status", "value": "speaking"})
            emit({"type": "reply_chunk", "value": safe_text + " "})

            barged = _play_text(player_proc, safe_text)
            barge_in_event.clear()

            if barged:
                log.info("[TTS] barge-in triggered.")

        except Exception:
            log.error(f"[TTS] error:\n{traceback.format_exc()}")
            try:
                player_proc.kill()
            except Exception:
                pass
            try:
                player_proc = _start_player()
            except Exception:
                log.error("[TTS] could not restart player")
        finally:
            if tts_queue.empty() and not is_llm_generating:
                time.sleep(0.3)
                is_playing_audio = False
                emit({"type": "status", "value": "idle"})

    try:
        _send(player_proc, {"cmd": "quit"})
        player_proc.wait(timeout=3)
    except Exception:
        try:
            player_proc.kill()
        except Exception:
            pass

'''

content = open('virus_server.py', 'r', encoding='utf-8').read()

start_marker = content.find('def _tts_worker():')
end_marker   = content.find('@app.on_event')

# Walk back to grab the comment header line above def
section_start = content.rfind('\n', 0, start_marker) + 1
prev_line_start = content.rfind('\n', 0, section_start - 1) + 1
if content[prev_line_start:section_start].strip().startswith('#'):
    section_start = prev_line_start

assert start_marker > 0, "def _tts_worker not found"
assert end_marker > 0,   "@app.on_event not found"

new_content = content[:section_start] + NEW_TTS + '\n' + content[end_marker:]

# Ensure sys is imported
if 'import sys' not in new_content.split('\n')[0:5]:
    new_content = new_content.replace(
        'import asyncio, json,',
        'import asyncio, json, sys,',
        1
    )

open('virus_server.py', 'w', encoding='utf-8').write(new_content)
print(f"Patched OK. Total lines: {new_content.count(chr(10))}")
