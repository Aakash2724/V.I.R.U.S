"""
diagnose.py - Run with: python diagnose.py
Starts the same pipeline as virus_server but adds faulthandler 
to capture any C-level segfault to a file.
"""
import faulthandler, sys, os

# Dump crashes to file BEFORE anything else loads
crash_log = open("crash_dump.txt", "w", encoding="utf-8")
faulthandler.enable(file=crash_log)
print("[DIAG] faulthandler enabled -> crash_dump.txt")

# Now import the real server module (will trigger startup)
import uvicorn

if __name__ == "__main__":
    uvicorn.run("virus_server:app", host="0.0.0.0", port=8000, reload=False)
