"""
Unit Tests for TeleTips Pro Email Verification System
------------------------------------------------------
Tests account creation with email verification, OTP code verification,
URL token verification, resend verification, and web verification endpoints.
"""

import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from src.web.auth import UserManager
from src.utils.email_service import _generate_verification_html, _generate_verification_text
from src.web.api import app


class FakeCollection:
    def __init__(self):
        self._data = {}

    def count_documents(self, filter_dict=None):
        if not filter_dict:
            return len(self._data)
        count = 0
        for doc in self._data.values():
            if all(doc.get(k) == v for k, v in filter_dict.items()):
                count += 1
        return count

    def find_one(self, filter_dict):
        for doc in self._data.values():
            match = True
            for k, v in filter_dict.items():
                if doc.get(k) != v:
                    match = False
                    break
            if match:
                return dict(doc)
        return None

    def insert_one(self, doc):
        doc_copy = dict(doc)
        doc_id = doc_copy.get("_id")
        self._data[doc_id] = doc_copy
        return doc_id

    def update_one(self, filter_dict, update_dict):
        target = None
        for doc_id, doc in self._data.items():
            match = True
            for k, v in filter_dict.items():
                if doc.get(k) != v:
                    match = False
                    break
            if match:
                target = doc_id
                break
        if target and "$set" in update_dict:
            self._data[target].update(update_dict["$set"])
            return True
        return False


class FakeDB:
    def __init__(self):
        self.users = FakeCollection()
        self.rules = FakeCollection()
        self.blacklist = FakeCollection()
        self.license_keys = FakeCollection()
        self.orders = FakeCollection()


class EmailVerificationTestCase(unittest.TestCase):
    def setUp(self):
        self.db = FakeDB()
        self.app = app
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def test_create_user_sets_verification_fields_for_client(self):
        """Regular user account should have is_verified=False and a 6-digit OTP."""
        # Insert a super admin first so the next user is a client
        UserManager.create_user(self.db, "alooshpal@gmail.com", "superpass123")
        
        user = UserManager.create_user(self.db, "testuser@example.com", "password123", "Test User")
        self.assertFalse(user["is_verified"])
        self.assertIsNotNone(user["verification_token"])
        self.assertIsNotNone(user["verification_otp"])
        self.assertEqual(len(user["verification_otp"]), 6)
        self.assertTrue(user["verification_otp"].isdigit())
        self.assertIsNotNone(user["verification_expires_at"])

    def test_verify_user_by_otp(self):
        """User can verify their account with the correct 6-digit OTP."""
        UserManager.create_user(self.db, "alooshpal@gmail.com", "superpass123")
        user = UserManager.create_user(self.db, "user1@example.com", "password123", "User One")
        otp = user["verification_otp"]

        verified_user = UserManager.verify_user_by_otp(self.db, "user1@example.com", otp)
        self.assertIsNotNone(verified_user)
        self.assertTrue(verified_user["is_verified"])

        # Check DB state
        db_user = self.db.users.find_one({"email": "user1@example.com"})
        self.assertTrue(db_user["is_verified"])
        self.assertIsNone(db_user["verification_token"])
        self.assertIsNone(db_user["verification_otp"])

    def test_verify_user_by_token(self):
        """User can verify their account with the URL verification token."""
        UserManager.create_user(self.db, "alooshpal@gmail.com", "superpass123")
        user = UserManager.create_user(self.db, "user2@example.com", "password123", "User Two")
        token = user["verification_token"]

        verified_user = UserManager.verify_user_by_token(self.db, token)
        self.assertIsNotNone(verified_user)
        self.assertTrue(verified_user["is_verified"])

        db_user = self.db.users.find_one({"email": "user2@example.com"})
        self.assertTrue(db_user["is_verified"])

    def test_verify_invalid_otp_fails(self):
        """Invalid OTP code should fail verification."""
        UserManager.create_user(self.db, "alooshpal@gmail.com", "superpass123")
        UserManager.create_user(self.db, "user3@example.com", "password123", "User Three")

        verified = UserManager.verify_user_by_otp(self.db, "user3@example.com", "000000")
        self.assertIsNone(verified)

    def test_regenerate_verification(self):
        """Regenerating verification generates a new OTP and token."""
        UserManager.create_user(self.db, "alooshpal@gmail.com", "superpass123")
        user = UserManager.create_user(self.db, "user4@example.com", "password123", "User Four")
        old_token = user["verification_token"]
        old_otp = user["verification_otp"]

        new_token, new_otp, name = UserManager.regenerate_verification(self.db, "user4@example.com")
        self.assertNotEqual(new_token, old_token)
        self.assertNotEqual(new_otp, old_otp)
        self.assertEqual(name, "User Four")

    def test_email_template_contains_brand_and_otp(self):
        """The HTML and plain text email templates contain TeleTips Pro branding and OTP."""
        html = _generate_verification_html("Ahmed", "https://teletips.pro/verify?token=123", "849201")
        text = _generate_verification_text("Ahmed", "https://teletips.pro/verify?token=123", "849201")

        self.assertIn("TeleTips", html)
        self.assertIn("849201", html)
        self.assertIn("Ahmed", html)

        self.assertIn("TeleTips Pro", text)
        self.assertIn("849201", text)

    @patch("src.web.api.get_db")
    def test_api_verify_email_endpoint(self, mock_get_db):
        """Test POST /api/auth/verify-email endpoint."""
        mock_get_db.return_value = self.db
        UserManager.create_user(self.db, "alooshpal@gmail.com", "superpass123")
        user = UserManager.create_user(self.db, "api_user@example.com", "password123", "API User")
        otp = user["verification_otp"]

        res = self.client.post("/api/auth/verify-email", json={
            "email": "api_user@example.com",
            "otp": otp
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertTrue(data["user"]["is_verified"])

    @patch("src.web.api.get_db")
    def test_api_resend_verification_endpoint(self, mock_get_db):
        """Test POST /api/auth/resend-verification endpoint."""
        mock_get_db.return_value = self.db
        UserManager.create_user(self.db, "alooshpal@gmail.com", "superpass123")
        UserManager.create_user(self.db, "resend_user@example.com", "password123", "Resend User")

        res = self.client.post("/api/auth/resend-verification", json={
            "email": "resend_user@example.com"
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])

    @patch("src.web.api.get_db")
    def test_web_verify_email_route(self, mock_get_db):
        """Test GET /verify-email web landing page."""
        mock_get_db.return_value = self.db
        UserManager.create_user(self.db, "alooshpal@gmail.com", "superpass123")
        user = UserManager.create_user(self.db, "web_user@example.com", "password123", "Web User")
        token = user["verification_token"]

        res = self.client.get(f"/verify-email?token={token}")
        self.assertEqual(res.status_code, 200)
        self.assertIn("تم تأكيد الحساب بنجاح", res.get_data(as_text=True))
        self.assertIn("TeleTips", res.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
