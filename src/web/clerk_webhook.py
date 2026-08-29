"""
Clerk Webhook Synchronization Engine
------------------------------------
Handles real-time webhook events from Clerk (user.created, user.updated, user.deleted)
secured with Svix HMAC-SHA256 signature verification.
Synchronizes user records to MongoDB/SQLite with idempotent updates.
"""

import os
import json
import base64
import hmac
import hashlib
import time
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)


def get_clerk_webhook_secret() -> str:
    """Retrieve Clerk Webhook Signing Secret (whsec_...)."""
    return (
        os.environ.get("CLERK_WEBHOOK_SECRET")
        or os.environ.get("CLERK_SIGNING_SECRET")
        or os.environ.get("CLERK_SECRET_KEY")
        or ""
    ).strip()


def verify_svix_signature(raw_payload: bytes, headers: dict, secret: str) -> bool:
    """
    Verify Svix HMAC-SHA256 webhook signatures.
    Supports both official svix library and native fallback.
    """
    if not secret:
        logger.warning("CLERK_WEBHOOK_SECRET is not configured")
        return False

    svix_id = headers.get("svix-id") or headers.get("Svix-Id")
    svix_timestamp = headers.get("svix-timestamp") or headers.get("Svix-Timestamp")
    svix_signature = headers.get("svix-signature") or headers.get("Svix-Signature")

    if not svix_id or not svix_timestamp or not svix_signature:
        logger.warning("Missing Svix signature headers")
        return False

    # Check timestamp tolerance (5 minutes)
    try:
        ts = int(svix_timestamp)
        if abs(time.time() - ts) > 300:
            logger.warning("Svix webhook timestamp out of tolerance")
            return False
    except ValueError:
        return False

    # 1. Try official svix library
    try:
        from svix.webhooks import Webhook
        wh = Webhook(secret)
        wh.verify(raw_payload.decode("utf-8") if isinstance(raw_payload, bytes) else str(raw_payload), headers)
        return True
    except Exception as svix_err:
        logger.debug(f"svix package verification: {svix_err}")

    # 2. Native Svix HMAC verification fallback
    try:
        clean_secret = secret
        if clean_secret.startswith("whsec_"):
            clean_secret = clean_secret[6:]
        
        try:
            key_bytes = base64.b64decode(clean_secret)
        except Exception:
            key_bytes = clean_secret.encode("utf-8")

        body_str = raw_payload.decode("utf-8") if isinstance(raw_payload, bytes) else str(raw_payload)
        signed_content = f"{svix_id}.{svix_timestamp}.{body_str}".encode("utf-8")
        computed_sig = base64.b64encode(hmac.new(key_bytes, signed_content, hashlib.sha256).digest()).decode("utf-8")

        passed_sigs = svix_signature.split(" ")
        for sig_item in passed_sigs:
            parts = sig_item.split(",", 1)
            sig_val = parts[1] if len(parts) == 2 else parts[0]
            if hmac.compare_digest(computed_sig, sig_val):
                return True
    except Exception as e:
        logger.warning(f"Native Svix verification failed: {e}")

    return False


