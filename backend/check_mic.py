import pyaudio
import struct
import math

print("Testing PyAudio...")
CHUNK = 512
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000

p = pyaudio.PyAudio()

try:
    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK)

    print("Stream opened.")
    for i in range(10):  # 10 chunks ~ 0.3 seconds
        data = stream.read(CHUNK, exception_on_overflow=False)
        n = len(data) // 2
        samples = struct.unpack(f"{n}h", data)
        mean_sq = sum(s * s for s in samples) / n
        rms = (math.sqrt(mean_sq)) / 32768.0
        
        if rms > 0.001:
            print(f"Got audio! RMS: {rms:.4f}")
        else:
            print(f"Silent/Zero. RMS: {rms:.4f}")

except Exception as e:
    print(f"Failed to open PyAudio: {e}")
finally:
    p.terminate()
