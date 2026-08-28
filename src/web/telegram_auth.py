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


async def fetch_user_telegram_dialogs(api_id: int, api_hash: str, session_string: str, limit: int = 100) -> dict:
    """
    Fetch all user's channels, supergroups, and groups.
    """
    if not session_string:
        return {"success": False, "error": "No Telegram account connected. Please connect your account first."}

    from src.utils.encryption import decrypt_session
    decrypted_session = decrypt_session(session_string)

    client = None
    try:
        session = StringSession(decrypted_session)
        client = TelegramClient(session, api_id, api_hash)
        await client.connect()

        if not await client.is_user_authorized():
            return {"success": False, "error": "Telegram session is invalid or has expired."}

        dialogs_list = []
        async for dialog in client.iter_dialogs(limit=limit):
            entity = dialog.entity
            is_channel = getattr(dialog, "is_channel", False)
            is_group = getattr(dialog, "is_group", False)

            # Focus on channels and groups
            if is_channel or is_group:
                dialog_type = "channel" if is_channel and not getattr(entity, "megagroup", False) else "group"
                username = getattr(entity, "username", None) or ""
                # Only use t.me userpic for standard public usernames without special characters
                if username and username.replace('_', '').isalnum():
                    photo_url = f"https://t.me/i/userpic/320/{username}.jpg"
                else:
                    photo_url = f"/api/telegram/avatar/{dialog.id}"

                dialogs_list.append({
                    "id": dialog.id,
                    "title": dialog.name or "Untitled",
                    "username": username,
                    "type": dialog_type,
                    "is_channel": is_channel,
                    "is_group": is_group,
                    "unread_count": dialog.unread_count or 0,
                    "photo_url": photo_url,
                })

        return {
            "success": True,
            "count": len(dialogs_list),
            "dialogs": dialogs_list
        }
    except FloodWaitError as e:
        return {"success": False, "error": f"Telegram rate limit: please wait {e.seconds} seconds."}
    except Exception as e:
        logger.error(f"Error fetching dialogs: {e}")
        return {"success": False, "error": f"Failed to fetch channels: {str(e)}"}
    finally:
        if client:
            try:
                await client.disconnect()
            except Exception:
                pass


_AVATAR_CACHE = {}


async def fetch_channel_avatar(api_id: int, api_hash: str, session_string: str, entity_id: int) -> bytes:
    """Download profile photo bytes for a given channel/group ID with caching."""
    now = time.time()
    if entity_id in _AVATAR_CACHE:
        photo_bytes, cached_time = _AVATAR_CACHE[entity_id]
        if now - cached_time < 3600:
            return photo_bytes

    from src.utils.encryption import decrypt_session
    decrypted_session = decrypt_session(session_string)
    if not decrypted_session:
        return None

    client = None
    try:
        session = StringSession(decrypted_session)
        client = TelegramClient(session, api_id, api_hash)
        await client.connect()
        if not await client.is_user_authorized():
            return None

        photo_bytes = await client.download_profile_photo(entity_id, file=bytes, is_big=False)
        if photo_bytes:
            _AVATAR_CACHE[entity_id] = (photo_bytes, now)
        return photo_bytes
    except Exception as e:
        logger.debug(f"Could not fetch avatar for {entity_id}: {e}")
        return None
    finally:
        if client:
            try:
                await client.disconnect()
            except Exception:
                pass
