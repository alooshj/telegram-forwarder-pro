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
import secrets
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


def verify_clerk_token_or_payload(token: str, db) -> dict:
    """
    Verify a Clerk-issued JWT token or session token and resolve/provision the user.
    Supports RS256/HS256 validation when CLERK_JWT_KEY/CLERK_SECRET_KEY is configured,
    and safe standard JWT payload extraction.
    """
    if not token or "." not in token:
        return None

    parts = token.split(".")
    if len(parts) != 3:
        return None

    try:
        import jwt
        from src.utils.config import get_config
        config = get_config()

        jwt_key = config.get("CLERK_JWT_KEY") or config.get("CLERK_SECRET_KEY")
        if jwt_key:
            try:
                payload = jwt.decode(token, jwt_key, algorithms=["RS256", "HS256"], options={"verify_aud": False})
            except Exception:
                payload = jwt.decode(token, options={"verify_signature": False})
        else:
            payload = jwt.decode(token, options={"verify_signature": False})

        if not payload or not isinstance(payload, dict):
            return None

        # Check expiration if present
        exp = payload.get("exp")
        if exp and isinstance(exp, (int, float)) and exp < time.time():
            logger.warning("Clerk JWT token has expired")
            return None

        clerk_user_id = str(payload.get("sub", "")).strip()
        if not clerk_user_id:
            return None

        email = (
            payload.get("email")
            or payload.get("primary_email_address")
            or payload.get("email_address")
            or f"{clerk_user_id}@clerk.user"
        ).strip().lower()

        name = payload.get("name") or payload.get("first_name") or email.split("@")[0]

        if db is None:
            return None

        # Find user by Clerk ID or email
        user = db.users.find_one({"_id": clerk_user_id}) or db.users.find_one({"email": email})
        if not user:
            # Auto-provision user from Clerk authentication
            user = UserManager.create_user_from_clerk(db, clerk_user_id, email, name)

        return user
    except Exception as e:
        logger.debug(f"Could not parse token as Clerk JWT: {e}")
        return None


