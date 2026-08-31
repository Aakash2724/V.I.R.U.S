"""
patch_bargein_v2.py
===================
Rewrites _barge_in_transcribe and _barge_in_monitor for fast, reliable barge-in:
- Uses LOCAL Whisper (no network, ~300ms for short clips) instead of Groq API
- Uses time-based silence detection instead of consecutive_voice decrement
  (avoids the 1s+ extra wait to drain the counter)
- Anti-feedback heuristic: only trigger if transcription is SHORT (user saying
  "virus" = 1 word, TTS feedback = long sentence that happens to contain "VIRUS")
- Lowers VAD threshold to 0.65 so user voice registers even over speaker output
"""

OLD_SECTION = '''BARGE_IN_CHUNKS   = 5      # consecutive VAD speech chunks before triggering (~160 ms)
BARGE_IN_VAD_PROB = 0.80   # high threshold to ignore ambient noise / TV / fan etc.


def _trigger_barge_in():'''

NEW_SECTION = '''BARGE_IN_VAD_PROB  = 0.65   # lowered so user voice registers even during TTS playback
BARGE_IN_SILENCE   = 0.30   # seconds of silence that mark end of utterance
BARGE_IN_MIN_DUR   = 0.35   # minimum speech duration to bother transcribing (seconds)
BARGE_IN_MAX_DUR   = 2.50   # collect at most this many seconds before forcing transcribe
BARGE_IN_MAX_WORDS = 8      # anti-feedback: TTS says long sentences; user says "virus" (1 word)


def _trigger_barge_in():'''

NEW_TRANSCRIBE = '''
def _barge_in_transcribe(audio: "np.ndarray"):
    """Transcribe barge-in clip. Trigger stop ONLY if 'virus' is found in a
    short utterance (anti-feedback: TTS saying 'I am VIRUS your assistant' = many words,
    user interrupting with just 'virus' = 1-3 words)."""
    try:
        text = ""

        # Local Whisper — fast, no network latency (~0.2-0.4s for short clips)
        try:
            model = get_whisper()
            segs, _ = model.transcribe(
                audio, beam_size=1, language="en",
                initial_prompt="Virus", vad_filter=False
            )
            text = " ".join(s.text.strip() for s in segs).strip().lower()
            log.info(f"[BARGE-IN] heard: {text!r}")
        except Exception as e:
            log.warning(f"[BARGE-IN] local whisper failed: {e}")

        if not text:
            return

        wake_words = ["virus", "v.i.r.u.s", "v i r u s"]
        has_wake   = any(w in text for w in wake_words)
        word_count = len(text.split())

        # Anti-feedback: if transcription is long, it's likely the TTS output
        # being picked up by the mic (e.g. "My name is VIRUS sir I am ready...")
        if has_wake and word_count <= BARGE_IN_MAX_WORDS:
            if is_playing_audio or is_llm_generating:
                log.info(f"[BARGE-IN] wake word in {word_count} words -> stopping")
                _trigger_barge_in()
        elif has_wake:
            log.info(f"[BARGE-IN] 'virus' found but {word_count} words -> likely TTS feedback, ignoring")

    except Exception:
        log.error(f"[_barge_in_transcribe] error:\\n{traceback.format_exc()}")

'''

NEW_MONITOR = '''
def _barge_in_monitor():
    """Monitor real mic audio during TTS playback.
    Uses time-based silence detection (much faster than counter drain).
    Triggers barge-in only if user says 'virus'."""
    speech_buf  = []
    speaking    = False
    silence_t   = None   # timestamp when silence started

    while True:
        # ── Idle: drain queue and reset ───────────────────────────────────
        if not (is_playing_audio or is_llm_generating):
            speech_buf.clear()
            speaking   = False
            silence_t  = None
            try:
                while True:
                    barge_in_q.get_nowait()
            except queue.Empty:
                pass
            time.sleep(0.05)
            continue

        # ── Get audio chunk ───────────────────────────────────────────────
        try:
            chunk = barge_in_q.get(timeout=0.05)
        except queue.Empty:
            # No chunk → silence
            if speaking and silence_t is None:
                silence_t = time.time()
            if speaking and silence_t and (time.time() - silence_t) >= BARGE_IN_SILENCE:
                # End of utterance
                if speech_buf:
                    audio    = np.concatenate(speech_buf)
                    duration = len(audio) / SAMPLE_RATE
                    if duration >= BARGE_IN_MIN_DUR:
                        audio_copy = audio.copy()
                        threading.Thread(
                            target=_barge_in_transcribe, args=(audio_copy,), daemon=True
                        ).start()
                speech_buf.clear()
                speaking  = False
                silence_t = None
            continue

        if vad_model is None:
            continue

        # ── VAD ───────────────────────────────────────────────────────────
        try:
            tensor = torch.from_numpy(chunk).float()
            with vad_lock:
                with torch.no_grad():
                    prob = vad_model(tensor, SAMPLE_RATE).item()

            if prob >= BARGE_IN_VAD_PROB:
                speaking  = True
                silence_t = None      # reset silence timer on each speech chunk
                speech_buf.append(chunk)

                # Force-transcribe if buffer gets too long
                speech_dur = len(speech_buf) * BLOCK_SIZE / SAMPLE_RATE
                if speech_dur >= BARGE_IN_MAX_DUR:
                    audio = np.concatenate(speech_buf)
                    speech_buf.clear()
                    speaking  = False
                    silence_t = None
                    threading.Thread(
                        target=_barge_in_transcribe, args=(audio.copy(),), daemon=True
                    ).start()
            else:
                if speaking and silence_t is None:
                    silence_t = time.time()

        except Exception:
            log.error(f"[barge_in_monitor] error:\\n{traceback.format_exc()}")

'''

content = open("virus_server.py", "r", encoding="utf-8").read()

# Replace the constants + _trigger_barge_in opening
if OLD_SECTION not in content:
    print("ERROR: OLD_SECTION not found")
    import sys; sys.exit(1)

content = content.replace(OLD_SECTION, NEW_SECTION, 1)

# Replace _barge_in_transcribe
start = content.find("\ndef _barge_in_transcribe(")
end   = content.find("\ndef _barge_in_monitor(")
assert start != -1 and end != -1

content = content[:start] + "\n" + NEW_TRANSCRIBE + content[end:]

# Replace _barge_in_monitor
start = content.find("\ndef _barge_in_monitor(")
end   = content.find("\n# ", content.find("def _barge_in_monitor("))
# Find the audio callback section
end   = content.find("\ndef _audio_cb(")
assert start != -1 and end != -1

content = content[:start] + "\n" + NEW_MONITOR + content[end:]

open("virus_server.py", "w", encoding="utf-8").write(content)
print(f"Patch applied. Lines: {content.count(chr(10))}")
