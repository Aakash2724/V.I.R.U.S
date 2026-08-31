import glob, os, re
cache = {}
for sm_dir in [
    os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
    os.path.expandvars(r"%PROGRAMDATA%\Microsoft\Windows\Start Menu\Programs"),
]:
    if os.path.isdir(sm_dir):
        for lnk in glob.glob(os.path.join(sm_dir, "**", "*.lnk"), recursive=True):
            name = os.path.splitext(os.path.basename(lnk))[0].lower()
            cache[name] = lnk

print(f"Start Menu apps indexed: {len(cache)}\nSample:")
for k in sorted(cache.keys())[:15]:
    print(f"  {repr(k)}")

print("\nApp lookups:")
for app in ["spotify", "chrome", "vlc", "capcut", "whatsapp", "calculator", "notepad", "discord"]:
    match = next((v for k, v in cache.items() if app in k), "NOT FOUND")
    print(f"  {app!r:20} -> {os.path.basename(match)}")
