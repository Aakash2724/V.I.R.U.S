# patchwork/fix_bargein_final.py
# Replaces the broken Whisper-based barge-in with instant VAD consecutive-frame detection.
# No transcription, no network, no model contention. ~384ms latency max.

content = open("virus_server.py", "r", encoding="utf-8").read()

# Find and replace the entire barge-in section (from the constants to _audio_cb)
start_marker = "\ndef _trigger_barge_in():"
end_marker   = "\ndef _audio_cb("

start = content.find(start_marker)
end   = content.find(end_marker)

if start == -1 or end == -1:
    print(f"ERROR: markers not found. start={start}, end={end}")
    raise SystemExit(1)

NEW_BARGEIN = '''
# ── Barge-in constants ────────────────────────────────────────────────────────
BARGE_IN_VAD_PROB = 0.60   # VAD threshold (0.60 catches user voice, rejects ambient)
BARGE_IN_FRAMES   = 12     # consecutive frames needed to confirm user speech
                           # 12 frames x 32ms = ~384ms  →  fast enough to feel instant


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


def _barge_in_monitor():
    """Instant VAD-based barge-in during TTS/LLM activity.

    No transcription — pure consecutive-frame voice detection.
    Requires BARGE_IN_FRAMES frames (~384 ms) of sustained speech above
    BARGE_IN_VAD_PROB to fire, which is long enough to ignore brief TTS
    mic-feedback spikes but short enough to feel instantaneous to the user.
    """
    consecutive = 0

    while True:
        # ── When idle: drain queue so it never bloats ─────────────────────
        if not (is_playing_audio or is_llm_generating):
            consecutive = 0
            try:
                while True:
                    barge_in_q.get_nowait()
            except queue.Empty:
                pass
            time.sleep(0.04)
            continue

        # ── Get audio chunk ───────────────────────────────────────────────
        try:
            chunk = barge_in_q.get(timeout=0.04)
        except queue.Empty:
            # Silence — decay counter twice as fast as we accumulate
            consecutive = max(0, consecutive - 2)
            continue

        if vad_model is None:
            continue

        # ── VAD check ─────────────────────────────────────────────────────
        try:
            tensor = torch.from_numpy(chunk).float()
            with vad_lock:
                with torch.no_grad():
                    prob = vad_model(tensor, SAMPLE_RATE).item()

            if prob >= BARGE_IN_VAD_PROB:
                consecutive += 1
                if consecutive >= BARGE_IN_FRAMES:
                    if is_playing_audio or is_llm_generating:
                        log.info(
                            f"[BARGE-IN] {consecutive} frames @ VAD={prob:.2f} -- stopping"
                        )
                        consecutive = 0
                        threading.Thread(target=_trigger_barge_in, daemon=True).start()
            else:
                consecutive = max(0, consecutive - 1)

        except Exception:
            log.error(f"[barge_in_monitor] error:\\n{traceback.format_exc()}")

'''

content = content[:start] + NEW_BARGEIN + content[end:]
print(f"Barge-in section replaced ({end - start} chars -> {len(NEW_BARGEIN)} chars)")

open("virus_server.py", "w", encoding="utf-8").write(content)
print(f"Done. Lines: {content.count(chr(10))}")
