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
    PasswordHashInvalidError,
)

logger = logging.getLogger(__name__)


async def send_telegram_login_code(db, api_id: int, api_hash: str, phone_number: str, user_id: str) -> dict:
    """
    Step 1: Connect to Telegram MTProto and send confirmation code to the user's phone.
    Persists temporary session state in the database for multi-worker safety.
    """
    if not phone_number:
        return {"success": False, "error": "Phone number is required."}

    phone_clean = phone_number.strip().replace(" ", "").replace("-", "")
    if not phone_clean.startswith("+") and not phone_clean.isdigit():
        return {"success": False, "error": "Please provide a valid international phone number starting with +"}

    client = None
    try:
        session = StringSession()
        client = TelegramClient(session, api_id, api_hash)
        await client.connect()

        result = await client.send_code_request(phone_clean)
        temp_session = client.session.save()

        if db and hasattr(db, "pending_auth"):
            try:
                # Clean up any previous pending auth for this phone
                db.pending_auth.delete_one({"phone": phone_clean})
                db.pending_auth.insert_one({
                    "_id": f"{user_id}_{phone_clean}",
                    "user_id": user_id,
                    "phone": phone_clean,
                    "phone_code_hash": result.phone_code_hash,
                    "temp_session": temp_session,
                    "created_at": time.time(),
                })
            except Exception as e:
                logger.warning(f"Could not persist pending auth in DB: {e}")

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
    finally:
        if client:
            try:
                await client.disconnect()
            except Exception:
                pass


async def verify_telegram_login_code(
    db,
    api_id: int,
    api_hash: str,
    user_id: str,
    code: str,
    password: str = None,
    phone_number: str = None
) -> dict:
    """
    Step 2: Sign in with the received confirmation code (+ 2FA password if required).
    Returns generated StringSession and user details on success.
    """
    phone_clean = (phone_number or "").strip().replace(" ", "").replace("-", "")

    # Look up pending auth in database
    auth_doc = None
    if db and hasattr(db, "pending_auth"):
        if phone_clean:
            auth_doc = db.pending_auth.find_one({"phone": phone_clean})
        if not auth_doc:
            auth_doc = db.pending_auth.find_one({"user_id": user_id})

    if not auth_doc:
        return {"success": False, "error": "Login session not found or expired. Please request a new code."}

    phone = auth_doc.get("phone", phone_clean)
    phone_code_hash = auth_doc.get("phone_code_hash", "")
    temp_session = auth_doc.get("temp_session", "")

    client = None
    try:
        session = StringSession(temp_session)
        client = TelegramClient(session, api_id, api_hash)
        await client.connect()

        if not await client.is_user_authorized():
            try:
                await client.sign_in(phone=phone, code=code.strip(), phone_code_hash=phone_code_hash)
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

        # Clean up pending auth from DB
        if db and hasattr(db, "pending_auth"):
            try:
                db.pending_auth.delete_one({"_id": auth_doc.get("_id")})
                db.pending_auth.delete_one({"phone": phone})
            except Exception:
                pass

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
    except PasswordHashInvalidError:
        return {
            "success": False,
            "requires_2fa": True,
            "error": "Invalid 2FA password. Please re-enter your Two-Factor Authentication password.",
        }
    except FloodWaitError as e:
        return {"success": False, "error": f"Telegram rate limit: please wait {e.seconds} seconds."}
    except Exception as e:
        logger.error(f"Error verifying Telegram login code: {e}")
        return {"success": False, "error": f"Verification failed: {str(e)}"}
    finally:
        if client:
            try:
                await client.disconnect()
            except Exception:
                pass
