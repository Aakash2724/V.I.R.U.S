# patch_session_and_parser.py
# Fix 1: Session mode (30s cooldown replaces per-utterance wake word)
# Fix 2: Smart multi-app parser that handles "Instagram YouTube Facebook" without commas

content = open("virus_server.py", "r", encoding="utf-8").read()

# ─── Fix 1: Replace wake word gate with session mode ─────────────────────────
OLD_GATE = (
    '    if text:\n'
    '        emit({"type": "transcript", "value": text, "final": True})\n'
    '        # Wake-word gate: only respond if \'virus\' is in the transcription\n'
    '        wake_words = ["virus", "v.i.r.u.s", "v i r u s"]\n'
    '        if any(w in text.lower() for w in wake_words):\n'
    '            threading.Thread(\n'
    '                target=lambda t=text: _llm_reply(t),\n'
    '                daemon=True\n'
    '            ).start()\n'
    '        else:\n'
    '            log.info(f"[GATE] No wake word in {text!r} -- ignoring.")\n'
    '            emit({"type": "status", "value": "idle"})\n'
    '    else:\n'
    '        emit({"type": "status", "value": "idle"})'
)

NEW_GATE = (
    '    if text:\n'
    '        emit({"type": "transcript", "value": text, "final": True})\n'
    '        # Session gate: first message must contain \'virus\' to activate.\n'
    '        # Once active, stay open for SESSION_TIMEOUT seconds after last reply.\n'
    '        _WAKE_WORDS    = ["virus", "v.i.r.u.s", "v i r u s"]\n'
    '        _SESSION_SECS  = 45.0   # session stays alive 45s after last reply\n'
    '        _now           = time.time()\n'
    '        _has_wake      = any(w in text.lower() for w in _WAKE_WORDS)\n'
    '        _sess_alive    = (_now - _session_last_active) < _SESSION_SECS\n'
    '        if _has_wake or _sess_alive:\n'
    '            threading.Thread(\n'
    '                target=lambda t=text: _llm_reply(t),\n'
    '                daemon=True\n'
    '            ).start()\n'
    '        else:\n'
    '            log.info(f"[GATE] Session expired, no wake word in {text!r} -- ignoring.")\n'
    '            emit({"type": "status", "value": "idle"})\n'
    '    else:\n'
    '        emit({"type": "status", "value": "idle"})'
)

if OLD_GATE not in content:
    print("ERROR: gate not found")
    raise SystemExit(1)
content = content.replace(OLD_GATE, NEW_GATE, 1)
print("Session gate installed")

# ─── Add _session_last_active global near the other globals ───────────────────
OLD_GLOBALS = "_last_opened_browser: list[str] = []"
NEW_GLOBALS = (
    "_last_opened_browser: list[str] = []\n"
    "_session_last_active: float      = 0.0   # timestamp of last replied-to utterance"
)
if OLD_GLOBALS not in content:
    print("ERROR: globals anchor not found")
    raise SystemExit(1)
content = content.replace(OLD_GLOBALS, NEW_GLOBALS, 1)
print("Session global added")

# ─── Update _session_last_active in _llm_reply's finally block ────────────────
OLD_FINALLY = (
    '        is_llm_generating = False\n'
    '        tts_queue.put({"type": "end_reply"})\n'
    '        log.info("[LLM] done")'
)
NEW_FINALLY = (
    '        is_llm_generating = False\n'
    '        tts_queue.put({"type": "end_reply"})\n'
    '        log.info("[LLM] done")\n'
    '        global _session_last_active\n'
    '        _session_last_active = time.time()   # keep session alive after each reply'
)
if OLD_FINALLY not in content:
    print("WARNING: finally block not found, session won't refresh on reply")
else:
    content = content.replace(OLD_FINALLY, NEW_FINALLY, 1)
    print("Session refresh on reply added")

# ─── Fix 2: Smart parser that handles "Instagram YouTube Facebook" ─────────────
OLD_PARSER = (
    'def _parse_app_list(raw: str) -> list[str]:\n'
    '    """\'Instagram, YouTube and Facebook\' -> [\'instagram\', \'youtube\', \'facebook\']"""\n'
    '    raw = re.sub(r"\\b(?:both|all|the|please|simultaneously|at once)\\b", "", raw, flags=re.IGNORECASE)\n'
    '    parts = re.split(r",\\s*|\\s+and\\s+|\\s*&\\s*", raw, flags=re.IGNORECASE)\n'
    '    return [p.strip().lower().rstrip(".,!") for p in parts if p.strip()]'
)

