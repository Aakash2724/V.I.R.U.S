# final_patch.py — THE DEFINITIVE V.I.R.U.S. PRODUCTION PATCH
# Replaces the static app map + broken intent handler with a full dynamic
# app discovery engine that can open ANY installed app on Windows.

import os, re, sys, glob, traceback

content = open("virus_server.py", "r", encoding="utf-8").read()

# ────────────────────────────────────────────────────────────────────────────
# PART 1 — Replace URL_MAP + WIN_APP_MAP with comprehensive versions
# ────────────────────────────────────────────────────────────────────────────

OLD_MAPS_START = "# ─── URL & APP MAPPINGS ──────────────────────────────────────────────────\nURL_MAP = {"
OLD_MAPS_END   = "# ─── TOOL DEFINITIONS ──────────────────────────────────────────────────"

if OLD_MAPS_START not in content:
    print("ERROR: URL_MAP section not found"); sys.exit(1)

maps_start = content.find(OLD_MAPS_START)
maps_end   = content.find(OLD_MAPS_END)

NEW_MAPS = r'''# ─── URL & APP MAPS (web services always open in browser) ───────────────────
URL_MAP = {
    # Social / streaming
    "youtube":      "https://www.youtube.com",
    "instagram":    "https://www.instagram.com",
    "facebook":     "https://www.facebook.com",
    "fb":           "https://www.facebook.com",
    "twitter":      "https://www.twitter.com",
    "x":            "https://www.x.com",
    "reddit":       "https://www.reddit.com",
    "pinterest":    "https://www.pinterest.com",
    "twitch":       "https://www.twitch.tv",
    "tiktok":       "https://www.tiktok.com",
    "snapchat":     "https://web.snapchat.com",
    "linkedin":     "https://www.linkedin.com",
    # Messaging / comms
    "whatsapp":     "https://web.whatsapp.com",
    "telegram":     "https://web.telegram.org",
    "discord":      "https://discord.com/app",
    "slack":        "https://app.slack.com",
    "skype":        "https://web.skype.com",
    "zoom":         "https://zoom.us",
    "teams":        "https://teams.microsoft.com",
    "microsoft teams": "https://teams.microsoft.com",
    # Google suite
    "google":       "https://www.google.com",
    "gmail":        "https://mail.google.com",
    "google drive": "https://drive.google.com",
    "drive":        "https://drive.google.com",
    "docs":         "https://docs.google.com",
    "google docs":  "https://docs.google.com",
    "sheets":       "https://sheets.google.com",
    "google sheets":"https://sheets.google.com",
    "slides":       "https://slides.google.com",
    "google slides":"https://slides.google.com",
    "maps":         "https://maps.google.com",
    "google maps":  "https://maps.google.com",
    "google photos":"https://photos.google.com",
    "photos":       "https://photos.google.com",
    "google translate": "https://translate.google.com",
    "translate":    "https://translate.google.com",
    "google meet":  "https://meet.google.com",
    "meet":         "https://meet.google.com",
    "google calendar": "https://calendar.google.com",
    "calendar":     "https://calendar.google.com",
    "google classroom": "https://classroom.google.com",
    "classroom":    "https://classroom.google.com",
    # Productivity / cloud
    "github":       "https://www.github.com",
    "notion":       "https://www.notion.so",
    "trello":       "https://www.trello.com",
    "figma":        "https://www.figma.com",
    "canva":        "https://www.canva.com",
    "codepen":      "https://codepen.io",
    "replit":       "https://replit.com",
    "stackoverflow": "https://stackoverflow.com",
    "stack overflow": "https://stackoverflow.com",
    "medium":       "https://medium.com",
    "chatgpt":      "https://chat.openai.com",
    "openai":       "https://chat.openai.com",
    "claude":       "https://claude.ai",
    "gemini":       "https://gemini.google.com",
    "perplexity":   "https://www.perplexity.ai",
    # Shopping / services
    "amazon":       "https://www.amazon.in",
    "flipkart":     "https://www.flipkart.com",
    "netflix":      "https://www.netflix.com",
    "hotstar":      "https://www.hotstar.com",
    "disney":       "https://www.hotstar.com",
    "prime":        "https://www.primevideo.com",
    "prime video":  "https://www.primevideo.com",
    "spotify":      "https://open.spotify.com",
    "apple music":  "https://music.apple.com",
    "soundcloud":   "https://soundcloud.com",
    # Dev / tools
    "vercel":       "https://vercel.com",
    "netlify":      "https://netlify.com",
    "railway":      "https://railway.app",
    "jira":         "https://id.atlassian.com",
    "confluence":   "https://www.atlassian.com/software/confluence",
    "postman":      "https://www.postman.com",
    # Finance
    "paytm":        "https://paytm.com",
    "gpay":         "https://pay.google.com",
    "phonepe":      "https://www.phonepe.com",
}

# Classic/native desktop apps — used ONLY if NOT in URL_MAP
WIN_APP_MAP = {
    # System tools
    "notepad":              "notepad.exe",
    "notepad++":            "notepad++.exe",
    "paint":                "mspaint.exe",
    "calculator":           "calc.exe",
    "calc":                 "calc.exe",
    "task manager":         "taskmgr.exe",
    "file explorer":        "explorer.exe",
    "explorer":             "explorer.exe",
    "cmd":                  "cmd.exe",
    "command prompt":       "cmd.exe",
    "powershell":           "powershell.exe",
    "terminal":             "wt.exe",
    "windows terminal":     "wt.exe",
    "control panel":        "control.exe",
    "settings":             "ms-settings:",
    "device manager":       "devmgmt.msc",
    "registry":             "regedit.exe",
    "disk management":      "diskmgmt.msc",
    "snipping tool":        "snippingtool.exe",
    "snip":                 "snippingtool.exe",
    "magnifier":            "magnify.exe",
    "on-screen keyboard":   "osk.exe",
    "character map":        "charmap.exe",
    # Browsers
    "chrome":               "chrome",
    "google chrome":        "chrome",
    "firefox":              "firefox",
    "mozilla firefox":      "firefox",
    "edge":                 "msedge",
    "microsoft edge":       "msedge",
    "brave":                "brave",
    "opera":                "opera",
    # Microsoft Office
    "word":                 "WINWORD.EXE",
    "microsoft word":       "WINWORD.EXE",
    "excel":                "EXCEL.EXE",
    "microsoft excel":      "EXCEL.EXE",
    "powerpoint":           "POWERPNT.EXE",
    "microsoft powerpoint": "POWERPNT.EXE",
    "outlook":              "OUTLOOK.EXE",
    "microsoft outlook":    "OUTLOOK.EXE",
    "onenote":              "ONENOTE.EXE",
    "access":               "MSACCESS.EXE",
    "publisher":            "MSPUB.EXE",
    "visio":                "VISIO.EXE",
    # Development
    "vs code":              "code",
    "vscode":               "code",
    "visual studio code":   "code",
    "visual studio":        "devenv.exe",
    "android studio":       "studio64.exe",
    "pycharm":              "pycharm64.exe",
    "intellij":             "idea64.exe",
    "webstorm":             "webstorm64.exe",
    "sublime":              "sublime_text.exe",
    "sublime text":         "sublime_text.exe",
    "atom":                 "atom.exe",
    "vim":                  "vim.exe",
    "git bash":             "sh.exe",
    "github desktop":       "GitHubDesktop.exe",
    "sourcetree":           "SourceTree.exe",
    "mongodb compass":      "MongoDBCompass.exe",
    "mysql workbench":      "MySQLWorkbench.exe",
    "dbeaver":              "dbeaver.exe",
    "insomnia":             "Insomnia.exe",
    "docker":               "Docker Desktop.exe",
    "wamp":                 "wampmanager.exe",
    "xampp":                "xampp-control.exe",
    # Media & entertainment
    "vlc":                  "vlc",
    "vlc media player":     "vlc",
    "spotify app":          "Spotify.exe",
    "itunes":               "iTunes.exe",
    "windows media player": "wmplayer.exe",
    "groovie":              "music.ui.exe",
    "movies":               "Video.UI.exe",
    "steam":                "steam",
    "epic games":           "EpicGamesLauncher.exe",
    "epic":                 "EpicGamesLauncher.exe",
    "xbox":                 "GamingServices.exe",
    "obs":                  "obs64.exe",
    "obs studio":           "obs64.exe",
    "audacity":             "audacity.exe",
    "handbrake":            "HandBrake.exe",
    "winamp":               "winamp.exe",
    # Adobe
    "photoshop":            "Photoshop.exe",
    "adobe photoshop":      "Photoshop.exe",
    "illustrator":          "Illustrator.exe",
    "adobe illustrator":    "Illustrator.exe",
    "premiere":             "Adobe Premiere Pro.exe",
    "premiere pro":         "Adobe Premiere Pro.exe",
    "after effects":        "AfterFX.exe",
    "adobe after effects":  "AfterFX.exe",
    "lightroom":            "lightroom.exe",
    "acrobat":              "Acrobat.exe",
    "adobe acrobat":        "Acrobat.exe",
    # Communication (native clients)
    "discord app":          "Discord.exe",
    "telegram app":         "Telegram.exe",
    "whatsapp app":         "WhatsApp.exe",
    "skype app":            "Skype.exe",
    "zoom app":             "Zoom.exe",
    "capcut":               "CapCut.exe",
    "cap cut":              "CapCut.exe",
    # Other popular
    "winrar":               "WinRAR.exe",
    "7zip":                 "7zFM.exe",
    "7-zip":                "7zFM.exe",
    "ccleaner":             "CCleaner64.exe",
    "malwarebytes":         "mbam.exe",
    "avast":                "AvastUI.exe",
    "anydesk":              "AnyDesk.exe",
    "teamviewer":           "TeamViewer.exe",
    "nordvpn":              "NordVPN.exe",
    "winscp":               "WinSCP.exe",
    "putty":                "putty.exe",
    "filezilla":            "filezilla.exe",
    "qbittorrent":          "qbittorrent.exe",
    "uTorrent":             "uTorrent.exe",
    "blender":              "blender.exe",
    "unity":                "Unity.exe",
    "unreal":               "UE4Editor.exe",
    "minecraft":            "MinecraftLauncher.exe",
    "valorant":             "VALORANT.exe",
    "lol":                  "LeagueClient.exe",
    "league of legends":    "LeagueClient.exe",
    "roblox":               "RobloxPlayerLauncher.exe",
    "fortnite":             "FortniteClient-Win64-Shipping.exe",
}

'''

