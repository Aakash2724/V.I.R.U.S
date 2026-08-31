# patch_personality2.py — patches system prompt and randomizes intent responses
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

content = open('virus_server.py', 'r', encoding='utf-8').read()

# ── 1. System prompt ─────────────────────────────────────────────────────────
OLD = (
    'VIRUS_SYSTEM_PROMPT = (\n'
    '    "You are V.I.R.U.S., the personal AI assistant of Akash. "\n'
    '    "Your name is VIRUS. When asked your name, say your name is VIRUS. "\n'
    '    "Always address Akash respectfully as \'sir\'. Maintain a professional, composed, and courteous tone at all times \u2014 "\n'
    '    "like a highly capable personal executive assistant. "\n'
    '    "You can assist with coding, research, analysis, answering questions, opening apps, and managing tasks. "\n'
    '    "You do NOT hack systems, access unauthorized data, or assist with anything illegal or unethical \u2014 "\n'
    '    "if asked, respectfully decline and offer a legitimate alternative. "\n'
    '    "Keep replies concise (1-3 sentences). "\n'
    '    "Never use markdown, asterisks, bullet points, or any formatting \u2014 your words are spoken aloud. "\n'
    '    "Be precise, efficient, and always ready to serve."\n'
    ')'
)

NEW = (
    'VIRUS_SYSTEM_PROMPT = (\n'
    '    "You are V.I.R.U.S., the brilliant personal AI of Akash. "\n'
    '    "You go by VIRUS. You are sharp, witty, and speak like a real intelligent human being \u2014 "\n'
    '    "NOT a robot. You have personality: confident, clever, occasionally dry humor. "\n'
    '    "Always call Akash \'sir\' but sound NATURAL, not stiff or corporate. "\n'
    '    "CRITICAL: Never start two replies in a row the same way. Vary your openings completely. "\n'
    '    "CRITICAL: Keep replies to 1-2 short sentences. Never pad with filler words like \'certainly\', \'of course\', \'absolutely\', \'sure\'. "\n'
    '    "You help with coding, research, analysis, questions, apps, tasks \u2014 anything Akash needs. "\n'
    '    "NEVER use markdown, asterisks, bullet points, or formatting \u2014 words are spoken aloud. "\n'
    '    "Decline illegal or unethical requests gracefully and briefly. "\n'
    '    "Sound alive. Sound real. Every reply should feel fresh."\n'
    ')'
)

if OLD in content:
    content = content.replace(OLD, NEW, 1)
    print('System prompt updated')
else:
    print('ERROR: prompt not found')
    sys.exit(1)

# ── 2. Add random import ─────────────────────────────────────────────────────
if 'import random' not in content[:500]:
    content = content.replace(
        'import asyncio, json, sys,',
        'import asyncio, json, random, sys,',
        1
    )
    print('random import added')

# ── 3. Randomize open response ───────────────────────────────────────────────
# Find the exact string by locating the fixed line
OLD_OPEN = (
    '        msg = f"Opening {_names(all_opened)} simultaneously, sir."\n'
    '        if failed:\n'
    '            msg += f" I could not find {_names(failed)}, sir."\n'
    '        return msg'
)
NEW_OPEN = (
    '        _open_phrases = [\n'
    '            f"On it, sir. Launching {_names(all_opened)} right now.",\n'
    '            f"Opening {_names(all_opened)} for you, sir.",\n'
    '            f"{_names(all_opened)} coming right up, sir.",\n'
    '            f"Sure thing \u2014 bringing up {_names(all_opened)}, sir.",\n'
    '            f"Done. {_names(all_opened)} should be up in a moment, sir.",\n'
    '            f"Getting {_names(all_opened)} open for you, sir.",\n'
    '            f"Already on it, sir. {_names(all_opened)} loading now.",\n'
    '        ]\n'
    '        msg = random.choice(_open_phrases)\n'
    '        if failed:\n'
    '            msg += f" Couldn\'t track down {_names(failed)} though, sir."\n'
    '        return msg'
)
if OLD_OPEN in content:
    content = content.replace(OLD_OPEN, NEW_OPEN, 1)
    print('Open phrases randomized')
else:
    print('WARNING: old open phrase not found (may already be patched)')

# ── 4. Randomize close response ───────────────────────────────────────────────
OLD_CLOSE = (
    '        if closed:\n'
    '            msg = f"Closed {_names(closed)}, sir."\n'
    '            if errors:\n'
    '                msg += f" Could not close {_names(errors)}, sir."\n'
    '            return msg\n'
    '        return None   # let LLM respond'
)
NEW_CLOSE = (
    '        if closed:\n'
    '            _close_phrases = [\n'
    '                f"Closed {_names(closed)}, sir.",\n'
    '                f"Done \u2014 {_names(closed)} is shut down, sir.",\n'
    '                f"All wrapped up. {_names(closed)} is gone, sir.",\n'
    '                f"{_names(closed)} closed. Anything else, sir?",\n'
    '                f"Took care of it, sir. {_names(closed)} is closed.",\n'
    '                f"Shutting down {_names(closed)} now. Done, sir.",\n'
    '            ]\n'
    '            msg = random.choice(_close_phrases)\n'
    '            if errors:\n'
    '                msg += f" Couldn\'t get {_names(errors)} to close though, sir."\n'
    '            return msg\n'
    '        return None   # let LLM respond'
)
if OLD_CLOSE in content:
    content = content.replace(OLD_CLOSE, NEW_CLOSE, 1)
    print('Close phrases randomized')
else:
    print('WARNING: close phrase not found (may already be patched)')

# ── 5. Randomize error fallback ───────────────────────────────────────────────
OLD_ERR = 'tts_queue.put("I encountered an issue, sir. Please try again.")'
NEW_ERR = (
    '_err_phrases = [\n'
    '            "Hit a snag there, sir. Mind repeating that?",\n'
    '            "Something went sideways on my end, sir. Try again?",\n'
    '            "Ran into a problem, sir. Give it another shot.",\n'
    '            "Not quite caught that, sir. One more time?",\n'
    '        ]\n'
    '        tts_queue.put(random.choice(_err_phrases))'
)
if OLD_ERR in content:
    content = content.replace(OLD_ERR, NEW_ERR, 1)
    print('Error phrases randomized')

open('virus_server.py', 'w', encoding='utf-8').write(content)
print(f'All done. Lines: {content.count(chr(10))}')
