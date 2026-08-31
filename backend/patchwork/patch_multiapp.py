"""patch_multiapp.py — rewrites _detect_and_execute_intent with multi-app support"""

NEW_INTENT = '''# --- LLM REPLY ---

# Tracks the last batch of browser-based apps opened (for "close them" command)
_last_opened_browser: list[str] = []


def _parse_app_list(raw: str) -> list[str]:
    """'Instagram, YouTube and Facebook' -> ['instagram', 'youtube', 'facebook']"""
    raw = re.sub(r"\\b(?:both|all|the|please|simultaneously|at once)\\b", "", raw, flags=re.IGNORECASE)
    parts = re.split(r",\\s*|\\s+and\\s+|\\s*&\\s*", raw, flags=re.IGNORECASE)
    return [p.strip().lower().rstrip(".,!") for p in parts if p.strip()]


def _open_single(app_name: str) -> bool:
    """Open one app. Returns True on success."""
    name = app_name.lower().strip()
    # 1. Try desktop app map
    cmd = WIN_APP_MAP.get(name)
    if cmd:
        try:
            if cmd.endswith(":"):
                subprocess.Popen(f\'start "" "{cmd}"\', shell=True)
            else:
                subprocess.Popen(cmd, shell=True)
            return True
        except Exception as e:
            log.warning(f"[INTENT] app open failed for {name!r}: {e}")
    # 2. Try URL map (open in browser tab)
    url = URL_MAP.get(name)
    if url:
        webbrowser.open_new_tab(url)
        return True
    return False


def _detect_and_execute_intent(text: str) -> str | None:
    """Detect open/close commands for one or multiple apps. Returns spoken reply or None."""
    global _last_opened_browser
    t = text.lower().strip()

    # ── OPEN command ────────────────────────────────────────────────────────
    open_match = re.search(
        r"(?:open|launch|start)\\s+(.+?)(?:\\s+(?:in|on|with|for)\\s+.*)?[.!?]?$", t
    )
    if open_match:
        raw   = open_match.group(1).strip().rstrip(".,!?")
        apps  = _parse_app_list(raw)
        if not apps:
            return None

        opened_browser  = []   # browser-based (URL_MAP)
        opened_desktop  = []   # desktop executables
        failed          = []

        for app in apps:
            in_url = app in URL_MAP
            ok     = _open_single(app)
            if ok:
                if in_url:
                    opened_browser.append(app)
                else:
                    opened_desktop.append(app)
            else:
                failed.append(app)

        all_opened = opened_browser + opened_desktop
        if not all_opened:
            return None   # let LLM handle (might not be an open command after all)

        # Remember browser apps so we can close them later
        if opened_browser:
            _last_opened_browser = opened_browser[:]

        def _names(lst):
            if len(lst) == 1:  return lst[0].title()
            if len(lst) == 2:  return f"{lst[0].title()} and {lst[1].title()}"
            return ", ".join(a.title() for a in lst[:-1]) + f", and {lst[-1].title()}"

        msg = f"Opening {_names(all_opened)} simultaneously, sir."
        if failed:
            msg += f" I could not find {_names(failed)}, sir."
        return msg

    # ── CLOSE command ────────────────────────────────────────────────────────
    close_match = re.search(
        r"(?:close|shut|exit|quit)\\s+(.+?)[.!?]?$", t
    )
    if close_match:
        raw = close_match.group(1).strip().rstrip(".,!?")

        # "close all" / "close them" / "close everything"
        if re.search(r"\\b(all|them|everything|these)\\b", raw):
            apps_to_close = _last_opened_browser[:]
        else:
            apps_to_close = _parse_app_list(raw)

        if not apps_to_close:
            # fallback: plain tab count
            if re.search(r"\\d+\\s+tabs?", raw) or raw.strip() in ("tab", "tabs"):
                count_m = re.search(r"(\\d+)", raw)
                count   = int(count_m.group(1)) if count_m else 1
                try:
                    import pyautogui
                    for _ in range(min(count, 20)):
                        pyautogui.hotkey("ctrl", "w")
                        time.sleep(0.25)
                    return f"Closed {count} tab{\'s\' if count != 1 else \'\'}, sir."
                except Exception as e:
                    return f"Could not close tabs: {e}"
            return None

        browser_to_close  = [a for a in apps_to_close if a in URL_MAP]
        desktop_to_close  = [a for a in apps_to_close if a in WIN_APP_MAP and a not in URL_MAP]

        closed  = []
        errors  = []

        # Close browser tabs (Ctrl+W per tab)
        if browser_to_close:
            try:
                import pyautogui
                for _ in range(len(browser_to_close)):
                    pyautogui.hotkey("ctrl", "w")
                    time.sleep(0.25)
                closed.extend(browser_to_close)
            except ImportError:
                errors.extend(browser_to_close)
                log.warning("[INTENT] pyautogui not installed")

        # Kill desktop apps
        for app in desktop_to_close:
            exe = WIN_APP_MAP.get(app, "")
            if not exe or exe.endswith(":"):
                errors.append(app)
                continue
            # Derive the actual executable name
            exe_name = os.path.basename(exe) if os.sep in exe else exe
            if not exe_name.endswith(".exe"):
                exe_name += ".exe"
            try:
                subprocess.Popen(f\'taskkill /F /IM "{exe_name}" /T\', shell=True,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                closed.append(app)
            except Exception as e:
                log.warning(f"[INTENT] taskkill failed for {app}: {e}")
                errors.append(app)

        # Clear tracking
        _last_opened_browser.clear()

        def _names(lst):
            if len(lst) == 1:  return lst[0].title()
            if len(lst) == 2:  return f"{lst[0].title()} and {lst[1].title()}"
            return ", ".join(a.title() for a in lst[:-1]) + f", and {lst[-1].title()}"

        if closed:
            msg = f"Closed {_names(closed)}, sir."
            if errors:
                msg += f" Could not close {_names(errors)}, sir."
            return msg
        return None   # let LLM respond

    # ── Desktop info ─────────────────────────────────────────────────────────
    if re.search(r"desktop", t) and re.search(r"(how many|files?|folders?|items?)", t):
        return _execute_tool("get_desktop_info", {"item_type": "all"})

    return None  # no intent matched — let LLM handle


'''

content = open("virus_server.py", "r", encoding="utf-8").read()

old_start = content.find("\n# --- LLM REPLY ---\n")
old_end   = content.find("\ndef _stream_to_tts(")

assert old_start != -1, "LLM REPLY section not found"
assert old_end   != -1, "_stream_to_tts not found"

print(f"Replacing intent section: chars {old_start} to {old_end}")
content = content[:old_start] + "\n" + NEW_INTENT + content[old_end:]
open("virus_server.py", "w", encoding="utf-8").write(content)
print(f"Done. Lines: {content.count(chr(10))}")
