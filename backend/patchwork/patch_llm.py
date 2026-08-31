"""patch_llm.py — replaces the broken Groq tool-call LLM section with a simple streaming reply + local intent handler"""
import re

NEW_STREAM_AND_REPLY = '''
# --- LLM REPLY ---
def _detect_and_execute_intent(text: str) -> str | None:
    """Check user text for app/site open commands. Returns spoken result or None."""
    t = text.lower().strip()

    # "open <app/site>" pattern
    open_match = re.search(r"open\\s+(.+?)(?:\\s+(?:in|on|with)\\s+.+)?$", t)
    if open_match:
        target = open_match.group(1).strip().rstrip(".")
        # Try app map first
        cmd = WIN_APP_MAP.get(target)
        if cmd:
            try:
                if cmd.endswith(":"):
                    subprocess.Popen(f\'start "" "{cmd}"\', shell=True)
                else:
                    subprocess.Popen(cmd, shell=True)
                return f"Opening {target}, sir."
            except Exception as e:
                log.warning(f"[INTENT] app open failed: {e}")
        # Try URL map
        url = URL_MAP.get(target)
        if url:
            webbrowser.open(url)
            return f"Opening {target} in the browser, sir."

    # "close tab(s)"
    if re.search(r"close\\s+(\\d+\\s+)?tabs?", t):
        count_match = re.search(r"(\\d+)", t)
        count = int(count_match.group(1)) if count_match else 1
        try:
            import pyautogui
            for _ in range(min(count, 20)):
                pyautogui.hotkey("ctrl", "w")
                time.sleep(0.3)
            return f"Closed {count} tab{\'s\' if count != 1 else \'\'}, sir."
        except Exception as e:
            return f"Could not close tabs: {e}"

    # "how many files/folders on the desktop"
    if re.search(r"desktop", t) and re.search(r"(how many|files?|folders?|items?)", t):
        result = _execute_tool("get_desktop_info", {"item_type": "all"})
        return result

    return None  # no intent matched — let LLM handle it


def _stream_to_tts(stream) -> str:
    """Consume a streaming Groq response, pushing sentences to TTS queue."""
    full = ""
    buf  = ""
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            full += delta
            buf  += delta
            if any(p in delta for p in [".", "!", "?", "\\n"]):
                if buf.strip():
                    tts_queue.put(buf.strip())
                    buf = ""
    if buf.strip():
        tts_queue.put(buf.strip())
    return full


def _llm_reply(text: str):
    global is_llm_generating
    if not groq_client:
        return
    is_llm_generating = True
    log.info(f"[LLM] processing: {text!r}")

    try:
        # 1. Check for local intent (open app, close tabs, desktop info)
        intent_result = _detect_and_execute_intent(text)
        if intent_result:
            log.info(f"[LLM] intent handled locally: {intent_result!r}")
            tts_queue.put(intent_result)
            conversation_memory.append({"role": "user",      "content": text})
            conversation_memory.append({"role": "assistant", "content": intent_result})
            return

        # 2. Plain streaming LLM call — no tools, no 400 errors
        conversation_memory.append({"role": "user", "content": text})
        messages = [{"role": "system", "content": VIRUS_SYSTEM_PROMPT}] + list(conversation_memory)

        stream = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            stream=True,
            temperature=0.7,
            max_tokens=300,
        )
        full = _stream_to_tts(stream)
        if full.strip():
            conversation_memory.append({"role": "assistant", "content": full})

    except Exception:
        log.error(f"[LLM] crashed:\\n{traceback.format_exc()}")
        tts_queue.put("I encountered an issue, sir. Please try again.")
    finally:
        is_llm_generating = False
        tts_queue.put({"type": "end_reply"})

'''

content = open("virus_server.py", "r", encoding="utf-8").read()

# Find boundaries
start = content.find("\n# --- LLM REPLY ---")
if start == -1:
    # Try to find using the original comment style
    for marker in ["# \u2500\u2500\u2500 LLM REPLY", "# --- LLM REPLY", "def _stream_to_tts"]:
        idx = content.find(marker)
        if idx != -1:
            start = content.rfind("\n", 0, idx)
            break

end = content.find("\n# --- TTS WORKER THREAD ---")
if end == -1:
    end = content.find("\ndef _tts_worker")

assert start != -1, f"Could not find LLM REPLY section start"
assert end   != -1, f"Could not find TTS WORKER section end"

print(f"Replacing chars {start} to {end}")
new_content = content[:start] + NEW_STREAM_AND_REPLY + content[end:]
open("virus_server.py", "w", encoding="utf-8").write(new_content)
print(f"Patch applied. Lines: {new_content.count(chr(10))}")
