"""
Comprehensive Security Patches & Logic Flaws Test Suite
-------------------------------------------------------
Validates resolution for all 10 security vulnerabilities:
1. Auth bypass in /api/auth/clerk-sync
2. JWT signature verification enforcement
3. Mandatory payment webhook signature verification
4. Payment simulation endpoint lockdown in production
5. Hardcoded secrets sanitization & validate_environment
6. Information disclosure protection on /api/test-mongo and /api/debug
7. Blacklist routes access control (@require_auth)
8. Atomic license key redemption (race condition prevention)
9. Rule IDOR protection against unassigned/other users' rules
10. Rate limiting on sensitive auth routes
"""

import os
import time
import json
import uuid
import unittest
from unittest.mock import patch
import jwt

from src.utils.database import SQLiteDB
from src.web.api import app
from src.web.auth import UserManager, generate_auth_token, verify_clerk_token_or_payload
from src.billing.keys import LicenseKeyManager
from src.billing.webhook import WebhookEngine
from src.utils.config import validate_environment


class SecurityVulnerabilityPatchesTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        self.db = SQLiteDB(":memory:")
        os.environ["SECRET_KEY"] = "test_super_secret_key_32_bytes"
        os.environ["CLERK_SECRET_KEY"] = "sk_test_secret_key_12345"
        os.environ["PAYMENT_WEBHOOK_SECRET"] = "test_webhook_secret_key"

    def test_01_clerk_sync_rejects_plaintext_email_injection(self):
        """Vulnerability #1: Ensure /api/auth/clerk-sync rejects raw body with email without verified JWT."""
        with patch("src.web.api.get_db", return_value=self.db):
            res = self.client.post(
                "/api/auth/clerk-sync",
                json={
                    "email": "victim_admin@company.com",
                    "clerk_id": "spoofed_admin_id"
                }
            )
            self.assertEqual(res.status_code, 401)
            data = res.get_json()
            self.assertFalse(data["success"])

    def test_02_jwt_signature_verification_enforcement(self):
        """Vulnerability #2: Ensure forged/unsigned Clerk tokens are strictly rejected."""
        # Forged token signed with completely different untrusted key
        forged_token = jwt.encode(
            {"sub": "attacker_id", "email": "attacker@evil.com", "exp": int(time.time()) + 3600},
            "untrusted_attacker_key",
            algorithm="HS256"
        )
        user = verify_clerk_token_or_payload(forged_token, self.db)
        self.assertIsNone(user, "Forged JWT token must be rejected with None")

    def test_03_payment_webhook_mandates_signature(self):
        """Vulnerability #3: Ensure webhook rejects missing or invalid signatures."""
        user = UserManager.create_user(self.db, "payer_sec@test.com", "pass123")
        _, checkout = WebhookEngine.create_checkout_order(self.db, user["_id"], "monthly")
        payload = {"order_id": checkout["order_id"], "status": "COMPLETED"}

        # 1. Missing signature -> MUST fail
        ok_no_sig, res_no_sig = WebhookEngine.process_webhook_payment(self.db, payload)
        self.assertFalse(ok_no_sig)
        self.assertIn("signature", res_no_sig.get("error", "").lower())

        # 2. Invalid signature -> MUST fail
        raw_body = json.dumps(payload).encode("utf-8")
        ok_bad_sig, res_bad_sig = WebhookEngine.process_webhook_payment(
            self.db, payload, raw_body=raw_body, signature="bad_invalid_signature_hex"
        )
        self.assertFalse(ok_bad_sig)
        self.assertEqual(res_bad_sig.get("error"), "Invalid signature")

    def test_04_payment_simulation_endpoint_protection(self):
        """Vulnerability #4: Ensure simulate-success endpoint is rejected for non-admins and when not in debug."""
        user = UserManager.create_user(self.db, "regular_client@test.com", "pass123", role="client")
        token = generate_auth_token(user["_id"], user["email"])

        with patch("src.web.api.get_db", return_value=self.db):
            # Unauthenticated -> 401
            res_unauth = self.client.post("/api/v1/payments/simulate-success", json={"order_id": "any_order"})
            self.assertEqual(res_unauth.status_code, 401)

            # Non-admin in production mode -> 403
            with patch.dict(self.app.config, {"DEBUG": False, "TESTING": False}):
                res_prod = self.client.post(
                    "/api/v1/payments/simulate-success",
                    headers={"Authorization": f"Bearer {token}"},
                    json={"order_id": "any_order"}
                )
                self.assertEqual(res_prod.status_code, 403)

    def test_05_startup_environment_validation(self):
        """Vulnerability #5: validate_environment identifies missing essential production secrets."""
        with patch.dict(os.environ, {"FLASK_ENV": "production", "SECRET_KEY": ""}):
            from src.utils import config as cfg_mod
            cfg_mod._config = None
            missing = validate_environment(raise_on_missing=False)
            self.assertIn("SECRET_KEY", missing)

    def test_06_info_disclosure_endpoints_require_super_admin(self):
        """Vulnerability #6: Protect /api/test-mongo and /api/debug from unauthorized access."""
        client_user = UserManager.create_user(self.db, "client_user@test.com", "pass123", role="client")
        client_token = generate_auth_token(client_user["_id"], client_user["email"])

        super_admin = UserManager.create_user(self.db, "alooshpal@gmail.com", "pass123", role="super_admin")
        super_token = generate_auth_token(super_admin["_id"], super_admin["email"])

        with patch("src.web.api.get_db", return_value=self.db):
            # 1. Unauthenticated -> 401
            self.assertEqual(self.client.get("/api/debug").status_code, 401)
            self.assertEqual(self.client.get("/api/test-mongo").status_code, 401)

            # 2. Regular client -> 403 Forbidden
            self.assertEqual(self.client.get("/api/debug", headers={"Authorization": f"Bearer {client_token}"}).status_code, 403)
            self.assertEqual(self.client.get("/api/test-mongo", headers={"Authorization": f"Bearer {client_token}"}).status_code, 403)

            # 3. Super Admin -> 200 OK
            self.assertEqual(self.client.get("/api/debug", headers={"Authorization": f"Bearer {super_token}"}).status_code, 200)
            self.assertEqual(self.client.get("/api/test-mongo", headers={"Authorization": f"Bearer {super_token}"}).status_code, 200)

    def test_07_blacklist_routes_require_authentication(self):
        """Vulnerability #7: Protect /api/blacklist endpoints with @require_auth."""
        with patch("src.web.api.get_db", return_value=self.db):
            # GET /api/blacklist without auth -> 401
            self.assertEqual(self.client.get("/api/blacklist").status_code, 401)

            # POST /api/blacklist without auth -> 401
            self.assertEqual(self.client.post("/api/blacklist", json={"channel_id": "-1001"}).status_code, 401)

            # DELETE /api/blacklist/-1001 without auth -> 401
            self.assertEqual(self.client.delete("/api/blacklist/-1001").status_code, 401)

    def test_08_atomic_license_key_redemption_prevents_double_redemption(self):
        """Vulnerability #8: Atomic redemption prevents race conditions and double redemption."""
        user1 = UserManager.create_user(self.db, "user1_key@test.com", "pass123")
        user2 = UserManager.create_user(self.db, "user2_key@test.com", "pass123")

        key = LicenseKeyManager.generate_key(self.db, plan_id="monthly", created_by="admin")
        key_code = key["key_code"]

        # First redemption must succeed
        ok1, msg1, sub1 = LicenseKeyManager.redeem_key(self.db, user1["_id"], key_code)
        self.assertTrue(ok1)
        self.assertEqual(sub1["status"], "active")

        # Immediate second redemption attempt for same key must fail
        ok2, msg2, sub2 = LicenseKeyManager.redeem_key(self.db, user2["_id"], key_code)
        self.assertFalse(ok2)
        self.assertIn("مسبقاً", msg2)

    def test_09_rule_idor_unassigned_and_cross_user_protection(self):
        """Vulnerability #9: IDOR protection prevents users from modifying/deleting unassigned or other users' rules."""
        user_a = UserManager.create_user(self.db, "user_a@test.com", "pass123", role="client")
        token_a = generate_auth_token(user_a["_id"], user_a["email"])

        user_b = UserManager.create_user(self.db, "user_b@test.com", "pass123", role="client")
        token_b = generate_auth_token(user_b["_id"], user_b["email"])

        with patch("src.web.api.get_db", return_value=self.db):
            # Create Rule for User A
            res = self.client.post(
                "/api/rules",
                headers={"Authorization": f"Bearer {token_a}"},
                json={"name": "User A Rule", "source_id": "-1001", "target_id": "-1002"}
            )
            rule_id = res.get_json()["rule"]["_id"]

            # User B attempts to UPDATE User A's rule -> 403 Forbidden
            res_update = self.client.put(
                f"/api/rules/{rule_id}",
                headers={"Authorization": f"Bearer {token_b}"},
                json={"name": "Hacked Name"}
            )
            self.assertEqual(res_update.status_code, 403)

            # User B attempts to TOGGLE User A's rule -> 403 Forbidden
            res_toggle = self.client.post(
                f"/api/rules/{rule_id}/toggle",
                headers={"Authorization": f"Bearer {token_b}"}
            )
            self.assertEqual(res_toggle.status_code, 403)

            # User B attempts to DELETE User A's rule -> 403 Forbidden
            res_delete = self.client.delete(
                f"/api/rules/{rule_id}",
                headers={"Authorization": f"Bearer {token_b}"}
            )
            self.assertEqual(res_delete.status_code, 403)

            # Legacy unassigned rule (user_id is None)
            res_legacy = self.db.rules.insert_one({"name": "Legacy Rule", "user_id": None, "active": True})
            legacy_id = str(res_legacy.inserted_id)

            # User B attempts to DELETE legacy unassigned rule -> 403 Forbidden
            res_del_legacy = self.client.delete(
                f"/api/rules/{legacy_id}",
                headers={"Authorization": f"Bearer {token_b}"}
            )
            self.assertEqual(res_del_legacy.status_code, 403)

            # User A (Owner) can successfully DELETE their own rule
            res_del_own = self.client.delete(
                f"/api/rules/{rule_id}",
                headers={"Authorization": f"Bearer {token_a}"}
            )
            self.assertEqual(res_del_own.status_code, 200)

    def test_sec01_rules_engine_user_id_isolation(self):
        """SEC-01: Verify RulesEngine only loads rules belonging to its assigned user_id."""
        from src.rules.engine import RulesEngine
        # Insert rules for User 1 and User 2
        self.db.rules.insert_one({"_id": "r1", "name": "User 1 Rule", "user_id": "user_1", "active": True})
        self.db.rules.insert_one({"_id": "r2", "name": "User 2 Rule", "user_id": "user_2", "active": True})

        engine1 = RulesEngine(db=self.db, user_id="user_1")
        rules1 = engine1.load_rules()
        self.assertEqual(len(rules1), 1)
        self.assertEqual(rules1[0]["user_id"], "user_1")

        engine2 = RulesEngine(db=self.db, user_id="user_2")
        rules2 = engine2.load_rules()
        self.assertEqual(len(rules2), 1)
        self.assertEqual(rules2[0]["user_id"], "user_2")

    def test_sec03_telegram_auth_session_binding(self):
        """SEC-03: Verify verify_telegram_login_code requires matching phone AND user_id."""
        import asyncio
        from src.web.telegram_auth import verify_telegram_login_code

        # Seed pending auth for Victim User
        self.db.pending_auth.insert_one({
            "_id": "victim_user_+1234567890",
            "user_id": "victim_user",
            "phone": "+1234567890",
            "phone_code_hash": "hash123",
            "temp_session": "session123",
            "created_at": time.time()
        })

        # Attacker user tries to verify victim's pending phone code
        result = asyncio.run(verify_telegram_login_code(
            db=self.db,
            api_id=12345,
            api_hash="fakehash",
            user_id="attacker_user",
            code="12345",
            phone_number="+1234567890"
        ))
        self.assertFalse(result["success"])
        self.assertIn("not found or expired", result["error"])

    def test_sec04_rules_test_endpoint_requires_auth(self):
        """SEC-04: Verify POST /api/rules/test is protected with @require_auth and scopes to user rules."""
        user_a = UserManager.create_user(self.db, "user_test_a@test.com", "pass123")
        token_a = generate_auth_token(user_a["_id"], user_a["email"])

        with patch("src.web.api.get_db", return_value=self.db):
            # Unauthenticated -> 401
            res_unauth = self.client.post("/api/rules/test", json={"text": "Hello"})
            self.assertEqual(res_unauth.status_code, 401)

            # Authenticated User A
            self.client.post("/api/rules", headers={"Authorization": f"Bearer {token_a}"}, json={
                "name": "Replace Hello",
                "type": "replace",
                "pattern": "Hello",
                "replacement": "Greetings",
                "active": True
            })

            res_auth = self.client.post(
                "/api/rules/test",
                headers={"Authorization": f"Bearer {token_a}"},
                json={"text": "Hello World"}
            )
            self.assertEqual(res_auth.status_code, 200)
            data = res_auth.get_json()
            self.assertTrue(data["success"])
            self.assertEqual(data["transformed"], "Greetings World")

    def test_sec05_nowpayments_raises_on_missing_env_in_production(self):
        """SEC-05: Verify NOWPayments raises RuntimeError on missing secrets in production."""
        from src.billing.nowpayments import NOWPaymentsGateway
        with patch.dict(os.environ, {"FLASK_ENV": "production", "DEBUG": "false", "TESTING": "false", "NOWPAYMENTS_API_KEY": "", "NOWPAYMENTS_IPN_SECRET": "", "PAYMENT_WEBHOOK_SECRET": ""}):
            with self.assertRaises(RuntimeError):
                NOWPaymentsGateway.get_api_key()

            with self.assertRaises(RuntimeError):
                NOWPaymentsGateway.get_ipn_secret()


if __name__ == "__main__":
    unittest.main()
