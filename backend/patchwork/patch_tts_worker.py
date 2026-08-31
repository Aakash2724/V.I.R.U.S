"""patch_tts_worker.py — rewrites _tts_worker with persistent stdout reader + non-blocking _play_text"""

NEW_TTS_WORKER = '''
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
            p.stdin.write(json.dumps(msg) + "\\n")
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

    try:
        player_proc = _start_player()
    except Exception:
        log.error(f"[TTS] Failed to start tts_player:\\n{traceback.format_exc()}")
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
            log.error(f"[TTS] error:\\n{traceback.format_exc()}")
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

'''

content = open("virus_server.py", "r", encoding="utf-8").read()

start = content.find("\n# --- TTS WORKER THREAD ---")
if start == -1:
    # find by def
    idx = content.find("\ndef _tts_worker():")
    start = content.rfind("\n", 0, idx)

end = content.find("\n@app.on_event")

assert start != -1, "TTS WORKER start not found"
assert end   != -1, "@app.on_event not found"

print(f"Replacing chars {start} to {end}")
new_content = content[:start] + "\n" + NEW_TTS_WORKER + "\n" + content[end:]

open("virus_server.py", "w", encoding="utf-8").write(new_content)
print(f"Done. Lines: {new_content.count(chr(10))}")
