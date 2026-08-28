"""
Billing & Subscription Plans Definition
---------------------------------------
Defines available subscription plans, durations, pricing, and feature limits:
- Weekly: 7 days - $5.00
- Monthly: 30 days - $15.00
- Quarterly: 90 days - $35.00
- Semi-Annual: 180 days - $65.00
- Annual: 365 days - $110.00
- Trial: 3 days (Free upon registration, max 2 target channels)
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple

PLANS = {
    "weekly": {
        "id": "weekly",
        "name": "Weekly Plan",
        "name_ar": "باقة أسبوعية",
        "duration_days": 7,
        "price_usd": 5.00,
        "max_target_channels": 999,  # Unlimited
        "unlimited_rules": True,
        "fast_forwarding": True,
        "description": "7 Days full access with unlimited channels and instant forwarding.",
        "description_ar": "وصول كامل لمدة 7 أيام مع قنوات غير محدودة وبث لحظي.",
    },
    "monthly": {
        "id": "monthly",
        "name": "Monthly Plan",
        "name_ar": "باقة شهرية",
        "duration_days": 30,
        "price_usd": 15.00,
        "max_target_channels": 999,
        "unlimited_rules": True,
        "fast_forwarding": True,
        "description": "30 Days full access with all enterprise features included.",
        "description_ar": "وصول كامل لمدة 30 يوماً مع كافة ميزات المنصة المتقدمة.",
    },
    "quarterly": {
        "id": "quarterly",
        "name": "3 Months Plan",
        "name_ar": "باقة 3 أشهر",
        "duration_days": 90,
        "price_usd": 35.00,
        "max_target_channels": 999,
        "unlimited_rules": True,
        "fast_forwarding": True,
        "description": "90 Days full access with save-more pricing.",
        "description_ar": "وصول كامل لمدة 90 يوماً مع توفير ملحوظ في التكلفة.",
    },
    "semi_annual": {
        "id": "semi_annual",
        "name": "6 Months Plan",
        "name_ar": "باقة 6 أشهر",
        "duration_days": 180,
        "price_usd": 65.00,
        "max_target_channels": 999,
        "unlimited_rules": True,
        "fast_forwarding": True,
        "description": "180 Days full access with priority speed and support.",
        "description_ar": "وصول كامل لمدة 180 يوماً مع أولوية في السرعة والدعم.",
    },
    "annual": {
        "id": "annual",
        "name": "Annual Plan",
        "name_ar": "باقة سنوية",
        "duration_days": 365,
        "price_usd": 110.00,
        "max_target_channels": 999,
        "unlimited_rules": True,
        "fast_forwarding": True,
        "description": "365 Days complete uninterrupted forwarding access.",
        "description_ar": "وصول كامل وشامل لسنة كاملة (365 يوم) دون أي انقطاع.",
    },
    "trial": {
        "id": "trial",
        "name": "Free Trial",
        "name_ar": "فترة تجريبية",
        "duration_days": 3,
        "price_usd": 0.00,
        "max_target_channels": 2,
        "unlimited_rules": False,
        "fast_forwarding": True,
        "description": "3 Days automatic trial with max 2 target channels limit.",
        "description_ar": "تجربة مجانية تلقائية لـ 3 أيام بحد أقصى قناتين هدف.",
    }
}


def get_plan(plan_id: str) -> Optional[dict]:
    """Retrieve plan configuration by ID."""
    return PLANS.get(plan_id.lower().strip()) if plan_id else None


def calculate_new_expiration(current_expires_at: Optional[datetime], duration_days: int) -> datetime:
    """
    Calculate new expiration date:
    - If user currently has an active subscription in the future, stack/extend from current_expires_at.
    - Otherwise, start from current UTC now + duration_days.
    """
    now = datetime.now(timezone.utc)
    if current_expires_at:
        # Ensure current_expires_at has timezone
        if current_expires_at.tzinfo is None:
            current_expires_at = current_expires_at.replace(tzinfo=timezone.utc)
        if current_expires_at > now:
            return current_expires_at + timedelta(days=duration_days)

    return now + timedelta(days=duration_days)


def check_subscription_status(user: dict) -> Tuple[str, bool, Optional[datetime], int]:
    """
    Evaluate user subscription status:
    Returns (status: 'trial'|'active'|'expired', is_active: bool, expires_at: datetime, days_remaining: int)
    """
    if not user:
        return "expired", False, None, 0

    role = user.get("role", "client")
    if role == "super_admin":
        return "active", True, datetime(2099, 12, 31, tzinfo=timezone.utc), 9999

    expires_at = user.get("subscription_expires_at")
    if isinstance(expires_at, str):
        try:
            expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        except Exception:
            expires_at = None

    now = datetime.now(timezone.utc)
    if not expires_at:
        return "expired", False, None, 0

    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at > now:
        days_left = (expires_at - now).days
        status = user.get("subscription_status", "active")
        if status == "trial":
            return "trial", True, expires_at, max(0, days_left)
        return "active", True, expires_at, max(0, days_left)

    return "expired", False, expires_at, 0
