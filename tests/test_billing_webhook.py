"""
Tests for Automated Webhook Activation Engine, Subscriptions, and Role Hierarchy
"""

import hashlib
import hmac
import json
import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import tests.conftest  # noqa: F401
from src.billing.expiration import SubscriptionExpirationWorker
from src.billing.plans import PLANS, calculate_new_expiration, check_subscription_status, get_plan
from src.billing.webhook import WebhookEngine
from src.utils.database import SQLiteDB
from src.web.api import app, get_db
from src.web.auth import UserManager, generate_auth_token


class BillingWebhookTestCase(unittest.TestCase):
    def setUp(self):
        self.db = SQLiteDB(":memory:")
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_plans_pricing_and_durations(self):
        """Verify all 5 plans exist with exact required durations and pricing."""
        self.assertEqual(PLANS["weekly"]["duration_days"], 7)
        self.assertEqual(PLANS["weekly"]["price_usd"], 5.00)

        self.assertEqual(PLANS["monthly"]["duration_days"], 30)
        self.assertEqual(PLANS["monthly"]["price_usd"], 15.00)

        self.assertEqual(PLANS["quarterly"]["duration_days"], 90)
        self.assertEqual(PLANS["quarterly"]["price_usd"], 35.00)

        self.assertEqual(PLANS["semi_annual"]["duration_days"], 180)
        self.assertEqual(PLANS["semi_annual"]["price_usd"], 65.00)

        self.assertEqual(PLANS["annual"]["duration_days"], 365)
        self.assertEqual(PLANS["annual"]["price_usd"], 110.00)

        self.assertEqual(PLANS["trial"]["duration_days"], 3)
        self.assertEqual(PLANS["trial"]["max_target_channels"], 2)

    def test_calculate_new_expiration_stacking(self):
        """Verify that extending an active future subscription stacks on top of it."""
        now = datetime.now(timezone.utc)
        future_date = now + timedelta(days=15)
        new_date = calculate_new_expiration(future_date, 30)
        # Should be approximately 45 days from now
        self.assertAlmostEqual((new_date - now).total_seconds(), 45 * 86400, delta=10)

        # If already expired, should start from now + duration
        past_date = now - timedelta(days=5)
        new_date_from_past = calculate_new_expiration(past_date, 30)
        self.assertAlmostEqual((new_date_from_past - now).total_seconds(), 30 * 86400, delta=10)

    def test_user_creation_automatic_trial_and_superadmin(self):
        """First user is super_admin, subsequent users get 3-day automatic trial."""
        # 1st user -> super_admin
        admin = UserManager.create_user(self.db, "admin@test.com", "pass123")
        self.assertEqual(admin["role"], "super_admin")
        self.assertEqual(admin["subscription_status"], "active")

        # 2nd user -> client with 3-day trial
        client = UserManager.create_user(self.db, "client@test.com", "pass123")
        self.assertEqual(client["role"], "client")
        self.assertEqual(client["subscription_status"], "trial")
        self.assertEqual(client["max_target_channels"], 2)

        info = UserManager.get_subscription_info(self.db, client["_id"])
        self.assertTrue(info["is_active"])
        self.assertEqual(info["status"], "trial")
        self.assertGreaterEqual(info["days_remaining"], 2)

    def test_designated_super_admin_email(self):
        """alooshpal@gmail.com is always super_admin even if created after other users."""
        # Create a regular user first
        UserManager.create_user(self.db, "first@test.com", "pass123")

        # Create designated super admin
        sa = UserManager.create_user(self.db, "alooshpal@gmail.com", "my_secure_pass")
        self.assertEqual(sa["role"], "super_admin")
        self.assertEqual(sa["subscription_status"], "active")
        self.assertEqual(sa["max_target_channels"], 999)

        info = UserManager.get_subscription_info(self.db, sa["_id"])
        self.assertEqual(info["role"], "super_admin")
        self.assertTrue(info["is_active"])

    def test_create_checkout_order(self):
        """Test checkout order creation with transaction ledger."""
        user = UserManager.create_user(self.db, "payer@test.com", "pass123")
        success, checkout = WebhookEngine.create_checkout_order(self.db, user["_id"], "monthly")
        self.assertTrue(success)
        self.assertIn("ORD-", checkout["order_id"])
        self.assertEqual(checkout["amount"], 15.00)
        self.assertEqual(checkout["plan_id"], "monthly")

        # Verify record in DB
        tx = self.db.transactions.find_one({"order_id": checkout["order_id"]})
        self.assertIsNotNone(tx)
        self.assertEqual(tx["status"], "pending")

    def test_webhook_hmac_signature_verification(self):
        """Test HMAC-SHA256 signature verification."""
        secret = "super_secret_webhook_key_2026"
        payload_bytes = b'{"order_id":"ORD-123","status":"COMPLETED"}'

        # Valid signature
        valid_sig = WebhookEngine.generate_signature(payload_bytes, secret=secret)
        self.assertTrue(WebhookEngine.verify_signature(payload_bytes, valid_sig, secret=secret))

        # Invalid signature
        invalid_sig = "a" * 64
        self.assertFalse(WebhookEngine.verify_signature(payload_bytes, invalid_sig, secret=secret))

    def test_webhook_automatic_subscription_activation(self):
        """Test automated webhook zero-touch account activation."""
        user = UserManager.create_user(self.db, "customer@test.com", "pass123")
        user_id = str(user["_id"])

        # Create checkout order
        success, checkout = WebhookEngine.create_checkout_order(self.db, user_id, "monthly")
        self.assertTrue(success)
        order_id = checkout["order_id"]

        # Simulate Webhook confirmation payload
        webhook_payload = {
            "order_id": order_id,
            "status": "COMPLETED",
            "transaction_id": "CRYPTO-TX-998877"
        }
        body_bytes = json.dumps(webhook_payload).encode("utf-8")
        secret = WebhookEngine.get_webhook_secret()
        sig = WebhookEngine.generate_signature(body_bytes, secret)

        # Process Webhook
        ok, res = WebhookEngine.process_webhook_payment(
            self.db, webhook_payload, raw_body=body_bytes, signature=sig
        )
        self.assertTrue(ok)
        self.assertEqual(res["status"], "success")

        # Verify user is now active with 30 days
        user_updated = self.db.users.find_one({"_id": user_id})
        self.assertEqual(user_updated["subscription_status"], "active")
        self.assertEqual(user_updated["plan"], "monthly")

        # Verify transaction marked completed
        tx = self.db.transactions.find_one({"order_id": order_id})
        self.assertEqual(tx["status"], "completed")
        self.assertEqual(tx["transaction_id"], "CRYPTO-TX-998877")

    def test_webhook_idempotency(self):
        """Duplicate webhook deliveries for same order return success without re-extending."""
        user = UserManager.create_user(self.db, "idempotent@test.com", "pass123")
        _, checkout = WebhookEngine.create_checkout_order(self.db, user["_id"], "monthly")
        payload = {"order_id": checkout["order_id"], "status": "COMPLETED"}
        raw_body = json.dumps(payload).encode("utf-8")
        sig = WebhookEngine.generate_signature(raw_body)

        # 1st processing
        ok1, res1 = WebhookEngine.process_webhook_payment(self.db, payload, raw_body=raw_body, signature=sig)
        self.assertTrue(ok1)

        # 2nd processing
        ok2, res2 = WebhookEngine.process_webhook_payment(self.db, payload, raw_body=raw_body, signature=sig)
        self.assertTrue(ok2)
        self.assertTrue(res2.get("already_completed"))

    def test_api_plans_and_subscription_endpoints(self):
        """Test GET /api/v1/plans and GET /api/v1/user/subscription."""
        # Create user
        user = UserManager.create_user(self.db, "api_sub_test@test.com", "pass123", role="client")
        token = generate_auth_token(user["_id"], user["email"])

        with patch("src.web.api.get_db", return_value=self.db):
            # Test GET /api/v1/plans
            resp = self.client.get("/api/v1/plans")
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            self.assertTrue(data["success"])
            self.assertGreaterEqual(len(data["plans"]), 5)

            # Test GET /api/v1/user/subscription
            resp = self.client.get("/api/v1/user/subscription", headers={"Authorization": f"Bearer {token}"})
            self.assertEqual(resp.status_code, 200)
            sub = resp.get_json()["subscription"]
            self.assertTrue(sub["is_active"])
            self.assertEqual(sub["status"], "trial")

    def test_api_checkout_and_polling_status(self):
        """Test POST /api/v1/payments/create-checkout and GET /api/v1/payments/check-status/<order_id>."""
        user = UserManager.create_user(self.db, "polling_user@test.com", "pass123", role="client")
        token = generate_auth_token(user["_id"], user["email"])

        with patch("src.web.api.get_db", return_value=self.db):
            # Create checkout
            resp = self.client.post(
                "/api/v1/payments/create-checkout",
                headers={"Authorization": f"Bearer {token}"},
                json={"plan_id": "quarterly"}
            )
            self.assertEqual(resp.status_code, 200)
            order_id = resp.get_json()["checkout"]["order_id"]

            # Poll status (pending)
            resp_poll = self.client.get(
                f"/api/v1/payments/check-status/{order_id}",
                headers={"Authorization": f"Bearer {token}"}
            )
            self.assertEqual(resp_poll.status_code, 200)
            self.assertEqual(resp_poll.get_json()["status"], "pending")
            self.assertFalse(resp_poll.get_json()["is_completed"])

            # Simulate payment confirmation
            resp_sim = self.client.post(
                "/api/v1/payments/simulate-success",
                headers={"Authorization": f"Bearer {token}"},
                json={"order_id": order_id}
            )
            self.assertEqual(resp_sim.status_code, 200)

            # Poll status again (completed!)
            resp_poll2 = self.client.get(
                f"/api/v1/payments/check-status/{order_id}",
                headers={"Authorization": f"Bearer {token}"}
            )
            self.assertTrue(resp_poll2.get_json()["is_completed"])
            self.assertEqual(resp_poll2.get_json()["subscription"]["status"], "active")
            self.assertEqual(resp_poll2.get_json()["subscription"]["plan"], "quarterly")

    def test_subscription_expiration_worker(self):
        """Test that expiration worker flags expired accounts and halts workers."""
        now = datetime.now(timezone.utc)
        # Create an expired client user
        user = UserManager.create_user(self.db, "expired_client@test.com", "pass123", role="client")
        self.db.users.update_one(
            {"_id": user["_id"]},
            {"$set": {"subscription_expires_at": now - timedelta(hours=2), "subscription_status": "trial"}}
        )

        worker = SubscriptionExpirationWorker()
        worker.db_getter = lambda: self.db

        with patch("src.forwarder.worker_pool.worker_pool.stop_user_worker") as mock_stop:
            expired_count = worker.check_and_expire_subscriptions()
            self.assertEqual(expired_count, 1)
            mock_stop.assert_called_with(str(user["_id"]))

        # Verify DB status updated to 'expired'
        updated = self.db.users.find_one({"_id": user["_id"]})
        self.assertEqual(updated["subscription_status"], "expired")

    def test_trial_channel_limit_enforcement(self):
        """Trial plan cannot add > 2 target channels per rule."""
        user = UserManager.create_user(self.db, "trial_limiter@test.com", "pass123", role="client")
        token = generate_auth_token(user["_id"], user["email"])

        with patch("src.web.api.get_db", return_value=self.db):
            # Attempt creating rule with 3 targets on trial plan -> 400 Bad Request / Plan Limit
            resp = self.client.post(
                "/api/rules",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "name": "Over Limit Rule",
                    "source_id": "@source",
                    "target_id": "@t1, @t2, @t3",
                }
            )
            self.assertEqual(resp.status_code, 400)
            self.assertIn("Plan Limit", resp.get_json()["error"])

            # Rule with 2 targets -> 200 OK
            resp_ok = self.client.post(
                "/api/rules",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "name": "Valid Trial Rule",
                    "source_id": "@source",
                    "target_id": "@t1, @t2",
                }
            )
            self.assertEqual(resp_ok.status_code, 200)

    def test_expired_user_forwarder_start_blocked(self):
        """Expired user cannot start forwarder engine."""
        user = UserManager.create_user(self.db, "blocked_expired@test.com", "pass123", role="client")
        # Expire user
        self.db.users.update_one(
            {"_id": user["_id"]},
            {"$set": {"subscription_status": "expired", "subscription_expires_at": datetime.now(timezone.utc) - timedelta(days=1)}}
        )
        token = generate_auth_token(user["_id"], user["email"])

        with patch("src.web.api.get_db", return_value=self.db):
            resp = self.client.post(
                "/api/forward/start",
                headers={"Authorization": f"Bearer {token}"}
            )
            self.assertEqual(resp.status_code, 403)
            self.assertIn("expired", resp.get_json()["error"])

    def test_license_key_generation_and_manual_redemption(self):
        """Test license key generation by admin and manual redemption by client."""
        from src.billing.keys import LicenseKeyManager
        # Admin generates a 30-day monthly key
        key_doc = LicenseKeyManager.generate_key(self.db, "monthly", "admin@test.com", notes="VIP Customer")
        self.assertTrue(key_doc["key_code"].startswith("ACT-"))
        self.assertEqual(key_doc["duration_days"], 30)

        # Client redeems code via POST /api/v1/user/redeem-code
        client = UserManager.create_user(self.db, "redeemer@test.com", "pass123", role="client")
        token = generate_auth_token(client["_id"], client["email"])

        with patch("src.web.api.get_db", return_value=self.db):
            resp = self.client.post(
                "/api/v1/user/redeem-code",
                headers={"Authorization": f"Bearer {token}"},
                json={"code": key_doc["key_code"]}
            )
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            self.assertTrue(data["success"])
            self.assertEqual(data["subscription"]["status"], "active")

            # Verify key cannot be redeemed twice
            resp_dup = self.client.post(
                "/api/v1/user/redeem-code",
                headers={"Authorization": f"Bearer {token}"},
                json={"code": key_doc["key_code"]}
            )
            self.assertEqual(resp_dup.status_code, 400)
            self.assertIn("مسبقاً", resp_dup.get_json()["error"])

    def test_admin_freeze_user_and_block_forwarding(self):
        """Test admin freezing a user account and blocking forwarding."""
        admin = UserManager.create_user(self.db, "super_admin_freeze@test.com", "pass123", role="super_admin")
        admin_token = generate_auth_token(admin["_id"], admin["email"])

        client = UserManager.create_user(self.db, "bad_client@test.com", "pass123", role="client")
        client_token = generate_auth_token(client["_id"], client["email"])

        with patch("src.web.api.get_db", return_value=self.db):
            # Admin freezes client
            resp = self.client.post(
                f"/api/v1/admin/users/{client['_id']}/freeze",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={"freeze": True, "reason": "Violation of terms"}
            )
            self.assertEqual(resp.status_code, 200)
            self.assertTrue(resp.get_json()["is_frozen"])

            # Verify frozen status in get_subscription_info
            info = UserManager.get_subscription_info(self.db, client["_id"])
            self.assertTrue(info["is_frozen"])
            self.assertFalse(info["is_active"])

            # Client starting forwarder is blocked
            resp_start = self.client.post(
                "/api/forward/start",
                headers={"Authorization": f"Bearer {client_token}"}
            )
            self.assertEqual(resp_start.status_code, 403)

            # Admin unfreezes client
            resp_unfreeze = self.client.post(
                f"/api/v1/admin/users/{client['_id']}/freeze",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={"freeze": False}
            )
            self.assertEqual(resp_unfreeze.status_code, 200)
            self.assertFalse(resp_unfreeze.get_json()["is_frozen"])

    def test_admin_role_change_and_keys_crud(self):
        """Test Super Admin role elevation and License Keys CRUD endpoints."""
        super_admin = UserManager.create_user(self.db, "sa_role_test@test.com", "pass123", role="super_admin")
        sa_token = generate_auth_token(super_admin["_id"], super_admin["email"])

        client = UserManager.create_user(self.db, "promoted_client@test.com", "pass123", role="client")

        with patch("src.web.api.get_db", return_value=self.db):
            # Change role to admin
            resp_role = self.client.post(
                f"/api/v1/admin/users/{client['_id']}/role",
                headers={"Authorization": f"Bearer {sa_token}"},
                json={"role": "admin"}
            )
            self.assertEqual(resp_role.status_code, 200)
            self.assertEqual(resp_role.get_json()["role"], "admin")

            # Generate key via API
            resp_key = self.client.post(
                "/api/v1/admin/keys/generate",
                headers={"Authorization": f"Bearer {sa_token}"},
                json={"plan_id": "annual", "notes": "VIP Year Key"}
            )
            self.assertEqual(resp_key.status_code, 200)
            key_code = resp_key.get_json()["key"]["key_code"]

            # List keys
            resp_list = self.client.get(
                "/api/v1/admin/keys",
                headers={"Authorization": f"Bearer {sa_token}"}
            )
            self.assertEqual(resp_list.status_code, 200)
            keys = resp_list.get_json()["keys"]
            self.assertTrue(any(k["key_code"] == key_code for k in keys))

    def test_nowpayments_signature_verification(self):
        """Test NOWPayments HMAC-SHA512 signature verification on sorted JSON payload."""
        from src.billing.nowpayments import NOWPaymentsGateway
        secret = "c37ecbc1-6a5a-4e56-917b-3c77672a812b"
        payload = {
            "payment_id": 123456789,
            "payment_status": "finished",
            "pay_amount": 15.0,
            "price_amount": 15.0,
            "price_currency": "usd",
            "order_id": "ORD-20260828-TEST"
        }
        # Compute signature
        sorted_json = json.dumps(payload, separators=(',', ':'), sort_keys=True)
        sig = hmac.new(secret.encode("utf-8"), sorted_json.encode("utf-8"), hashlib.sha512).hexdigest()

        # Valid
        self.assertTrue(NOWPaymentsGateway.verify_ipn_signature(payload, sig, secret))
        # Invalid
        self.assertFalse(NOWPaymentsGateway.verify_ipn_signature(payload, "invalid_signature", secret))

    def test_nowpayments_checkout_and_ipn_activation(self):
        """Test full NOWPayments checkout creation and automated IPN webhook activation."""
        user = UserManager.create_user(self.db, "crypto_buyer@test.com", "pass123", role="client")
        token = generate_auth_token(user["_id"], user["email"])

        with patch("src.web.api.get_db", return_value=self.db), \
             patch("src.billing.nowpayments.NOWPaymentsGateway.create_invoice", return_value=(True, {
                 "invoice_id": "998877",
                 "invoice_url": "https://nowpayments.io/payment/?iid=998877",
                 "order_id": "ORD-TEST-123"
             })):

            # 1. User initiates checkout
            resp = self.client.post(
                "/api/v1/payments/create-checkout",
                headers={"Authorization": f"Bearer {token}"},
                json={"plan_id": "quarterly"}
            )
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            self.assertTrue(data["success"])
            order_id = data["checkout"]["order_id"]
            self.assertEqual(data["checkout"]["invoice_url"], "https://nowpayments.io/payment/?iid=998877")

            # 2. NOWPayments sends IPN Webhook callback with status 'finished'
            ipn_payload = {
                "payment_id": 55443322,
                "payment_status": "finished",
                "pay_amount": 35.0,
                "price_amount": 35.0,
                "price_currency": "usd",
                "order_id": order_id
            }
            secret = "c37ecbc1-6a5a-4e56-917b-3c77672a812b"
            sorted_json = json.dumps(ipn_payload, separators=(',', ':'), sort_keys=True)
            sig = hmac.new(secret.encode("utf-8"), sorted_json.encode("utf-8"), hashlib.sha512).hexdigest()

            ipn_resp = self.client.post(
                "/api/v1/payments/nowpayments-webhook",
                headers={"x-nowpayments-sig": sig, "Content-Type": "application/json"},
                data=json.dumps(ipn_payload)
            )
            self.assertEqual(ipn_resp.status_code, 200)
            self.assertEqual(ipn_resp.get_json()["status"], "success")

            # 3. Verify user subscription is now active with 90 days quarterly plan
            info = UserManager.get_subscription_info(self.db, user["_id"])
            self.assertTrue(info["is_active"])
            self.assertEqual(info["plan"], "quarterly")
            self.assertGreaterEqual(info["days_remaining"], 89)


if __name__ == "__main__":
    unittest.main()


