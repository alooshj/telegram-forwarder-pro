"""
Fernet AES Encryption Engine
----------------------------
Provides secure military-grade encryption (AES-128-CBC + HMAC-SHA256)
for user Telegram session strings stored in database.
"""

import os
import base64
import hashlib
import logging
from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

_DEFAULT_SALT = b"tg_forwarder_salt_2026"


def _get_fernet() -> Fernet:
    """Derive a deterministic Fernet key from the application SECRET_KEY."""
    secret = os.environ.get("SECRET_KEY", "dev-secret-key-change-me-forwarder-pro")
    derived_key = hashlib.sha256(secret.encode("utf-8") + _DEFAULT_SALT).digest()
    urlsafe_key = base64.urlsafe_b64encode(derived_key)
    return Fernet(urlsafe_key)


def encrypt_session(session_string: str) -> str:
    """
    Encrypt a Telethon StringSession before persisting in the database.
    Returns Fernet token string with prefix 'enc:'.
    """
    if not session_string:
        return ""
    if session_string.startswith("enc:"):
        return session_string

    try:
        f = _get_fernet()
        token = f.encrypt(session_string.encode("utf-8")).decode("utf-8")
        return f"enc:{token}"
    except Exception as e:
        logger.error(f"Encryption error: {e}")
        return session_string


def decrypt_session(stored_session: str) -> str:
    """
    Decrypt a stored session string. If not encrypted, returns as-is.
    """
    if not stored_session:
        return ""
    if not stored_session.startswith("enc:"):
        return stored_session

    raw_token = stored_session[4:]
    try:
        f = _get_fernet()
        decrypted = f.decrypt(raw_token.encode("utf-8")).decode("utf-8")
        return decrypted
    except (InvalidToken, Exception) as e:
        logger.error(f"Decryption error: {e}")
        return ""
