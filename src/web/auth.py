"""
Authentication & User Management Module
---------------------------------------
Handles multi-tenant SaaS user registration, password hashing, session tokens,
and authentication middleware for Telegram Forwarder Pro.
"""

import os
import uuid
import hmac
import hashlib
import time
import logging
from functools import wraps
from datetime import datetime, timezone
from flask import request, jsonify, g
from werkzeug.security import generate_password_hash, check_password_hash

logger = logging.getLogger(__name__)

# Secret key for token signing (falls back to a persistent or generated key)
AUTH_SECRET_KEY = os.getenv("AUTH_SECRET_KEY", "tg-forwarder-pro-saas-secret-key-2026")


def generate_auth_token(user_id: str, email: str = "") -> str:
    """Generate a signed, timestamped authentication token."""
    timestamp = int(time.time())
    payload = f"{user_id}:{email}:{timestamp}"
    signature = hmac.new(
        AUTH_SECRET_KEY.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()
    return f"{payload}:{signature}"


def verify_auth_token(token: str, max_age_seconds: int = 30 * 86400) -> dict:
    """
    Verify a signed authentication token.
    Returns user payload dict if valid, else None.
    """
    if not token or ":" not in token:
        return None

    try:
        parts = token.split(":")
        if len(parts) != 4:
            return None

        user_id, email, ts_str, signature = parts
        timestamp = int(ts_str)

        # Check token expiration
        if time.time() - timestamp > max_age_seconds:
            logger.warning(f"Auth token expired for user {user_id}")
            return None

        # Verify signature
        expected_payload = f"{user_id}:{email}:{timestamp}"
        expected_signature = hmac.new(
            AUTH_SECRET_KEY.encode(),
            expected_payload.encode(),
            hashlib.sha256
        ).hexdigest()

        if hmac.compare_digest(signature, expected_signature):
            return {"user_id": user_id, "email": email, "timestamp": timestamp}

        return None
    except Exception as e:
        logger.warning(f"Error verifying auth token: {e}")
        return None


def get_current_user_from_request(db):
    """Extract and authenticate the user from Authorization header or Cookie."""
    # 1. Check Authorization Bearer header
    auth_header = request.headers.get("Authorization", "")
    token = None
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1].strip()

    # 2. Fallback to cookie
    if not token:
        token = request.cookies.get("auth_token", "")

    if not token:
        return None

    verified = verify_auth_token(token)
    if not verified or db is None:
        return None

    user = db.users.find_one({"_id": verified["user_id"]})
    return user


def require_auth(f):
    """Decorator to require authenticated user on API routes."""
    @wraps(f)
    def decorated(*args, **kwargs):
        from src.web.api import _get_db
        db = _get_db()
        user = get_current_user_from_request(db)
        if not user:
            return jsonify({"success": False, "error": "Unauthorized. Please log in."}), 401
        g.current_user = user
        return f(*args, **kwargs)
    return decorated


class UserManager:
    """Helper class for user database operations."""

    @staticmethod
    def create_user(db, email: str, password: str, name: str = "", plan: str = "free") -> dict:
        """Create a new registered user."""
        if not email or not password:
            raise ValueError("Email and password are required")

        email = email.strip().lower()
        existing = db.users.find_one({"email": email})
        if existing:
            raise ValueError("An account with this email already exists")

        user_id = str(uuid.uuid4())
        hashed_password = generate_password_hash(password)

        user_doc = {
            "_id": user_id,
            "email": email,
            "name": name.strip() or email.split("@")[0],
            "password_hash": hashed_password,
            "plan": plan,
            "role": "user",
            "created_at": datetime.now(timezone.utc),
            "telegram_account": None,  # Will store connected telegram info
        }

        db.users.insert_one(user_doc)
        return user_doc

    @staticmethod
    def authenticate_user(db, email: str, password: str) -> dict:
        """Validate user credentials and return user dict if valid."""
        if not email or not password:
            return None

        email = email.strip().lower()
        user = db.users.find_one({"email": email})
        if not user:
            return None

        if check_password_hash(user.get("password_hash", ""), password):
            return user
        return None

    @staticmethod
    def get_user_by_id(db, user_id: str) -> dict:
        """Fetch user by ID."""
        if not db or not user_id:
            return None
        return db.users.find_one({"_id": user_id})

    @staticmethod
    def update_telegram_account(db, user_id: str, telegram_data: dict) -> bool:
        """Store or update connected Telegram userbot session for a user."""
        if not db or not user_id:
            return False

        db.users.update_one(
            {"_id": user_id},
            {"$set": {"telegram_account": telegram_data, "updated_at": datetime.now(timezone.utc)}}
        )
        return True

    @staticmethod
    def disconnect_telegram_account(db, user_id: str) -> bool:
        """Disconnect and delete the user's Telegram session."""
        if not db or not user_id:
            return False

        db.users.update_one(
            {"_id": user_id},
            {"$set": {"telegram_account": None, "updated_at": datetime.now(timezone.utc)}}
        )
        return True
