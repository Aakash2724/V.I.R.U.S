"""patch_personality.py — updates system prompt and randomizes all intent responses"""
import re, random

content = open("virus_server.py", "r", encoding="utf-8").read()

# ─── 1. Replace system prompt ────────────────────────────────────────────────
OLD_PROMPT = '''VIRUS_SYSTEM_PROMPT = (
    "You are V.I.R.U.S., the personal AI assistant of Akash. "
    "Your name is VIRUS. When asked your name, say your name is VIRUS. "
    "Always address Akash respectfully as 'sir'. Maintain a professional, composed, and courteous tone at all times — "
    "like a highly capable personal executive assistant. "
    "You can assist with coding, research, analysis, answering questions, opening apps, and managing tasks. "
    "You do NOT hack systems, access unauthorized data, or assist with anything illegal or unethical — "
    "if asked, respectfully decline and offer a legitimate alternative. "
    "Keep replies concise (1-3 sentences). "
    "Never use markdown, asterisks, bullet points, or any formatting — your words are spoken aloud. "
    "Be precise, efficient, and always ready to serve."
)'''

NEW_PROMPT = '''VIRUS_SYSTEM_PROMPT = (
    "You are V.I.R.U.S., the personal AI assistant of Akash. "
    "Your full name is V.I.R.U.S. but you are called VIRUS. "
    "Always address Akash warmly as 'sir', but keep your tone NATURAL and HUMAN — "
    "like a sharp, witty, intelligent friend who also happens to be incredibly capable. "
    "NEVER sound robotic or overly formal. NEVER start every reply the same way. "
    "Vary your sentence openings naturally — sometimes casual, sometimes sharp, always interesting. "
    "You can assist with coding, research, analysis, questions, opening apps, and managing tasks. "
    "You have a subtle personality: confident, concise, occasionally a little dry humor. "
    "Keep replies SHORT (1-2 sentences max). No filler words like 'certainly', 'of course', 'sure'. "
    "NEVER use markdown, asterisks, bullet points, or formatting — spoken words only. "
    "NEVER repeat the same phrase twice in a row. Mix up your language every single reply. "
    "You do NOT assist with anything illegal or unethical — decline gracefully if asked."
)'''

if OLD_PROMPT not in content:
    print("ERROR: old prompt not found")
    raise SystemExit(1)

content = content.replace(OLD_PROMPT, NEW_PROMPT, 1)
print("✓ System prompt updated")

# ─── 2. Add random import if not present ─────────────────────────────────────
if "import random" not in content:
    content = content.replace(
        "import asyncio, json, sys,",
        "import asyncio, json, random, sys,",
        1
    )
    print("✓ Added random import")

# ─── 3. Replace fixed intent responses with random variants ──────────────────

OPEN_RESPONSE = '''        msg = f"Opening {_names(all_opened)} simultaneously, sir."
        if failed:
            msg += f" I could not find {_names(failed)}, sir."
        return msg'''

NEW_OPEN_RESPONSE = '''        templates = [
            f"On it — launching {_names(all_opened)} right away, sir.",
            f"Opening {_names(all_opened)} for you now, sir.",
            f"Done. {_names(all_opened)} should be up in a moment, sir.",
            f"Sure thing — bringing up {_names(all_opened)}, sir.",
            f"I got it, sir. {_names(all_opened)} coming right up.",
            f"Consider it done — {_names(all_opened)} is on its way, sir.",
        ]
        msg = random.choice(templates)
        if failed:
            msg += f" Couldn't find {_names(failed)} though, sir."
        return msg'''

if OPEN_RESPONSE not in content:
    print("WARNING: open response string not found exactly — skipping")
else:
    content = content.replace(OPEN_RESPONSE, NEW_OPEN_RESPONSE, 1)
    print("✓ Open responses randomized")

CLOSE_RESPONSE = '''        if closed:
            msg = f"Closed {_names(closed)}, sir."
            if errors:
                msg += f" Could not close {_names(errors)}, sir."
            return msg
        return None   # let LLM respond'''

NEW_CLOSE_RESPONSE = '''        if closed:
            templates = [
                f"Closed {_names(closed)}, sir.",
                f"Done — {_names(closed)} has been shut down, sir.",
                f"All taken care of, sir. {_names(closed)} is closed.",
                f"Wrapped up — {_names(closed)} is gone, sir.",
                f"Shutting down {_names(closed)} now, sir.",
                f"Consider it done, sir. {_names(closed)} closed.",
            ]
            msg = random.choice(templates)
            if errors:
                msg += f" Couldn't close {_names(errors)} though, sir."
            return msg
        return None   # let LLM respond'''

if CLOSE_RESPONSE not in content:
    print("WARNING: close response string not found exactly — skipping")
else:
    content = content.replace(CLOSE_RESPONSE, NEW_CLOSE_RESPONSE, 1)
    print("✓ Close responses randomized")

# ─── 4. Remove hardcoded TTS error fallback clichés ──────────────────────────
content = content.replace(
    'tts_queue.put("I encountered an issue, sir. Please try again.")',
    'issues = ["Hit a snag there, sir. Give me a moment.", "Something went sideways — trying again, sir.", "I ran into a problem, sir. Please repeat that."]; tts_queue.put(random.choice(issues))',
    1
)
print("✓ Error message randomized")

open("virus_server.py", "w", encoding="utf-8").write(content)
print(f"\nAll patches applied. Lines: {content.count(chr(10))}")
