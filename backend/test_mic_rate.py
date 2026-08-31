import pyaudio
p = pyaudio.PyAudio()
try:
    stream = p.open(format=pyaudio.paInt16, channels=1, rate=48000, input=True, input_device_index=1)
    print("SUCCESS 1: 48000Hz")
    stream.close()
except Exception as e:
    print("FAIL 1: 48000Hz", e)

try:
    stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, input_device_index=1)
    print("SUCCESS 1: 16000Hz")
    stream.close()
except Exception as e:
    print("FAIL 1: 16000Hz", e)
p.terminate()
