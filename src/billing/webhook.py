"""
Automated Payment Webhook & Checkout Engine
-------------------------------------------
Handles:
- Secure HMAC-SHA256 signature verification
- Checkout order creation
- Instant zero-touch subscription activation on webhook confirmation
- Stacking & extension of active subscription periods
- Transaction ledger recording (pending -> completed/failed)
"""

import hashlib
import hmac
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

from src.billing.plans import calculate_new_expiration, get_plan

logger = logging.getLogger(__name__)


class WebhookEngine:
    """Automated Payment Webhook processor and transaction manager."""

    @staticmethod
    def get_webhook_secret() -> str:
        """Fetch configured webhook secret key from environment or config."""
        return os.environ.get("PAYMENT_WEBHOOK_SECRET") or os.environ.get("WEBHOOK_SECRET") or "default_secret_key_tg_pro_2026"

    @classmethod
    def verify_signature(cls, payload_bytes: bytes, signature: str, secret: Optional[str] = None) -> bool:
        """
        Verify HMAC-SHA256 signature of incoming webhook payload.
        Prevents tampering and unauthorized injection.
        """
        if not signature:
            return False
        secret_key = (secret or cls.get_webhook_secret()).encode("utf-8")
        expected = hmac.new(secret_key, payload_bytes, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected.lower(), signature.lower().strip())

    @classmethod
    def generate_signature(cls, payload_bytes: bytes, secret: Optional[str] = None) -> str:
        """Generate HMAC-SHA256 signature for test payloads and client verifications."""
        secret_key = (secret or cls.get_webhook_secret()).encode("utf-8")
        return hmac.new(secret_key, payload_bytes, hashlib.sha256).hexdigest()

    @staticmethod
    def create_checkout_order(
        db,
        user_id: str,
        plan_id: str,
        provider: str = "nowpayments",
        base_url: Optional[str] = None
    ) -> Tuple[bool, dict]:
        """
        Create a new pending transaction and generate a NOWPayments cryptocurrency invoice.
        """
        if not db or not user_id or not plan_id:
            return False, {"error": "Invalid checkout parameters"}

        plan = get_plan(plan_id)
        if not plan or plan["id"] == "trial":
            return False, {"error": "Invalid plan selected for purchase"}

        order_id = f"ORD-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"

        # 1. Create live NOWPayments Crypto Invoice
        invoice_url = None
        invoice_id = None
        from src.billing.nowpayments import NOWPaymentsGateway
        try:
            callback_url = f"{base_url.rstrip('/')}/api/v1/payments/nowpayments-webhook" if base_url else "https://telegram-forwarder-pro.onrender.com/api/v1/payments/nowpayments-webhook"
            success_url = f"{base_url.rstrip('/')}/?payment=success&order_id={order_id}" if base_url else "https://telegram-forwarder-pro.onrender.com/?payment=success"
            cancel_url = f"{base_url.rstrip('/')}/?payment=cancel" if base_url else "https://telegram-forwarder-pro.onrender.com/?payment=cancel"

            ok, inv_res = NOWPaymentsGateway.create_invoice(
                order_id=order_id,
                price_amount=float(plan["price_usd"]),
                price_currency="usd",
                plan_name=plan["name"],
                callback_url=callback_url,
                success_url=success_url,
                cancel_url=cancel_url
            )
            if ok:
                invoice_url = inv_res.get("invoice_url")
                invoice_id = inv_res.get("invoice_id")
        except Exception as e:
            logger.warning(f"NOWPayments direct invoice creation error (will fallback): {e}")

        tx_doc = {
            "_id": str(uuid.uuid4()),
            "order_id": order_id,
            "user_id": user_id,
            "plan_id": plan["id"],
            "plan_name": plan["name"],
            "amount": plan["price_usd"],
            "currency": "USD",
            "payment_provider": provider,
            "transaction_id": None,
            "invoice_id": invoice_id,
            "invoice_url": invoice_url,
            "status": "pending",
            "created_at": datetime.now(timezone.utc),
            "completed_at": None,
        }

        try:
            if hasattr(db, "transactions") and db.transactions is not None:
                db.transactions.insert_one(tx_doc)
            logger.info(f"Created checkout order {order_id} for user {user_id} (Plan: {plan['id']}, ${plan['price_usd']}, NOWPayments: {invoice_url or 'N/A'})")
            return True, {
                "order_id": order_id,
                "plan_id": plan["id"],
                "plan_name": plan["name"],
                "amount": plan["price_usd"],
                "currency": "USD",
                "payment_provider": provider,
                "invoice_id": invoice_id,
                "invoice_url": invoice_url,
                "checkout_url": invoice_url or f"/checkout/{order_id}",
            }
        except Exception as e:
            logger.error(f"Failed to create checkout transaction: {e}")
            return False, {"error": f"Failed to record transaction: {str(e)}"}

    @staticmethod
    def get_order_status(db, order_id: str) -> Optional[dict]:
        """Fetch current transaction status by order_id."""
        if not db or not order_id or not hasattr(db, "transactions") or db.transactions is None:
            return None
        return db.transactions.find_one({"order_id": order_id})

    @classmethod
    def process_webhook_payment(cls, db, payload: dict, raw_body: Optional[bytes] = None, signature: Optional[str] = None) -> Tuple[bool, dict]:
        """
        Process incoming payment confirmation from payment gateway (NOWPayments / Cryptomus / Webhook):
        1. Validates signature if present.
        2. Validates payment status is SUCCESS/COMPLETED/PAID/FINISHED/CONFIRMED.
        3. Identifies user and plan from transaction ledger.
        4. Calculates extended expiration and updates user record to 'active'.
        5. Marks transaction as 'completed'.
        """
        if not db:
            return False, {"error": "Database unavailable"}

        # 1. Verify signature if provided (HMAC-SHA512 for NOWPayments or HMAC-SHA256)
        if signature:
            from src.billing.nowpayments import NOWPaymentsGateway
            is_nowpayments_sig = NOWPaymentsGateway.verify_ipn_signature(payload, signature)
            is_standard_sig = raw_body and cls.verify_signature(raw_body, signature)
            if not is_nowpayments_sig and not is_standard_sig:
                # If neither matched, reject
                logger.warning("Rejected webhook: Invalid HMAC signature")
                return False, {"error": "Invalid signature"}

        order_id = payload.get("order_id") or payload.get("merchant_order_id") or payload.get("reference")
        payment_status = str(payload.get("payment_status") or payload.get("status") or "").upper()
        provider_tx_id = str(payload.get("payment_id") or payload.get("txid") or payload.get("transaction_id") or uuid.uuid4().hex[:12].upper())

        if not order_id:
            return False, {"error": "Missing order_id in webhook payload"}

        # 2. Check payment success state (NOWPayments uses 'finished', 'confirmed', 'sending', 'paid')
        success_states = ("SUCCESS", "PAID", "COMPLETED", "CONFIRMED", "FINISHED", "SENDING")
        if payment_status not in success_states:
            logger.info(f"Webhook received non-terminal status '{payment_status}' for order {order_id}")
            # Update tx status to pending/waiting in db
            if hasattr(db, "transactions") and db.transactions is not None:
                db.transactions.update_one({"order_id": order_id}, {"$set": {"status": payment_status.lower()}})
            return True, {"status": "ignored", "message": f"Payment status '{payment_status}' recorded"}

        # 3. Lookup transaction
        if not hasattr(db, "transactions") or db.transactions is None:
            return False, {"error": "Transactions store unavailable"}

        tx = db.transactions.find_one({"order_id": order_id})
        if not tx:
            # Fallback lookup by transaction_id
            tx = db.transactions.find_one({"transaction_id": provider_tx_id})

        if not tx:
            logger.warning(f"Webhook received for unknown order_id {order_id}")
            return False, {"error": f"Transaction for order {order_id} not found"}

        if tx.get("status") == "completed":
            # Idempotent response
            return True, {
                "status": "success",
                "message": "Subscription already activated for this order",
                "already_completed": True
            }

        user_id = tx.get("user_id")
        plan_id = tx.get("plan_id")
        plan = get_plan(plan_id)
        if not plan:
            return False, {"error": f"Invalid plan {plan_id} associated with transaction"}

        # 4. Fetch User and calculate new expiration
        user = db.users.find_one({"_id": user_id})
        if not user:
            return False, {"error": f"User {user_id} not found"}

        current_expires_at = user.get("subscription_expires_at")
        if isinstance(current_expires_at, str):
            try:
                current_expires_at = datetime.fromisoformat(current_expires_at.replace("Z", "+00:00"))
            except Exception:
                current_expires_at = None

        new_expires_at = calculate_new_expiration(current_expires_at, plan["duration_days"])

        # 5. Update user to active status
        db.users.update_one(
            {"_id": user_id},
            {
                "$set": {
                    "subscription_status": "active",
                    "plan": plan["id"],
                    "subscription_expires_at": new_expires_at,
                    "max_target_channels": plan.get("max_target_channels", 999),
                    "updated_at": datetime.now(timezone.utc),
                }
            }
        )

        # 6. Mark transaction completed
        db.transactions.update_one(
            {"_id": tx["_id"]},
            {
                "$set": {
                    "status": "completed",
                    "transaction_id": provider_tx_id,
                    "completed_at": datetime.now(timezone.utc),
                }
            }
        )

        # Log activation
        if hasattr(db, "logs"):
            try:
                db.logs.insert_one({
                    "timestamp": datetime.now(timezone.utc),
                    "user_id": user_id,
                    "level": "INFO",
                    "message": f"🎉 Automated Payment Webhook: Subscription activated for {user.get('email')} (Plan: {plan['name']}, Expires: {new_expires_at.strftime('%Y-%m-%d %H:%M:%S UTC')})"
                })
            except Exception:
                pass

        logger.info(f"✅ Subscription activated via Webhook for user {user_id} ({user.get('email')}) until {new_expires_at.isoformat()}")
        return True, {
            "status": "success",
            "message": "Subscription activated automatically",
            "user_id": user_id,
            "plan_id": plan["id"],
            "expires_at": new_expires_at.isoformat(),
        }