content = content[:maps_start] + NEW_MAPS + content[maps_end:]
print("Maps replaced")

# ────────────────────────────────────────────────────────────────────────────
# PART 2 — Replace the LLM REPLY section with the final production engine
# ────────────────────────────────────────────────────────────────────────────

OLD_LLM_START = "\n# --- LLM REPLY ---"
OLD_LLM_END   = "\ndef _stream_to_tts("

if OLD_LLM_START not in content:
    print("ERROR: LLM REPLY section not found"); sys.exit(1)

llm_start = content.find(OLD_LLM_START)
llm_end   = content.find(OLD_LLM_END)

NEW_LLM = r'''
# ════════════════════════════════════════════════════════════════════════════
# LLM REPLY  — Dynamic App Engine + Intent Detection
# ════════════════════════════════════════════════════════════════════════════

import glob as _glob

# ── App cache: built once from Start Menu at first use ───────────────────────
_app_cache:       dict[str, str]  = {}   # lowercase_name -> launch_path
_app_cache_ready: bool            = False
_app_cache_lock:  threading.Lock  = threading.Lock()

# Track last opened browser tabs for "close them" command
_last_opened_browser: list[str]    = []
_session_last_active: float         = 0.0


def _build_app_cache():
    """Scan Windows Start Menu to index every installed app shortcut."""
    global _app_cache, _app_cache_ready
    with _app_cache_lock:
        if _app_cache_ready:
            return
        cache: dict[str, str] = {}
        sm_dirs = [
            os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
            os.path.expandvars(r"%PROGRAMDATA%\Microsoft\Windows\Start Menu\Programs"),
        ]
        vendor_prefixes = {
            "microsoft", "adobe", "google", "apple", "amazon", "meta", "epic",
            "valve", "nvidia", "intel", "razer", "logitech", "asus", "hp",
        }
        for sm_dir in sm_dirs:
            if not os.path.isdir(sm_dir):
                continue
            for lnk in _glob.glob(os.path.join(sm_dir, "**", "*.lnk"), recursive=True):
                raw  = os.path.splitext(os.path.basename(lnk))[0]
                name = raw.lower()
                cache[name] = lnk
                # Strip vendor prefix ("microsoft edge" -> "edge")
                parts = name.split()
                if parts and parts[0] in vendor_prefixes and len(parts) > 1:
                    cache[" ".join(parts[1:])] = lnk
                # Strip parenthetical suffixes ("firefox (64-bit)" -> "firefox")
                clean = re.sub(r"\s*\(.*?\)\s*$", "", name).strip()
                if clean and clean != name:
                    cache[clean] = lnk
                # Strip version numbers ("python 3.11" -> "python")
                nover = re.sub(r"\s+\d+[\.\d]*$", "", name).strip()
                if nover and nover != name:
                    cache[nover] = lnk

        _app_cache     = cache
        _app_cache_ready = True
        log.info(f"[APP-CACHE] Indexed {len(cache)} Start Menu entries")


def _find_app_path(name: str) -> str | None:
    """Fuzzy-find an app path from the Start Menu cache."""
    _build_app_cache()
    n = name.lower().strip()

    # 1. Exact match
    if n in _app_cache:
        return _app_cache[n]

    # 2. Query is substring of key (e.g. "chrome" in "google chrome")
    best, best_len = None, float("inf")
    for key, path in _app_cache.items():
        if n in key and len(key) < best_len:
            best, best_len = path, len(key)
    if best:
        return best

    # 3. Key is substring of query (e.g. "visual studio" in "visual studio 2022")
    best, best_len = None, 0
    for key, path in _app_cache.items():
        if key in n and len(key) > best_len and len(key) >= 4:
            best, best_len = path, len(key)
    if best:
        return best

    return None


def _open_single(app_name: str) -> bool:
    """Open one app or website. Strategy: URL → WIN_APP_MAP → Start Menu → shell."""
    name = app_name.lower().strip()

    # 1. Known web service → browser tab (always reliable)
    url = URL_MAP.get(name)
    if url:
        webbrowser.open_new_tab(url)
        return True

    # 2. Known native desktop app → direct executable
    cmd = WIN_APP_MAP.get(name)
    if cmd and not cmd.endswith(":") and not cmd.endswith("\\"):
        try:
            subprocess.Popen(cmd, shell=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception as e:
            log.warning(f"[OPEN] WIN_APP_MAP exec failed {name!r}: {e}")

    # 3. Start Menu shortcut (covers 99% of installed apps)
    path = _find_app_path(name)
    if path:
        try:
            os.startfile(path)
            log.info(f"[OPEN] Start Menu: {path}")
            return True
        except Exception:
            try:
                subprocess.Popen(f'start "" "{path}"', shell=True)
                return True
            except Exception as e:
                log.warning(f"[OPEN] shortcut failed {path}: {e}")

    # 4. Try Windows shell "start" (works for UWP + registered names)
    try:
        subprocess.Popen(f'start "" "{name}"', shell=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        log.info(f"[OPEN] shell start: {name!r}")
        return True
    except Exception:
        pass

    return False


def _close_single(app_name: str) -> bool:
    """Kill a running app by name — scans tasklist for fuzzy match."""
    name = app_name.lower().strip()

    # Known process name overrides
    PROC_OVERRIDES = {
        "chrome":           "chrome.exe",
        "google chrome":    "chrome.exe",
        "firefox":          "firefox.exe",
        "edge":             "msedge.exe",
        "microsoft edge":   "msedge.exe",
        "explorer":         "explorer.exe",
        "file explorer":    "explorer.exe",
        "calculator":       "CalculatorApp.exe",
        "calc":             "CalculatorApp.exe",
        "notepad":          "notepad.exe",
        "word":             "WINWORD.EXE",
        "excel":            "EXCEL.EXE",
        "powerpoint":       "POWERPNT.EXE",
        "spotify":          "Spotify.exe",
        "discord":          "Discord.exe",
        "teams":            "Teams.exe",
        "zoom":             "Zoom.exe",
        "obs":              "obs64.exe",
        "vlc":              "vlc.exe",
        "steam":            "Steam.exe",
        "vs code":          "Code.exe",
        "vscode":           "Code.exe",
        "visual studio code": "Code.exe",
        "capcut":           "CapCut.exe",
    }

    proc = PROC_OVERRIDES.get(name)

    if not proc:
        # Dynamic scan: find best matching process from tasklist
        try:
            out = subprocess.check_output(
                ["tasklist", "/FO", "CSV", "/NH"], timeout=4, text=True
            )
            best_proc, best_score = None, 0
            for line in out.splitlines():
                cols = line.strip().strip('"').split('","')
                if not cols:
                    continue
                pname = cols[0].lower()
                pbare = pname.replace(".exe", "")
                # Score: exact > ends-with > contains
                if pbare == name:
                    best_proc, best_score = cols[0], 3; break
                elif pbare.endswith(name) and best_score < 2:
                    best_proc, best_score = cols[0], 2
                elif name in pbare and best_score < 1:
                    best_proc, best_score = cols[0], 1
            proc = best_proc
        except Exception as e:
            log.warning(f"[CLOSE] tasklist scan failed: {e}")

    if proc:
        try:
            subprocess.Popen(
                f'taskkill /F /IM "{proc}" /T', shell=True,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            log.info(f"[CLOSE] killed: {proc}")
            return True
        except Exception as e:
            log.warning(f"[CLOSE] taskkill failed {proc}: {e}")

    # For browser-based apps, close the active tab
    if name in URL_MAP:
        try:
            import pyautogui
            pyautogui.hotkey("ctrl", "w")
            return True
        except Exception:
            pass

    return False


def _format_names(lst: list) -> str:
    """['a','b','c'] -> 'A, B and C'"""
    titled = [a.title() for a in lst]
    if len(titled) == 1:  return titled[0]
    if len(titled) == 2:  return f"{titled[0]} and {titled[1]}"
    return ", ".join(titled[:-1]) + f" and {titled[-1]}"


def _parse_app_list(raw: str) -> list[str]:
    """Parse 'Instagram YouTube and Facebook' -> ['instagram', 'youtube', 'facebook'].
    Handles commas, 'and', '&', or plain whitespace between app names."""
    # Strip noise words
    raw = re.sub(
        r"\b(?:both|all|the|please|simultaneously|at\s+once|as\s+well|too|also|me|my)\b",
        " ", raw, flags=re.IGNORECASE
    ).strip()

    # Step 1: split on commas and 'and' / '&'
    parts = re.split(r",\s*|\s+and\s+|\s*&\s*", raw, flags=re.IGNORECASE)
    tokens = [p.strip().lower().rstrip(".,!?") for p in parts if p.strip()]

    if not tokens:
        return []

    # Step 2: for each token that isn't a known app, try splitting by whitespace
    _known = set(URL_MAP.keys()) | set(WIN_APP_MAP.keys())
    result: list[str] = []
    for token in tokens:
        if token in _known:
            result.append(token)
            continue
        # Try word-by-word splitting
        words = token.split()
        i, found = 0, False
        while i < len(words):
            # Try two-word combo first
            if i + 1 < len(words):
                two = f"{words[i]} {words[i+1]}"
                if two in _known:
                    result.append(two); i += 2; found = True; continue
            # Single word
            if words[i] in _known:
                result.append(words[i]); i += 1; found = True
            else:
                # Not in static maps — keep as-is for dynamic lookup
                result.append(words[i]); i += 1; found = True
        if not found:
            result.append(token)
    return list(dict.fromkeys(result))   # deduplicate preserving order


def _detect_and_execute_intent(text: str) -> str | None:
    """Parse user intent and execute locally. Returns spoken reply or None."""
    global _last_opened_browser, _session_last_active
    t = text.lower().strip()

    # ── OPEN command ─────────────────────────────────────────────────────────
    open_match = re.search(
        r"(?:open|launch|start|pull\s+up|bring\s+up|load|run)\s+"
        r"(.+?)(?:\s+(?:in|on|with|for|using)\s+.*)?[.!?]?$",
        t, re.IGNORECASE
    )
    if open_match:
        raw  = open_match.group(1).strip().rstrip(".,!?")
        apps = _parse_app_list(raw)
        if not apps:
            return None

        opened_browser, opened_native, failed = [], [], []

        for app in apps:
            in_url = app in URL_MAP
            ok = _open_single(app)
            if ok:
                (opened_browser if in_url else opened_native).append(app)
            else:
                failed.append(app)

        all_opened = opened_browser + opened_native
        if not all_opened:
            return None   # let LLM handle (might not be an app open request)

        if opened_browser:
            _last_opened_browser = opened_browser[:]
        _session_last_active = time.time()

        phrases = [
            f"On it, sir. Launching {_format_names(all_opened)} right now.",
            f"Opening {_format_names(all_opened)} for you, sir.",
            f"{_format_names(all_opened)} coming right up, sir.",
            f"Done. {_format_names(all_opened)} should be up in a moment, sir.",
            f"Getting {_format_names(all_opened)} open for you now, sir.",
            f"Already on it, sir. {_format_names(all_opened)} loading now.",
        ]
        msg = random.choice(phrases)
        if failed:
            msg += f" Couldn't track down {_format_names(failed)} though, sir."
        return msg

    # ── CLOSE command ─────────────────────────────────────────────────────────
    close_match = re.search(
        r"(?:close|shut|exit|quit|kill|terminate)\s+(.+?)[.!?]?$",
        t, re.IGNORECASE
    )
    if close_match:
        raw = close_match.group(1).strip().rstrip(".,!?")

        if re.search(r"\b(all|them|everything|these)\b", raw):
            apps_to_close = _last_opened_browser[:] if _last_opened_browser else []
        else:
            apps_to_close = _parse_app_list(raw)

        if not apps_to_close:
            # Fallback: "close N tabs"
            if re.search(r"\d+\s*tabs?|tab", raw):
                count_m = re.search(r"(\d+)", raw)
                count   = int(count_m.group(1)) if count_m else 1
                try:
                    import pyautogui
                    for _ in range(min(count, 20)):
                        pyautogui.hotkey("ctrl", "w"); time.sleep(0.25)
                    return f"Closed {count} tab{'s' if count != 1 else ''}, sir."
                except Exception as e:
                    return f"Couldn't close tabs: {e}"
            return None

        closed, errors = [], []
        browser_apps = [a for a in apps_to_close if a in URL_MAP]
        other_apps   = [a for a in apps_to_close if a not in URL_MAP]

        # Close browser tabs
        if browser_apps:
            try:
                import pyautogui
                for _ in range(len(browser_apps)):
                    pyautogui.hotkey("ctrl", "w"); time.sleep(0.25)
                closed.extend(browser_apps)
            except ImportError:
                errors.extend(browser_apps)

        # Kill native apps
        for app in other_apps:
            ok = _close_single(app)
            (closed if ok else errors).append(app)

        _last_opened_browser.clear()

        if closed:
            phrases = [
                f"Closed {_format_names(closed)}, sir.",
                f"Done — {_format_names(closed)} shut down, sir.",
                f"All wrapped up. {_format_names(closed)} is gone, sir.",
                f"{_format_names(closed)} closed. Anything else, sir?",
                f"Took care of it — {_format_names(closed)} is closed, sir.",
            ]
            msg = random.choice(phrases)
            if errors:
                msg += f" Couldn't get {_format_names(errors)} to close, sir."
            return msg
        return None

    return None   # no intent matched — let the LLM handle it

'''

content = content[:llm_start] + NEW_LLM + content[llm_end:]
print("LLM / intent section replaced")

# PART 3 — Remove the old _session_last_active and _last_opened_browser duplicates
# These are now defined inside the NEW_LLM block above
old_dup = (
    "_last_opened_browser: list[str] = []\n"
    "_session_last_active: float      = 0.0   # timestamp of last replied-to utterance\n"
)
if old_dup in content:
    content = content.replace(old_dup, "", 1)
    print("Removed duplicate globals")

open("virus_server.py", "w", encoding="utf-8").write(content)
print(f"\nFinal patch done. Lines: {content.count(chr(10))}")
