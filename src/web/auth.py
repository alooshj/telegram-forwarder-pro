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
from datetime import datetime, timezone, timedelta
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
    def create_user(db, email: str, password: str, name: str = "", plan: str = "trial", role: str = None) -> dict:
        """Create a new registered user with 3-day automatic trial and role hierarchy."""
        if not email or not password:
            raise ValueError("Email and password are required")

        email = email.strip().lower()
        existing = db.users.find_one({"email": email})
        if existing:
            raise ValueError("An account with this email already exists")

        user_id = str(uuid.uuid4())
        hashed_password = generate_password_hash(password)
        now = datetime.now(timezone.utc)

        # Super admin emails or first registered user
        SUPER_ADMIN_EMAILS = {"alooshpal@gmail.com"}
        user_count = db.users.count_documents({}) if hasattr(db, "users") else 0
        if email in SUPER_ADMIN_EMAILS or (user_count == 0 and role is None):
            assigned_role = "super_admin"
            assigned_plan = "annual"
            sub_status = "active"
            expires_at = now + timedelta(days=3650)
            max_channels = 999
        else:
            assigned_role = role or "client"
            assigned_plan = plan or "trial"
            sub_status = "trial" if assigned_plan == "trial" else "active"
            expires_at = now + timedelta(days=3) if assigned_plan == "trial" else now + timedelta(days=30)
            max_channels = 2 if assigned_plan == "trial" else 999

        user_doc = {
            "_id": user_id,
            "email": email,
            "name": name.strip() or email.split("@")[0],
            "password_hash": hashed_password,
            "plan": assigned_plan,
            "role": assigned_role,
            "subscription_status": sub_status,
            "subscription_expires_at": expires_at,
            "max_target_channels": max_channels,
            "created_at": now,
            "updated_at": now,
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
        """Store or update connected Telegram userbot session for a user (encrypted with AES)."""
        if not db or not user_id:
            return False

        if telegram_data and "session_string" in telegram_data:
            from src.utils.encryption import encrypt_session
            telegram_data = dict(telegram_data)
            telegram_data["session_string"] = encrypt_session(telegram_data["session_string"])

        db.users.update_one(
            {"_id": user_id},
            {"$set": {"telegram_account": telegram_data, "updated_at": datetime.now(timezone.utc)}}
        )
        return True

    @staticmethod
    def get_user_telegram_session(db, user_id: str) -> str:
        """Fetch and decrypt the user's active Telegram session string."""
        user = UserManager.get_user_by_id(db, user_id)
        if not user or not user.get("telegram_account"):
            return ""
        from src.utils.encryption import decrypt_session
        return decrypt_session(user["telegram_account"].get("session_string", ""))

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

    @staticmethod
    def get_subscription_info(db, user_id: str) -> dict:
        """Retrieve full subscription metadata for user."""
        user = UserManager.get_user_by_id(db, user_id)
        if not user:
            return {
                "status": "expired",
                "is_active": False,
                "plan": "none",
                "role": "client",
                "expires_at": None,
                "days_remaining": 0,
                "max_target_channels": 0,
            }

        from src.billing.plans import check_subscription_status, get_plan
        status, is_active, expires_at, days_left = check_subscription_status(user)
        plan_id = user.get("plan", "trial")
        plan_cfg = get_plan(plan_id) or {}

        return {
            "status": status,
            "is_active": is_active,
            "plan": plan_id,
            "plan_name": plan_cfg.get("name", plan_id.capitalize()),
            "plan_name_ar": plan_cfg.get("name_ar", plan_id),
            "role": user.get("role", "client"),
            "expires_at": expires_at.isoformat() if expires_at else None,
            "days_remaining": days_left,
            "max_target_channels": user.get("max_target_channels", plan_cfg.get("max_target_channels", 999)),
        }

    @staticmethod
    def is_subscription_valid(db, user_id: str) -> bool:
        """Check if user has an active or trial subscription (or is super_admin)."""
        info = UserManager.get_subscription_info(db, user_id)
        return info.get("is_active", False)
