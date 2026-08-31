import soundcard as sc
import time
import numpy as np

def loopback_test():
    try:
        lb = sc.default_speaker().name
        print("Default speaker:", lb)
        mic = sc.get_microphone(id=str(lb), include_loopback=True)
        with mic.recorder(samplerate=48000) as rec:
            for _ in range(5):
                data = rec.record(numframes=4800)
                rms = np.sqrt(np.mean(data**2))
                print("Loopback RMS:", rms)
    except Exception as e:
        print("Loopback error:", e)

loopback_test()
