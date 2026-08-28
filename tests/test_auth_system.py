"""
Unit tests for the SaaS Multi-User Authentication & Telegram Account Connection system.
"""

import unittest
import json
from unittest.mock import patch, MagicMock, AsyncMock

from src.web.api import app
from src.utils.database import SQLiteDB
from src.web.auth import (
    UserManager,
    generate_auth_token,
    verify_auth_token,
)


class AuthSystemTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

        # Set up in-memory / temporary SQLite database
        self.db = SQLiteDB(db_path=":memory:")
        self.db_patcher = patch("src.web.api.get_db", return_value=self.db)
        self.db_patcher.start()

    def tearDown(self):
        self.db_patcher.stop()

    def test_user_creation_and_password_hashing(self):
        """Test creating a new user securely hashes password and prevents plain text storage."""
        user = UserManager.create_user(self.db, "client@example.com", "SecretPass123!", "Client One")
        self.assertIsNotNone(user["_id"])
        self.assertEqual(user["email"], "client@example.com")
        self.assertEqual(user["name"], "Client One")
        self.assertNotEqual(user["password_hash"], "SecretPass123!")
        self.assertTrue(user["password_hash"].startswith("scrypt:") or user["password_hash"].startswith("pbkdf2:"))

    def test_duplicate_email_rejected(self):
        """Test registration with existing email raises ValueError."""
        UserManager.create_user(self.db, "duplicate@example.com", "password123")
        with self.assertRaises(ValueError):
            UserManager.create_user(self.db, "duplicate@example.com", "otherpassword")

    def test_authenticate_user_valid_and_invalid(self):
        """Test user authentication with correct and incorrect credentials."""
        UserManager.create_user(self.db, "auth@example.com", "CorrectPassword123")

        # Valid login
        valid_user = UserManager.authenticate_user(self.db, "auth@example.com", "CorrectPassword123")
        self.assertIsNotNone(valid_user)
        self.assertEqual(valid_user["email"], "auth@example.com")

        # Invalid password
        invalid_user = UserManager.authenticate_user(self.db, "auth@example.com", "WrongPassword")
        self.assertIsNone(invalid_user)

        # Non-existent email
        no_user = UserManager.authenticate_user(self.db, "ghost@example.com", "Pass")
        self.assertIsNone(no_user)

    def test_auth_token_lifecycle(self):
        """Test generating and verifying signed authentication tokens."""
        token = generate_auth_token("user_12345", "user@test.com")
        self.assertIsInstance(token, str)
        self.assertIn("user_12345", token)

        payload = verify_auth_token(token)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["user_id"], "user_12345")
        self.assertEqual(payload["email"], "user@test.com")

        # Invalid token
        self.assertIsNone(verify_auth_token("tampered:token:format:xyz"))
        self.assertIsNone(verify_auth_token(token + "corrupt"))

    def test_api_register_and_login_endpoints(self):
        """Test /api/auth/register and /api/auth/login endpoints."""
        # 1. Register
        reg_res = self.client.post("/api/auth/register", json={
            "email": "saas_user@domain.com",
            "password": "MySecurePassword2026",
            "name": "SaaS Client"
        })
        self.assertEqual(reg_res.status_code, 200)
        reg_data = reg_res.get_json()
        self.assertTrue(reg_data["success"])
        self.assertIn("token", reg_data)
        self.assertEqual(reg_data["user"]["email"], "saas_user@domain.com")

        # 2. Login
        login_res = self.client.post("/api/auth/login", json={
            "email": "saas_user@domain.com",
            "password": "MySecurePassword2026"
        })
        self.assertEqual(login_res.status_code, 200)
        login_data = login_res.get_json()
        self.assertTrue(login_data["success"])
        self.assertIn("token", login_data)

    def test_api_auth_me_and_logout(self):
        """Test /api/auth/me profile inspection and logout."""
        user = UserManager.create_user(self.db, "me@test.com", "password", "Me Tester")
        token = generate_auth_token(user["_id"], user["email"])

        # Authenticated /api/auth/me
        res = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["authenticated"])
        self.assertEqual(data["user"]["email"], "me@test.com")

        # Logout
        logout_res = self.client.post("/api/auth/logout")
        self.assertEqual(logout_res.status_code, 200)
        self.assertTrue(logout_res.get_json()["success"])

    @patch("src.web.api.send_telegram_login_code")
    def test_telegram_send_code_endpoint(self, mock_send_code):
        """Test sending phone verification code endpoint."""
        mock_send_code.return_value = {
            "success": True,
            "phone_code_hash": "hash_12345",
            "phone": "+966500000000",
            "message": "Code sent"
        }

        with patch("src.web.api.load_config", return_value={"TELEGRAM_API_ID": "12345", "TELEGRAM_API_HASH": "hash"}):
            res = self.client.post("/api/auth/telegram/send-code", json={"phone_number": "+966500000000"})
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertTrue(data["success"])
            self.assertEqual(data["phone_code_hash"], "hash_12345")

    @patch("src.web.api.verify_telegram_login_code")
    def test_telegram_verify_code_endpoint(self, mock_verify):
        """Test verifying OTP code and attaching session to user profile."""
        user = UserManager.create_user(self.db, "tg_user@test.com", "password")
        token = generate_auth_token(user["_id"], user["email"])

        mock_verify.return_value = {
            "success": True,
            "telegram_account": {
                "telegram_user_id": 987654321,
                "username": "my_client_bot",
                "first_name": "Client",
                "phone": "+966500000000",
                "session_string": "1BJWNx...",
            },
            "message": "Connected!"
        }

        with patch("src.web.api.load_config", return_value={"TELEGRAM_API_ID": "12345", "TELEGRAM_API_HASH": "hash"}):
            res = self.client.post(
                "/api/auth/telegram/verify-code",
                json={"code": "12345", "phone_number": "+966500000000"},
                headers={"Authorization": f"Bearer {token}"}
            )
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertTrue(data["success"])
            self.assertEqual(data["telegram_account"]["username"], "my_client_bot")

            # Check that database was updated with telegram session
            updated_user = UserManager.get_user_by_id(self.db, user["_id"])
            self.assertIsNotNone(updated_user.get("telegram_account"))
            self.assertEqual(updated_user["telegram_account"]["telegram_user_id"], 987654321)


if __name__ == "__main__":
    unittest.main()