NEW_PARSER = (
    'def _parse_app_list(raw: str) -> list[str]:\n'
    '    """Parse app list from voice. Handles commas, \'and\',\n'
    '    or plain spaces: \'Instagram YouTube Facebook\' -> [\'instagram\',\'youtube\',\'facebook\']\n'
    '    Also handles \'Instagram, YouTube and Facebook\' (mixed).\n'
    '    """\n'
    '    # Strip noise words\n'
    '    raw = re.sub(\n'
    '        r"\\b(?:both|all|the|please|simultaneously|at\\s+once|as\\s+well|too|also)\\b",\n'
    '        "", raw, flags=re.IGNORECASE\n'
    '    ).strip()\n'
    '\n'
    '    # Step 1: split on commas and " and " / " & "\n'
    '    parts = re.split(r",\\s*|\\s+and\\s+|\\s*&\\s*", raw, flags=re.IGNORECASE)\n'
    '    tokens = [p.strip().lower().rstrip(".,!") for p in parts if p.strip()]\n'
    '\n'
    '    # Step 2: for any token that is NOT directly in a known map,\n'
    '    # try to split it further by whitespace (handles "Instagram YouTube")\n'
    '    _known = set(URL_MAP.keys()) | set(WIN_APP_MAP.keys())\n'
    '    result = []\n'
    '    for token in tokens:\n'
    '        if token in _known:\n'
    '            result.append(token)\n'
    '        else:\n'
    '            # Try individual words\n'
    '            words = token.split()\n'
    '            matched_any = False\n'
    '            i = 0\n'
    '            while i < len(words):\n'
    '                # Try two-word combo (e.g. "google docs")\n'
    '                if i + 1 < len(words):\n'
    '                    two = words[i] + " " + words[i + 1]\n'
    '                    if two in _known:\n'
    '                        result.append(two)\n'
    '                        matched_any = True\n'
    '                        i += 2\n'
    '                        continue\n'
    '                # Try single word\n'
    '                if words[i] in _known:\n'
    '                    result.append(words[i])\n'
    '                    matched_any = True\n'
    '                else:\n'
    '                    result.append(words[i])  # keep unknown for LLM feedback\n'
    '                i += 1\n'
    '            if not matched_any and not words:\n'
    '                pass  # empty, skip\n'
    '    return result if result else tokens'
)

if OLD_PARSER not in content:
    print("ERROR: parser not found")
    raise SystemExit(1)
content = content.replace(OLD_PARSER, NEW_PARSER, 1)
print("Smart parser installed")

# ─── Fix 3: Prefer URL_MAP for web apps (instagram:, youtube: URIs are unreliable) ──
OLD_OPEN_SINGLE = (
    'def _open_single(app_name: str) -> bool:\n'
    '    """Open one app. Returns True on success."""\n'
    '    name = app_name.lower().strip()\n'
    '    # 1. Try desktop app map\n'
    '    cmd = WIN_APP_MAP.get(name)\n'
    '    if cmd:\n'
    '        try:\n'
    '            if cmd.endswith(":"):\n'
    '                subprocess.Popen(f\'start "" "{cmd}"\', shell=True)\n'
    '            else:\n'
    '                subprocess.Popen(cmd, shell=True)\n'
    '            return True\n'
    '        except Exception as e:\n'
    '            log.warning(f"[INTENT] app open failed for {name!r}: {e}")\n'
    '    # 2. Try URL map (open in browser tab)\n'
    '    url = URL_MAP.get(name)\n'
    '    if url:\n'
    '        webbrowser.open_new_tab(url)\n'
    '        return True\n'
    '    return False'
)

NEW_OPEN_SINGLE = (
    'def _open_single(app_name: str) -> bool:\n'
    '    """Open one app. Returns True on success.\n'
    '    For web services (in URL_MAP), always prefer the browser URL.\n'
    '    For native desktop apps (in WIN_APP_MAP only), use the app launch command.\n'
    '    """\n'
    '    name = app_name.lower().strip()\n'
    '\n'
    '    # 1. If it is a web service, open the browser URL directly\n'
    '    url = URL_MAP.get(name)\n'
    '    if url:\n'
    '        webbrowser.open_new_tab(url)\n'
    '        return True\n'
    '\n'
    '    # 2. Try native desktop app (only if NOT a web service)\n'
    '    cmd = WIN_APP_MAP.get(name)\n'
    '    if cmd and not cmd.endswith(":"):\n'
    '        try:\n'
    '            subprocess.Popen(cmd, shell=True)\n'
    '            return True\n'
    '        except Exception as e:\n'
    '            log.warning(f"[INTENT] app open failed for {name!r}: {e}")\n'
    '\n'
    '    # 3. Fallback: try as a URL protocol\n'
    '    if cmd and cmd.endswith(":"):\n'
    '        try:\n'
    '            subprocess.Popen(f\'start "" "{cmd}"\', shell=True)\n'
    '            return True\n'
    '        except Exception as e:\n'
    '            log.warning(f"[INTENT] URI open failed for {name!r}: {e}")\n'
    '\n'
    '    return False'
)

if OLD_OPEN_SINGLE not in content:
    print("ERROR: _open_single not found")
    raise SystemExit(1)
content = content.replace(OLD_OPEN_SINGLE, NEW_OPEN_SINGLE, 1)
print("_open_single fixed (web-first)")

open("virus_server.py", "w", encoding="utf-8").write(content)
print(f"\nAll patches applied. Lines: {content.count(chr(10))}")
