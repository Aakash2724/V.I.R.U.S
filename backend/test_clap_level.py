# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
"""
V.I.R.U.S. Clap Level Tester
==============================
Run this to see the live RMS level your microphone picks up.
Clap normally and note the peak value — set CLAP_THRESHOLD
in .env to ~70% of that peak value.

Usage:
    cd backend
    python test_clap_level.py
"""

import struct, time
import pyaudio

RATE  = 16_000
CHUNK = 512

def rms(raw: bytes) -> float:
    n = len(raw) // 2
    if n == 0:
        return 0.0
    samples = struct.unpack(f"{n}h", raw)
    return (sum(s * s for s in samples) / n) ** 0.5 / 32_768.0

def bar(level: float, width: int = 40) -> str:
    filled = int(min(level / 0.30, 1.0) * width)
    return "[" + "#" * filled + "." * (width - filled) + "]"

pa     = pyaudio.PyAudio()
stream = pa.open(format=pyaudio.paInt16, channels=1,
                 rate=RATE, input=True, frames_per_buffer=CHUNK)

print("=" * 56)
print("  V.I.R.U.S.  |  Clap Level Tester")
print("  Clap near your mic and watch the bar spike.")
print("  Current threshold default: 0.15")
print("  Ctrl+C to quit")
print("=" * 56)
print()

peak = 0.0
try:
    while True:
        data  = stream.read(CHUNK, exception_on_overflow=False)
        level = rms(data)
        if level > peak:
            peak = level

        marker = " ◀ CLAP!" if level > 0.15 else ""
        print(f"\r  RMS: {level:6.4f}  Peak: {peak:6.4f}  {bar(level)}{marker}  ",
              end="", flush=True)

        time.sleep(0.01)

except KeyboardInterrupt:
    print(f"\n\n  Peak RMS recorded: {peak:.4f}")
    suggested = round(peak * 0.70, 3)
    print(f"  Suggested CLAP_THRESHOLD: {suggested}")
    print(f"\n  Add this to backend/.env:")
    print(f"  CLAP_THRESHOLD={suggested}")
finally:
    stream.stop_stream()
    stream.close()
    pa.terminate()
