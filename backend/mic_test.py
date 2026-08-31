import pyaudio, numpy as np

p = pyaudio.PyAudio()
s = p.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=512)
print("Speak now...")
peaks = []
for i in range(94):
    d = s.read(512, exception_on_overflow=False)
    a = np.frombuffer(d, dtype=np.int16).astype(np.float32) / 32768.0
    peaks.append(float(np.max(np.abs(a))))
s.stop_stream(); s.close(); p.terminate()
print(f"Peak: {max(peaks):.4f}")
print("GOOD" if max(peaks) > 0.1 else "SILENT")