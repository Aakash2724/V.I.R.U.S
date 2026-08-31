"""
patch_wakeword.py
=================
1. Adds wake-word gate: only respond if 'virus' is in the transcription.
2. Replaces dumb VAD barge-in with keyword barge-in: collect audio during
   playback, transcribe, trigger stop only if 'virus' is spoken.
"""

WAKE_WORDS = ["virus", "v.i.r.u.s", "v i r u s"]

# ── NEW: _trigger_barge_in stays same, _barge_in_monitor is replaced ────────
NEW_BARGE_IN_SECTION = '''
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


def _barge_in_transcribe(audio: "np.ndarray"):
    """Transcribe captured barge-in audio. If 'virus' is spoken, stop playback."""
    try:
        text = ""
        # Try Groq cloud first (fast)
        if groq_client:
            try:
                import tempfile, wave as _wave
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
                    wf = _wave.open(tf, "w")
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(SAMPLE_RATE)
                    wf.writeframes(np.int16(audio * 32767).tobytes())
                    wf.close()
                    tf_path = tf.name
                with open(tf_path, "rb") as f:
                    result = groq_client.audio.transcriptions.create(
                        model=GROQ_WHISPER_MODEL,
                        file=("barge.wav", f.read(), "audio/wav"),
                        language="en",
                        temperature=0.0,
                    )
                os.unlink(tf_path)
                text = result.text.strip().lower()
            except Exception as e:
                log.warning(f"[BARGE-IN] cloud transcription failed: {e}")

        # Fallback to local Whisper
        if not text:
            try:
                model = get_whisper()
                segs, _ = model.transcribe(audio, beam_size=1, language="en")
                text = " ".join(s.text for s in segs).strip().lower()
            except Exception as e:
                log.warning(f"[BARGE-IN] local transcription failed: {e}")

        log.info(f"[BARGE-IN] heard: {text!r}")

        wake_words = ["virus", "v.i.r.u.s", "v i r u s"]
        if any(w in text for w in wake_words):
            if is_playing_audio or is_llm_generating:
                log.info("[BARGE-IN] Wake word detected mid-response -- stopping.")
                threading.Thread(target=_trigger_barge_in, daemon=True).start()
    except Exception:
        log.error(f"[_barge_in_transcribe] error:\\n{traceback.format_exc()}")


def _barge_in_monitor():
    """Monitor mic audio during TTS playback.
    Collects speech segments and transcribes them; triggers barge-in only
    if the user says 'virus' mid-response. When idle, drains the queue."""
    consecutive_voice = 0
    speech_buf = []
    transcribing = False
    last_chunk_time = 0.0

    while True:
        if not (is_playing_audio or is_llm_generating):
            consecutive_voice = 0
            speech_buf.clear()
            transcribing = False
            try:
                while True:
                    barge_in_q.get_nowait()
            except queue.Empty:
                pass
            time.sleep(0.05)
            continue

        try:
            chunk = barge_in_q.get(timeout=0.1)
        except queue.Empty:
            consecutive_voice = max(0, consecutive_voice - 1)
            # If voice stopped and we have enough audio, transcribe
            if consecutive_voice == 0 and speech_buf and not transcribing:
                audio = np.concatenate(speech_buf)
                duration = len(audio) / SAMPLE_RATE
                if duration >= 0.6:  # min 600ms of speech to transcribe
                    transcribing = True
                    speech_buf_copy = audio
                    speech_buf.clear()
                    threading.Thread(
                        target=lambda a=speech_buf_copy: (_barge_in_transcribe(a), setattr(threading.current_thread(), "_done", True)),
                        daemon=True
                    ).start()
                    transcribing = False
                else:
                    speech_buf.clear()
            continue

        if vad_model is None:
            continue

        try:
            tensor = torch.from_numpy(chunk).float()
            with vad_lock:
                with torch.no_grad():
                    prob = vad_model(tensor, SAMPLE_RATE).item()

            if prob > BARGE_IN_VAD_PROB:
                consecutive_voice += 1
                speech_buf.append(chunk)
            else:
                consecutive_voice = max(0, consecutive_voice - 1)

            # Also transcribe if buffer gets long (user speaking for a while)
            speech_duration = len(speech_buf) * BLOCK_SIZE / SAMPLE_RATE
            if speech_duration >= 2.0 and not transcribing:
                transcribing = True
                audio = np.concatenate(speech_buf)
                speech_buf.clear()
                consecutive_voice = 0
                threading.Thread(
                    target=lambda a=audio: (_barge_in_transcribe(a), None),
                    daemon=True
                ).start()
                transcribing = False

        except Exception:
            log.error(f"[barge_in_monitor] error:\\n{traceback.format_exc()}")

'''

# ── NEW: wake-word gate in _final_flush ─────────────────────────────────────
OLD_FINAL_GATE = '''    if text:
        emit({"type": "transcript", "value": text, "final": True})
        threading.Thread(
            target=lambda t=text: _llm_reply(t),
            daemon=True
        ).start()
    else:
        emit({"type": "status", "value": "idle"})'''

NEW_FINAL_GATE = '''    if text:
        emit({"type": "transcript", "value": text, "final": True})
        # Wake-word gate: only respond if 'virus' is in the transcription
        wake_words = ["virus", "v.i.r.u.s", "v i r u s"]
        if any(w in text.lower() for w in wake_words):
            threading.Thread(
                target=lambda t=text: _llm_reply(t),
                daemon=True
            ).start()
        else:
            log.info(f"[GATE] No wake word in {text!r} -- ignoring.")
            emit({"type": "status", "value": "idle"})
    else:
        emit({"type": "status", "value": "idle"})'''


import sys

content = open("virus_server.py", "r", encoding="utf-8").read()

# Replace the barge-in section
start = content.find("\ndef _trigger_barge_in():")
end   = content.find("\n# ", content.find("def _barge_in_monitor():"))  # find next section comment after _barge_in_monitor
# Actually find the audio callback section
end   = content.find("\ndef _audio_cb(")

if start == -1 or end == -1:
    print(f"ERROR: markers not found. start={start} end={end}")
    sys.exit(1)

print(f"Replacing barge-in section: chars {start} to {end}")
content = content[:start] + "\n" + NEW_BARGE_IN_SECTION + content[end:]

# Replace the final gate
if OLD_FINAL_GATE not in content:
    print("ERROR: OLD_FINAL_GATE not found in file!")
    sys.exit(1)

content = content.replace(OLD_FINAL_GATE, NEW_FINAL_GATE, 1)

open("virus_server.py", "w", encoding="utf-8").write(content)
print(f"Patch applied OK. Total lines: {content.count(chr(10))}")
