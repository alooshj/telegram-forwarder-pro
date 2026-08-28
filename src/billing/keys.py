"""License key generation, validation, and redemption module.

Allows Super Admins and Admins to generate activation keys (license codes)
and enables clients/public users to redeem them manually.
"""

import uuid
import secrets
import string
from datetime import datetime, timezone
from src.billing.plans import PLANS, get_plan, calculate_new_expiration


def _generate_clean_code(prefix: str = "ACT") -> str:
    """Generate human-readable license key format: ACT-XXXX-XXXX-XXXX."""
    chars = string.ascii_uppercase + string.digits
    clean_chars = "".join([c for c in chars if c not in "0O1I"])
    p1 = "".join(secrets.choice(clean_chars) for _ in range(4))
    p2 = "".join(secrets.choice(clean_chars) for _ in range(4))
    p3 = "".join(secrets.choice(clean_chars) for _ in range(4))
    return f"{prefix}-{p1}-{p2}-{p3}"


class LicenseKeyManager:
    """Manager for admin activation codes / license keys."""

    @staticmethod
    def _get_col(db, col_name: str):
        if hasattr(db, col_name):
            return getattr(db, col_name)
        if hasattr(db, "db"):
            if hasattr(db.db, col_name):
                return getattr(db.db, col_name)
            try:
                return db.db[col_name]
            except Exception:
                pass
        try:
            return db[col_name]
        except Exception:
            return None

    @classmethod
    def generate_key(cls, db, plan_id: str, created_by: str, notes: str = "", custom_days: int = None) -> dict:
        """Generate a new license key with designated duration."""
        keys_col = cls._get_col(db, "license_keys")
        if keys_col is None:
            raise RuntimeError("Database collection 'license_keys' is not available")

        plan_cfg = get_plan(plan_id)
        if not plan_cfg and not custom_days:
            raise ValueError(f"Invalid plan ID: {plan_id}")

        duration_days = int(custom_days) if custom_days else plan_cfg["duration_days"]
        plan_name = plan_cfg.get("name", "Custom Plan") if plan_cfg else f"{duration_days} Days Plan"

        key_code = _generate_clean_code()
        key_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        key_doc = {
            "_id": key_id,
            "key_code": key_code,
            "plan_id": plan_id,
            "plan_name": plan_name,
            "duration_days": duration_days,
            "created_by": created_by,
            "is_redeemed": False,
            "redeemed_by": None,
            "redeemed_at": None,
            "created_at": now,
            "notes": notes.strip()
        }

        keys_col.insert_one(key_doc)
        return key_doc

    @classmethod
    def redeem_key(cls, db, user_id: str, key_code: str) -> tuple:
        """Redeem a license key for a user and stack subscription expiration."""
        keys_col = cls._get_col(db, "license_keys")
        users_col = cls._get_col(db, "users")
        if keys_col is None or users_col is None or not user_id or not key_code:
            return False, "Invalid redemption parameters", {}

        clean_code = key_code.strip().upper()
        key_doc = keys_col.find_one({"key_code": clean_code})

        if not key_doc:
            return False, "كود التفعيل غير صالح أو غير موجود (Invalid Code)", {}

        if key_doc.get("is_redeemed"):
            return False, "تم استخدام كود التفعيل هذا مسبقاً (Code Already Redeemed)", {}

        user = users_col.find_one({"_id": user_id})
        if not user:
            return False, "المستخدم غير موجود (User Not Found)", {}

        now = datetime.now(timezone.utc)
        duration_days = key_doc.get("duration_days", 30)
        plan_id = key_doc.get("plan_id", "monthly")

        current_exp = user.get("subscription_expires_at")
        new_expires_at = calculate_new_expiration(current_exp, duration_days)

        users_col.update_one(
            {"_id": user_id},
            {"$set": {
                "subscription_status": "active",
                "subscription_expires_at": new_expires_at,
                "plan": plan_id,
                "max_target_channels": 999,
                "is_frozen": False,
                "frozen_reason": "",
                "updated_at": now
            }}
        )

        keys_col.update_one(
            {"_id": key_doc["_id"]},
            {"$set": {
                "is_redeemed": True,
                "redeemed_by": user.get("email", user_id),
                "redeemed_at": now
            }}
        )

        from src.web.auth import UserManager
        updated_sub = UserManager.get_subscription_info(db, user_id)

        msg = f"تم تفعيل الكود بنجاح وتمديد اشتراكك لمدة {duration_days} يوماً بنجاح!"
        return True, msg, updated_sub

    @classmethod
    def list_keys(cls, db, limit: int = 100) -> list:
        """List generated license keys ordered by creation date."""
        keys_col = cls._get_col(db, "license_keys")
        if keys_col is None:
            return []

        cursor = keys_col.find({}).sort("created_at", -1).limit(limit)
        results = []
        for k in cursor:
            created_at_val = k.get("created_at")
            redeemed_at_val = k.get("redeemed_at")
            results.append({
                "id": str(k["_id"]),
                "key_code": k.get("key_code"),
                "plan_id": k.get("plan_id"),
                "plan_name": k.get("plan_name"),
                "duration_days": k.get("duration_days"),
                "created_by": k.get("created_by"),
                "is_redeemed": bool(k.get("is_redeemed")),
                "redeemed_by": k.get("redeemed_by"),
                "redeemed_at": redeemed_at_val.isoformat() if hasattr(redeemed_at_val, "isoformat") else str(redeemed_at_val) if redeemed_at_val else None,
                "created_at": created_at_val.isoformat() if hasattr(created_at_val, "isoformat") else str(created_at_val) if created_at_val else None,
                "notes": k.get("notes", "")
            })
        return results

    @classmethod
    def delete_key(cls, db, key_id: str) -> bool:
        """Delete an unredeemed license key."""
        keys_col = cls._get_col(db, "license_keys")
        if keys_col is None:
            return False
        keys_col.delete_one({"_id": key_id})
        return True

