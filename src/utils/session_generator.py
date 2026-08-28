"""
Session String Generator
------------------------
Generates Telethon session strings for non-programmer setup.
Users only need API_ID + API_HASH (from https://my.telegram.org),
then run this script to get a session string for the .env file.
"""

import sys
import os

# Ensure src is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telethon.sync import TelegramClient
from telethon.sessions import StringSession


def generate_session_string(api_id: int, api_hash: str, phone_number: str = None) -> str:
    """Generate a Telethon session string for a user account."""
    with TelegramClient(StringSession(), api_id, api_hash) as client:
        if phone_number and not client.is_user_authorized():
            client.start(phone=phone_number)
        session_string = client.session.save()
    return session_string


def main():
    print("=" * 60)
    print("  TeleTips Pro - Session String Generator")
    print("=" * 60)
    print()
    print("You'll need your API credentials from https://my.telegram.org")
    print("This script will generate a session string for your .env file.")
    print()

    try:
        api_id = int(input("Enter API ID: ").strip())
        api_hash = input("Enter API HASH: ").strip()
        phone_number = input("Enter phone number (with country code, e.g. +1234567890): ").strip()
    except ValueError:
        print("ERROR: API ID must be a number.")
        sys.exit(1)

    print()
    print("Generating session string...")
    try:
        session_str = generate_session_string(api_id, api_hash, phone_number)
        print()
        print("✅ SUCCESS! Session string generated:")
        print()
        print(f"SESSION_STRING={session_str}")
        print()
        print("Copy this into your .env file under SESSION_STRING=")
        print("Make sure your phone has received the login code and entered it.")
    except Exception as e:
        print(f"❌ ERROR: {e}")
        print("Ensure you entered the correct API ID/HASH and phone number.")
        sys.exit(1)


if __name__ == "__main__":
    main()
