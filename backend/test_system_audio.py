import time
import ctypes
import comtypes
from pycaw.pycaw import AudioUtilities, IAudioMeterInformation

def get_master_peak():
    try:
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioMeterInformation._iid_, comtypes.CLSCTX_ALL, None)
        meter = ctypes.cast(interface, ctypes.POINTER(IAudioMeterInformation))
        return meter.GetPeakValue()
    except Exception as e:
        print("err:", e)
        return 0.0

for _ in range(5):
    print("Peak:", get_master_peak())
    time.sleep(1)