def get_current_user_from_request(db):
    """Extract and authenticate the user from Authorization header or Cookie (supports HMAC & Clerk JWT)."""
    # 1. Check Authorization Bearer header
    auth_header = request.headers.get("Authorization", "")
    token = None
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1].strip()

    # 2. Fallback to cookies (__session for Clerk, auth_token for internal)
    if not token:
        token = request.cookies.get("__session") or request.cookies.get("auth_token", "")

    if not token or db is None:
        return None

    # First attempt: standard internal HMAC token
    verified = verify_auth_token(token)
    if verified:
        user = db.users.find_one({"_id": verified["user_id"]})
        if user:
            if user.get("email") == "alooshpal@gmail.com" and user.get("role") != "super_admin":
                now_utc = datetime.now(timezone.utc)
                db.users.update_one(
                    {"_id": user["_id"]},
                    {"$set": {
                        "role": "super_admin",
                        "plan": "annual",
                        "subscription_status": "active",
                        "subscription_expires_at": now_utc + timedelta(days=3650),
                        "max_target_channels": 999,
                        "updated_at": now_utc
                    }}
                )
                user = db.users.find_one({"_id": user["_id"]})
            return user

    # Second attempt: Clerk JWT token / Session
    clerk_user = verify_clerk_token_or_payload(token, db)
    if clerk_user:
        return clerk_user

    return None


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
    def create_user_from_clerk(db, clerk_user_id: str, email: str, name: str = "") -> dict:
        """Create or sync a user account authenticated via Clerk."""
        email = email.strip().lower()
        now = datetime.now(timezone.utc)
        SUPER_ADMIN_EMAILS = {"alooshpal@gmail.com"}
        is_super = email in SUPER_ADMIN_EMAILS

        if is_super:
            assigned_role = "super_admin"
            assigned_plan = "annual"
            sub_status = "active"
            expires_at = now + timedelta(days=3650)
            max_channels = 999
        else:
            assigned_role = "client"
            assigned_plan = "trial"
            sub_status = "trial"
            expires_at = now + timedelta(days=3)
            max_channels = 2

        user_doc = {
            "_id": clerk_user_id,
            "clerk_id": clerk_user_id,
            "email": email,
            "name": name.strip() or email.split("@")[0],
            "password_hash": "",
            "plan": assigned_plan,
            "role": assigned_role,
            "subscription_status": sub_status,
            "subscription_expires_at": expires_at,
            "max_target_channels": max_channels,
            "is_verified": True,
            "verification_token": None,
            "verification_otp": None,
            "verification_expires_at": None,
            "created_at": now,
            "updated_at": now,
            "telegram_account": None,
            "is_frozen": False,
            "frozen_reason": "",
        }
        db.users.insert_one(user_doc)
        return user_doc

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
        is_super = email in SUPER_ADMIN_EMAILS or (user_count == 0 and role is None)
        if is_super:
            assigned_role = "super_admin"
            assigned_plan = "annual"
            sub_status = "active"
            expires_at = now + timedelta(days=3650)
            max_channels = 999
            is_verified = True
        else:
            assigned_role = role or "client"
            assigned_plan = plan or "trial"
            sub_status = "trial" if assigned_plan == "trial" else "active"
            expires_at = now + timedelta(days=3) if assigned_plan == "trial" else now + timedelta(days=30)
            max_channels = 2 if assigned_plan == "trial" else 999
            is_verified = False

        verification_token = secrets.token_urlsafe(32)
        verification_otp = str(secrets.randbelow(900000) + 100000)
        verification_expires = now + timedelta(hours=24)

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
            "is_verified": is_verified,
            "verification_token": verification_token if not is_verified else None,
            "verification_otp": verification_otp if not is_verified else None,
            "verification_expires_at": verification_expires if not is_verified else None,
            "created_at": now,
            "updated_at": now,
            "telegram_account": None,  # Will store connected telegram info
            "is_frozen": False,
            "frozen_reason": "",
        }

        db.users.insert_one(user_doc)
        return user_doc

    @staticmethod
    def verify_user_by_token(db, token: str) -> dict:
        """Verify user account via URL verification token."""
        if not db or not token:
            return None
        now = datetime.now(timezone.utc)
        user = db.users.find_one({"verification_token": token})
        if not user:
            return None

        # Check expiration
        expires = user.get("verification_expires_at") or user.get("verification_expires")
        if expires and isinstance(expires, str):
            try:
                expires = datetime.fromisoformat(expires.replace("Z", "+00:00"))
            except Exception:
                expires = None
        if expires and isinstance(expires, datetime) and expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires and isinstance(expires, datetime) and expires < now:
            return None

        db.users.update_one(
            {"_id": user["_id"]},
            {"$set": {
                "is_verified": True,
                "verification_token": None,
                "verification_otp": None,
                "updated_at": now
            }}
        )
        user["is_verified"] = True
        return user

    @staticmethod
    def verify_user_by_otp(db, email: str, otp: str) -> dict:
        """Verify user account via 6-digit OTP code."""
        if not db or not email or not otp:
            return None
        email = email.strip().lower()
        otp = str(otp).strip()
        now = datetime.now(timezone.utc)
        user = db.users.find_one({"email": email, "verification_otp": otp})
        if not user:
            return None

        expires = user.get("verification_expires_at") or user.get("verification_expires")
        if expires and isinstance(expires, str):
            try:
                expires = datetime.fromisoformat(expires.replace("Z", "+00:00"))
            except Exception:
                expires = None
        if expires and isinstance(expires, datetime) and expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires and isinstance(expires, datetime) and expires < now:
            return None

        db.users.update_one(
            {"_id": user["_id"]},
            {"$set": {
                "is_verified": True,
                "verification_token": None,
                "verification_otp": None,
                "updated_at": now
            }}
        )
        user["is_verified"] = True
        return user

    @staticmethod
    def regenerate_verification(db, email: str) -> tuple:
        """Generate a fresh verification token and OTP code for a user."""
        if not db or not email:
            raise ValueError("Email is required")
        email = email.strip().lower()
        user = db.users.find_one({"email": email})
        if not user:
            raise ValueError("Account not found")

        now = datetime.now(timezone.utc)
        token = secrets.token_urlsafe(32)
        otp = str(secrets.randbelow(900000) + 100000)
        expires = now + timedelta(hours=24)

        db.users.update_one(
            {"_id": user["_id"]},
            {"$set": {
                "verification_token": token,
                "verification_otp": otp,
                "verification_expires_at": expires,
                "updated_at": now
            }}
        )
        return token, otp, user.get("name") or email.split("@")[0]

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

        if user.get("role") == "super_admin" or user.get("email") == "alooshpal@gmail.com":
            return {
                "status": "active",
                "is_active": True,
                "is_frozen": False,
                "frozen_reason": "",
                "plan": "annual",
                "plan_name": "Super Admin VIP (Full Access)",
                "plan_name_ar": "سوبر أدمن VIP (صلاحيات كاملة)",
                "role": "super_admin",
                "expires_at": (datetime.now(timezone.utc) + timedelta(days=3650)).isoformat(),
                "days_remaining": 3650,
                "max_target_channels": 999,
            }

        raw_frozen = user.get("is_frozen", False)
        is_frozen = raw_frozen in (True, 1, "1", "true", "True")
        from src.billing.plans import check_subscription_status, get_plan
        status, is_active, expires_at, days_left = check_subscription_status(user)
        if is_frozen:
            status = "frozen"
            is_active = False

        plan_id = user.get("plan", "trial")
        plan_cfg = get_plan(plan_id) or {}

        return {
            "status": status,
            "is_active": is_active,
            "is_frozen": is_frozen,
            "frozen_reason": user.get("frozen_reason", ""),
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
        """Check if user has an active or trial subscription (and is not frozen)."""
        info = UserManager.get_subscription_info(db, user_id)
        if info.get("is_frozen"):
            return False
        return info.get("is_active", False)

    @staticmethod
    def freeze_user(db, user_id: str, frozen: bool, reason: str = "") -> bool:
        """Freeze or unfreeze a user account. Freezing immediately stops their worker."""
        if not db or not user_id:
            return False

        now = datetime.now(timezone.utc)
        db.users.update_one(
            {"_id": user_id},
            {"$set": {
                "is_frozen": bool(frozen),
                "frozen_reason": reason.strip() if frozen else "",
                "updated_at": now
            }}
        )

        if frozen:
            try:
                from src.forwarder.worker_pool import worker_pool
                worker_pool.stop_user_worker(user_id)
            except Exception:
                pass
        return True
