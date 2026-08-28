"""
Quick Session String Generator
-------------------------------
Script to generate a Telethon StringSession for deployment.
Usage: python generate_session.py
"""

import os
import sys
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from dotenv import load_dotenv

# Load credentials from .env if available
load_dotenv(os.path.join(os.path.dirname(__file__), "config", ".env"))

API_ID = os.environ.get("API_ID")
API_HASH = os.environ.get("API_HASH")

if not API_ID or not API_HASH:
    print("=" * 60)
    print("  TeleTips Pro - Session String Generator")
    print("=" * 60)
    try:
        api_id_input = input("Enter API_ID: ").strip()
        API_ID = int(api_id_input)
        API_HASH = input("Enter API_HASH: ").strip()
    except (ValueError, EOFError):
        print("ERROR: Invalid API_ID entered.")
        sys.exit(1)
else:
    API_ID = int(API_ID)

print("\n[INFO] Initializing Telethon StringSession...")
try:
    with TelegramClient(StringSession(), API_ID, API_HASH) as client:
        session_str = client.session.save()

    print("\n✅ [SUCCESS] Session string generated:")
    print(f"SESSION_STRING={session_str}")

    with open(".session_string", "w") as f:
        f.write(session_str)

    print("\n[INFO] Saved to .session_string file")
except Exception as e:
    print(f"\n❌ [ERROR] Failed to generate session string: {e}")
    sys.exit(1)