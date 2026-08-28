"""
Unit Tests for Clerk Authentication & Multi-Tenant JWT Integration
------------------------------------------------------------------
Tests verification of Clerk JWT tokens, auto-provisioning, /api/auth/clerk-sync endpoint,
and route protection with data isolation.
"""

import os
import sys
import unittest
import time
import jwt
from unittest.mock import patch

# Ensure src is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.utils.database import SQLiteDB
from src.web.api import app
from src.web.auth import (
    UserManager,
    verify_clerk_token_or_payload,
    get_current_user_from_request,
)


class ClerkAuthTestCase(unittest.TestCase):
    """Test suite for Clerk Authentication and JWT Token Middleware."""

    def setUp(self):
        self.app = app
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        self.db = SQLiteDB(":memory:")

    def tearDown(self):
        pass

    def test_verify_clerk_token_payload(self):
        """Test decoding and auto-provisioning from Clerk JWT payload."""
        clerk_id = "user_clerk_test_12345"
        token = jwt.encode(
            {
                "sub": clerk_id,
                "email": "clerk_client@test.com",
                "name": "Clerk User",
                "exp": int(time.time()) + 3600,
            },
            "secret",
            algorithm="HS256",
        )

        user = verify_clerk_token_or_payload(token, self.db)
        self.assertIsNotNone(user)
        self.assertEqual(user["_id"], clerk_id)
        self.assertEqual(user["email"], "clerk_client@test.com")
        self.assertEqual(user["role"], "client")
        self.assertTrue(user["is_verified"])

    def test_clerk_sync_endpoint(self):
        """Test /api/auth/clerk-sync creates a user and returns session token."""
        with patch("src.web.api.get_db", return_value=self.db):
            res = self.client.post(
                "/api/auth/clerk-sync",
                json={
                    "clerk_id": "user_sync_789",
                    "email": "sync_user@example.com",
                    "name": "Sync User",
                },
            )
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertTrue(data["success"])
            self.assertEqual(data["user"]["email"], "sync_user@example.com")
            self.assertIn("token", data)

            # Check that user is in DB
            db_user = self.db.users.find_one({"_id": "user_sync_789"})
            self.assertIsNotNone(db_user)

    def test_clerk_super_admin_assignment(self):
        """Test that alooshpal@gmail.com authenticated via Clerk gets super_admin role."""
        token = jwt.encode(
            {
                "sub": "user_super_admin_clerk",
                "email": "alooshpal@gmail.com",
                "name": "Super Admin Ali",
                "exp": int(time.time()) + 3600,
            },
            "secret",
            algorithm="HS256",
        )

        user = verify_clerk_token_or_payload(token, self.db)
        self.assertIsNotNone(user)
        self.assertEqual(user["role"], "super_admin")
        self.assertEqual(user["plan"], "annual")

    def test_api_requests_with_clerk_jwt_header(self):
        """Test calling protected APIs directly using Clerk JWT in Authorization header."""
        clerk_id = "user_clerk_api_tester"
        token = jwt.encode(
            {
                "sub": clerk_id,
                "email": "api_tester@test.com",
                "name": "API Tester",
                "exp": int(time.time()) + 3600,
            },
            "secret",
            algorithm="HS256",
        )

        with patch("src.web.api.get_db", return_value=self.db):
            # Create a rule using Clerk JWT
            res_create = self.client.post(
                "/api/rules",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "name": "Clerk Test Rule",
                    "source_id": "-100111",
                    "target_id": "-100222",
                },
            )
            self.assertEqual(res_create.status_code, 200)

            # Get rules using Clerk JWT
            res_rules = self.client.get(
                "/api/rules",
                headers={"Authorization": f"Bearer {token}"},
            )
            self.assertEqual(res_rules.status_code, 200)
            rules = res_rules.get_json()["rules"]
            self.assertEqual(len(rules), 1)
            self.assertEqual(rules[0]["user_id"], clerk_id)


if __name__ == "__main__":
    unittest.main()
