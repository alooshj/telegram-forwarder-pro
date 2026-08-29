import unittest
import json
import time
import base64
import hmac
import hashlib
from unittest.mock import patch

from src.utils.database import SQLiteDB
from src.web.api import app, get_db
from src.web.clerk_webhook import verify_svix_signature, process_clerk_webhook_event


class ClerkWebhookTestCase(unittest.TestCase):
    def setUp(self):
        self.db = SQLiteDB(":memory:")
        app.config["TESTING"] = True
        self.client = app.test_client()
        self.secret = "whsec_test_clerk_webhook_secret_key_12345"
        self.raw_secret = "test_clerk_webhook_secret_key_12345"

    def _generate_svix_headers(self, payload_dict, secret_str):
        raw_body = json.dumps(payload_dict, separators=(',', ':'))
        msg_id = f"msg_{int(time.time()*1000)}"
        timestamp = str(int(time.time()))

        clean_secret = secret_str
        if clean_secret.startswith("whsec_"):
            clean_secret = clean_secret[6:]
        
        try:
            key_bytes = base64.b64decode(clean_secret)
        except Exception:
            key_bytes = clean_secret.encode("utf-8")

        signed_content = f"{msg_id}.{timestamp}.{raw_body}".encode("utf-8")
        sig = base64.b64encode(hmac.new(key_bytes, signed_content, hashlib.sha256).digest()).decode("utf-8")

        return {
            "svix-id": msg_id,
            "svix-timestamp": timestamp,
            "svix-signature": f"v1,{sig}",
            "Content-Type": "application/json"
        }, raw_body

    def test_01_svix_signature_verification_valid_and_invalid(self):
        """Test Svix HMAC-SHA256 signature verification helper."""
        payload = {"type": "user.created", "data": {"id": "user_test_123"}}
        headers, raw_body = self._generate_svix_headers(payload, self.secret)

        # 1. Valid signature
        self.assertTrue(verify_svix_signature(raw_body.encode("utf-8"), headers, self.secret))

        # 2. Tampered body
        tampered_body = raw_body + " "
        self.assertFalse(verify_svix_signature(tampered_body.encode("utf-8"), headers, self.secret))

        # 3. Missing headers
        self.assertFalse(verify_svix_signature(raw_body.encode("utf-8"), {}, self.secret))

        # 4. Wrong secret
        self.assertFalse(verify_svix_signature(raw_body.encode("utf-8"), headers, "whsec_wrong_secret"))

    def test_02_webhook_user_created_syncs_to_database(self):
        """Test user.created event synchronizes user metadata into database."""
        event_payload = {
            "type": "user.created",
            "data": {
                "id": "user_clerk_999",
                "first_name": "Sami",
                "last_name": "Ahmad",
                "image_url": "https://img.clerk.com/avatar999.png",
                "primary_email_address_id": "email_1",
                "email_addresses": [
                    {"id": "email_1", "email_address": "sami@example.com"}
                ]
            }
        }

        success, res_data, status = process_clerk_webhook_event(self.db, event_payload)
        self.assertTrue(success)
        self.assertEqual(status, 200)

        # Verify user record in database
        user = self.db.users.find_one({"clerk_id": "user_clerk_999"})
        self.assertIsNotNone(user)
        self.assertEqual(user["email"], "sami@example.com")
        self.assertEqual(user["fullName"], "Sami Ahmad")
        self.assertEqual(user["avatar"], "https://img.clerk.com/avatar999.png")
        self.assertEqual(user["status"], "active")
        self.assertEqual(user["role"], "client")

    def test_03_webhook_user_updated_syncs_idempotently(self):
        """Test user.updated event modifies user metadata idempotently."""
        # Initial user creation
        self.db.users.insert_one({
            "_id": "user_clerk_888",
            "clerk_id": "user_clerk_888",
            "email": "old@example.com",
            "fullName": "Old Name",
            "status": "active"
        })

        update_event = {
            "type": "user.updated",
            "data": {
                "id": "user_clerk_888",
                "first_name": "New",
                "last_name": "Name",
                "image_url": "https://img.clerk.com/new_avatar.png",
                "email_addresses": [
                    {"id": "email_1", "email_address": "new_email@example.com"}
                ]
            }
        }

        success, res_data, status = process_clerk_webhook_event(self.db, update_event)
        self.assertTrue(success)
        self.assertEqual(status, 200)

        user = self.db.users.find_one({"clerk_id": "user_clerk_888"})
        self.assertEqual(user["email"], "new_email@example.com")
        self.assertEqual(user["fullName"], "New Name")
        self.assertEqual(user["avatar"], "https://img.clerk.com/new_avatar.png")

    def test_04_webhook_user_deleted_marks_status(self):
        """Test user.deleted event updates user status to deleted."""
        self.db.users.insert_one({
            "_id": "user_clerk_777",
            "clerk_id": "user_clerk_777",
            "email": "delete_me@example.com",
            "status": "active"
        })

        delete_event = {
            "type": "user.deleted",
            "data": {
                "id": "user_clerk_777"
            }
        }

        success, res_data, status = process_clerk_webhook_event(self.db, delete_event)
        self.assertTrue(success)
        self.assertEqual(status, 200)

        user = self.db.users.find_one({"clerk_id": "user_clerk_777"})
        self.assertEqual(user["status"], "deleted")

    def test_05_webhook_super_admin_auto_elevation(self):
        """Test super admin (alooshpal@gmail.com) gets elevated to super_admin and annual plan."""
        event_payload = {
            "type": "user.created",
            "data": {
                "id": "user_super_admin_1",
                "first_name": "Ali",
                "last_name": "Admin",
                "email_addresses": [
                    {"id": "email_super", "email_address": "alooshpal@gmail.com"}
                ]
            }
        }

        success, res_data, status = process_clerk_webhook_event(self.db, event_payload)
        self.assertTrue(success)

        user = self.db.users.find_one({"email": "alooshpal@gmail.com"})
        self.assertIsNotNone(user)
        self.assertEqual(user["role"], "super_admin")
        self.assertEqual(user["plan"], "annual")
        self.assertEqual(user["subscription_status"], "active")
        self.assertEqual(user["max_target_channels"], 999)

    def test_06_endpoint_post_clerk_webhook_full_cycle(self):
        """Test full HTTP POST /api/webhooks/clerk request cycle with signature validation."""
        event_payload = {
            "type": "user.created",
            "data": {
                "id": "user_http_test_555",
                "first_name": "Http",
                "last_name": "User",
                "email_addresses": [
                    {"id": "e_1", "email_address": "http_user@test.com"}
                ]
            }
        }

        headers, raw_body = self._generate_svix_headers(event_payload, self.secret)

        with patch("src.web.api.get_db", return_value=self.db):
            with patch.dict("os.environ", {"CLERK_WEBHOOK_SECRET": self.secret}):
                # 1. Valid request -> 200 OK
                res = self.client.post("/api/webhooks/clerk", headers=headers, data=raw_body)
                self.assertEqual(res.status_code, 200)
                data = res.get_json()
                self.assertTrue(data["success"])
                self.assertEqual(data["event"], "user.created")

                # 2. Invalid signature request -> 400 Bad Request
                bad_headers = dict(headers)
                bad_headers["svix-signature"] = "v1,invalidsig12345"
                res_bad = self.client.post("/api/webhooks/clerk", headers=bad_headers, data=raw_body)
                self.assertEqual(res_bad.status_code, 400)


if __name__ == "__main__":
    unittest.main()