def process_clerk_webhook_event(db, payload: dict) -> tuple:
    """
    Process verified Clerk webhook event and synchronize user state.
    Returns (success: bool, response_dict: dict, status_code: int).
    """
    if db is None:
        return False, {"error": "Database not connected"}, 500

    event_type = payload.get("type", "")
    data = payload.get("data", {}) or {}
    clerk_id = str(data.get("id", "")).strip()

    if not clerk_id:
        return False, {"error": "Missing Clerk user id in payload"}, 400

    now_utc = datetime.now(timezone.utc)

    # Extract primary email
    email = ""
    email_addresses = data.get("email_addresses") or []
    primary_email_id = data.get("primary_email_address_id")
    for email_obj in email_addresses:
        if email_obj.get("id") == primary_email_id:
            email = email_obj.get("email_address", "").strip().lower()
            break
    if not email and email_addresses:
        email = email_addresses[0].get("email_address", "").strip().lower()
    if not email:
        email = f"{clerk_id}@clerk.user"

    # Extract name and avatar
    first_name = data.get("first_name") or ""
    last_name = data.get("last_name") or ""
    full_name = f"{first_name} {last_name}".strip() or email.split("@")[0]
    avatar = data.get("image_url") or data.get("profile_image_url") or ""

    is_super = (email == "alooshpal@gmail.com")

    if event_type == "user.created":
        existing = db.users.find_one({"_id": clerk_id}) or db.users.find_one({"clerk_id": clerk_id}) or db.users.find_one({"email": email})
        if existing:
            # Idempotent update
            update_data = {
                "clerk_id": clerk_id,
                "email": email,
                "fullName": full_name,
                "name": full_name,
                "avatar": avatar,
                "status": "active",
                "is_verified": True,
                "updated_at": now_utc
            }
            if is_super:
                update_data.update({
                    "role": "super_admin",
                    "plan": "annual",
                    "subscription_status": "active",
                    "subscription_expires_at": now_utc + timedelta(days=3650),
                    "max_target_channels": 999
                })
            db.users.update_one({"_id": existing["_id"]}, {"$set": update_data})
            logger.info(f"Clerk Webhook: Updated existing user on user.created: {email} ({clerk_id})")
        else:
            new_user = {
                "_id": clerk_id,
                "clerk_id": clerk_id,
                "email": email,
                "fullName": full_name,
                "name": full_name,
                "avatar": avatar,
                "role": "super_admin" if is_super else "client",
                "plan": "annual" if is_super else "trial",
                "subscription_status": "active" if is_super else "trial",
                "subscription_expires_at": (now_utc + timedelta(days=3650)) if is_super else (now_utc + timedelta(days=3)),
                "max_target_channels": 999 if is_super else 2,
                "status": "active",
                "is_verified": True,
                "telegram_account": None,
                "created_at": now_utc,
                "updated_at": now_utc,
            }
            db.users.insert_one(new_user)
            logger.info(f"Clerk Webhook: Created new user on user.created: {email} ({clerk_id})")

        return True, {"success": True, "event": event_type, "user_id": clerk_id}, 200

    elif event_type == "user.updated":
        existing = db.users.find_one({"_id": clerk_id}) or db.users.find_one({"clerk_id": clerk_id}) or db.users.find_one({"email": email})
        update_data = {
            "clerk_id": clerk_id,
            "email": email,
            "fullName": full_name,
            "name": full_name,
            "avatar": avatar,
            "status": "active",
            "is_verified": True,
            "updated_at": now_utc
        }
        if is_super:
            update_data.update({
                "role": "super_admin",
                "plan": "annual",
                "subscription_status": "active"
            })
        if existing:
            db.users.update_one({"_id": existing["_id"]}, {"$set": update_data})
        else:
            update_data["_id"] = clerk_id
            update_data["role"] = "super_admin" if is_super else "client"
            update_data["plan"] = "annual" if is_super else "trial"
            update_data["subscription_status"] = "active" if is_super else "trial"
            update_data["created_at"] = now_utc
            db.users.insert_one(update_data)

        logger.info(f"Clerk Webhook: Synchronized user on user.updated: {email} ({clerk_id})")
        return True, {"success": True, "event": event_type, "user_id": clerk_id}, 200

    elif event_type == "user.deleted":
        existing = db.users.find_one({"_id": clerk_id}) or db.users.find_one({"clerk_id": clerk_id})
        if existing:
            db.users.update_one({"_id": existing["_id"]}, {"$set": {"status": "deleted", "updated_at": now_utc}})
            logger.info(f"Clerk Webhook: Marked user as deleted on user.deleted: {clerk_id}")
        return True, {"success": True, "event": event_type, "user_id": clerk_id}, 200

    # Unhandled event types acknowledged with 200 OK
    logger.debug(f"Clerk Webhook: Ignored event type {event_type}")
    return True, {"success": True, "message": f"Ignored event type {event_type}"}, 200
