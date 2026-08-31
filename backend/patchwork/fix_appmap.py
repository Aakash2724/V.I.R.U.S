# fix_appmap.py — Machine-specific fixes: system apps not in Start Menu,
# and ensure Windows built-ins work with correct commands

content = open("virus_server.py", "r", encoding="utf-8").read()

# The system has: Brave, Chrome, VLC, Zoom, VS Code, PyCharm, Android Studio,
# Excel, Word, PowerPoint, OneNote, Outlook, Ollama, Spyder, Git, etc.
# Apps like Calculator, Notepad, Spotify, Discord, WhatsApp, CapCut are NOT
# in the Start Menu (not installed or are UWP apps accessed differently).
# Ensure the WIN_APP_MAP entries for system commands are correct.

# We need to make _open_single fall back to WIN_APP_MAP even for system apps
# The current code does: URL -> WIN_APP_MAP -> Start Menu -> shell start
# For calculator, notepad, etc., shell start should work: `start calc`

# Main fix: ensure system built-ins open via `start <name>` shell fallback when
# not found in Start Menu. Test that `start calc` and `start notepad` work:
# They do! Windows `start` resolves these system app names automatically.

# Also fix: the VLC Start Menu entry is the wrong one (reset preferences).
# We need to add a direct override for VLC.

OLD_VLC = '    "vlc":                  "vlc",\n    "vlc media player":     "vlc",'
NEW_VLC = '    "vlc":                  r"C:\\Program Files\\VideoLAN\\VLC\\vlc.exe",\n    "vlc media player":     r"C:\\Program Files\\VideoLAN\\VLC\\vlc.exe",'

if OLD_VLC in content:
    content = content.replace(OLD_VLC, NEW_VLC, 1)
    print("VLC path fixed")

# Fix Zoom - it's "Zoom Workplace" in Start Menu, WIN_APP_MAP should work
# Fix JioHotstar - add to URL_MAP
OLD_URL_PINTEREST = '    "pinterest":    "https://www.pinterest.com",'
NEW_URL_PINTEREST = (
    '    "pinterest":    "https://www.pinterest.com",\n'
    '    "hotstar":      "https://www.hotstar.com",\n'
    '    "jio hotstar":  "https://www.hotstar.com",\n'
    '    "jiohotstar":   "https://www.hotstar.com",'
)
if OLD_URL_PINTEREST in content and "hotstar" not in content[:content.find(OLD_URL_PINTEREST) + 100]:
    content = content.replace(OLD_URL_PINTEREST, NEW_URL_PINTEREST, 1)
    print("Hotstar URL added")

# Make _open_single use os.startfile for Start Menu matches correctly
# Also: for Windows system apps (calc, notepad, mspaint) that aren't in
# Start Menu, the `start "" "{name}"` fallback should work. But let's add
# explicit `start calc` style commands to WIN_APP_MAP for reliability:
OLD_SYSTEM_APPS = (
    '    "calculator":           "calc.exe",\n'
    '    "calc":                 "calc.exe",'
)
NEW_SYSTEM_APPS = (
    '    "calculator":           "calc",\n'
    '    "calc":                 "calc",'
)
if OLD_SYSTEM_APPS in content:
    content = content.replace(OLD_SYSTEM_APPS, NEW_SYSTEM_APPS, 1)
    print("Calculator command updated to 'calc' (shell-friendly)")

# Paint
OLD_PAINT = '    "paint":                 "mspaint.exe",'
NEW_PAINT = '    "paint":                 "mspaint",'
if OLD_PAINT in content:
    content = content.replace(OLD_PAINT, NEW_PAINT, 1)

# Notepad
OLD_NOTEPAD = '    "notepad":              "notepad.exe",'
NEW_NOTEPAD = '    "notepad":              "notepad",'
if OLD_NOTEPAD in content:
    content = content.replace(OLD_NOTEPAD, NEW_NOTEPAD, 1)

# Fix _open_single: for WIN_APP_MAP commands ending with .exe or just a name,
# use subprocess.Popen([name], shell=True) — works for PATH-registered commands
# The current code already does this. Ensure we handle both .exe and bare names.
print("Checking _open_single logic...")
if '"start "" ' in content:
    print("  shell start fallback present: OK")

open("virus_server.py", "w", encoding="utf-8").write(content)
print(f"Done. Lines: {content.count(chr(10))}")
