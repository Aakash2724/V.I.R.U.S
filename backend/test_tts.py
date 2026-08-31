import pygame, edge_tts, asyncio, os, time, traceback

print("Testing TTS pipeline...")

try:
    pygame.mixer.pre_init(44100, -16, 2, 512)
    pygame.mixer.init()
    print("pygame mixer: OK")
except Exception:
    print("pygame mixer FAILED:", traceback.format_exc())

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

async def gen():
    c = edge_tts.Communicate("Hello sir, this is a test.", voice="en-US-JennyNeural", rate="+10%")
    await c.save("test_out.mp3")

try:
    loop.run_until_complete(gen())
    print("edge_tts generate: OK")
except Exception:
    print("edge_tts generate FAILED:", traceback.format_exc())

try:
    pygame.mixer.music.load("test_out.mp3")
    pygame.mixer.music.play()
    print("pygame play: OK — waiting 4s...")
    time.sleep(4)
    pygame.mixer.music.stop()
    os.remove("test_out.mp3")
    print("All OK!")
except Exception:
    print("pygame play FAILED:", traceback.format_exc())
