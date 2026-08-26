"""
Quick Session String Generator
-------------------------------
One-shot script to generate a Telethon session string for a given phone number.
Usage: python generate_session.py
"""

import os
import sys
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

# --- Your credentials ---
API_ID = 39284987
API_HASH = "db5acc5317a2c17cbbff862e29d04e9b"
PHONE_NUMBER = "+972568185376"

print(f"[INFO] Starting session generation for {PHONE_NUMBER}")

with TelegramClient("anon", API_ID, API_HASH) as client:
    session_str = client.session.save()

print("\n✅ [SUCCESS] Session string generated:")
print(f"SESSION_STRING={session_str}")

# Optionally save to file
with open(".session_string", "w") as f:
    f.write(session_str)

print("\n[INFO] Saved to .session_string file")