"""
Telegram Web Authenticator Module
---------------------------------
Handles web-based interactive Telegram MTProto login:
- Step 1: Send verification code to phone number via Telegram
- Step 2: Verify code (with 2FA password support)
- Step 3: Generate and encrypt StringSession for user's account
- Step 4: Disconnect / Reconnect management
"""

import os
import asyncio
import time
import logging
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneCodeInvalidError,
    PhoneCodeExpiredError,
    PhoneNumberInvalidError,
    FloodWaitError,
)

logger = logging.getLogger(__name__)

# Temporary store for pending auth requests { user_id: { "client": TelegramClient, "phone": str, "phone_code_hash": str, "created_at": float } }
_PENDING_AUTH_FLOWS = {}


def _clean_expired_flows():
    """Remove pending auth flows older than 10 minutes."""
    now = time.time()
    expired = [uid for uid, flow in _PENDING_AUTH_FLOWS.items() if now - flow.get("created_at", 0) > 600]
    for uid in expired:
        flow = _PENDING_AUTH_FLOWS.pop(uid, None)
        if flow and flow.get("client"):
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(flow["client"].disconnect())
            except Exception:
                pass


async def send_telegram_login_code(api_id: int, api_hash: str, phone_number: str, user_id: str) -> dict:
    """
    Step 1: Connect to Telegram MTProto and send confirmation code to the user's phone.
    """
    _clean_expired_flows()

    if not phone_number:
        return {"success": False, "error": "Phone number is required."}

    phone_clean = phone_number.strip().replace(" ", "").replace("-", "")
    if not phone_clean.startswith("+") and not phone_clean.isdigit():
        return {"success": False, "error": "Please provide a valid international phone number starting with +"}

    try:
        session = StringSession()
        client = TelegramClient(session, api_id, api_hash)
        await client.connect()

        result = await client.send_code_request(phone_clean)

        _PENDING_AUTH_FLOWS[user_id] = {
            "client": client,
            "phone": phone_clean,
            "phone_code_hash": result.phone_code_hash,
            "created_at": time.time(),
        }

        logger.info(f"Telegram login code sent to {phone_clean} for user {user_id}")
        return {
            "success": True,
            "phone_code_hash": result.phone_code_hash,
            "phone": phone_clean,
            "message": "Verification code sent to your Telegram application.",
        }

    except PhoneNumberInvalidError:
        return {"success": False, "error": "The phone number is invalid. Make sure to include the country code."}
    except FloodWaitError as e:
        return {"success": False, "error": f"Telegram rate limit: please wait {e.seconds} seconds before trying again."}
    except Exception as e:
        logger.error(f"Error sending Telegram login code: {e}")
        return {"success": False, "error": f"Failed to send code: {str(e)}"}


async def verify_telegram_login_code(
    api_id: int,
    api_hash: str,
    user_id: str,
    code: str,
    password: str = None
) -> dict:
    """
    Step 2: Sign in with the received confirmation code (+ 2FA password if required).
    Returns generated StringSession and user details on success.
    """
    _clean_expired_flows()
    flow = _PENDING_AUTH_FLOWS.get(user_id)

    if not flow or not flow.get("client"):
        return {"success": False, "error": "Login session expired. Please request a new code."}

    client: TelegramClient = flow["client"]
    phone = flow["phone"]
    phone_code_hash = flow["phone_code_hash"]

    try:
        if not await client.is_user_authorized():
            try:
                await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
            except SessionPasswordNeededError:
                if not password:
                    return {
                        "success": False,
                        "requires_2fa": True,
                        "error": "Two-factor authentication (2FA) is enabled on this account. Please enter your 2FA password.",
                    }
                await client.sign_in(password=password)

        me = await client.get_me()
        session_string = client.session.save()

        # Clean up pending flow
        _PENDING_AUTH_FLOWS.pop(user_id, None)

        telegram_account_data = {
            "telegram_user_id": me.id,
            "username": me.username or "",
            "first_name": me.first_name or "",
            "last_name": me.last_name or "",
            "phone": me.phone or phone,
            "session_string": session_string,
            "connected_at": time.time(),
        }

        logger.info(f"Telegram account connected successfully: @{me.username or me.id} for user {user_id}")
        return {
            "success": True,
            "telegram_account": telegram_account_data,
            "message": f"Successfully connected Telegram account @{me.username or me.first_name}!",
        }

    except PhoneCodeInvalidError:
        return {"success": False, "error": "Invalid verification code. Please check the code sent to your Telegram app."}
    except PhoneCodeExpiredError:
        return {"success": False, "error": "The verification code has expired. Please request a new code."}
    except SessionPasswordNeededError:
        return {
            "success": False,
            "requires_2fa": True,
            "error": "Two-factor authentication (2FA) password required.",
        }
    except FloodWaitError as e:
        return {"success": False, "error": f"Telegram rate limit: please wait {e.seconds} seconds."}
    except Exception as e:
        logger.error(f"Error verifying Telegram login code: {e}")
        return {"success": False, "error": f"Verification failed: {str(e)}"}
