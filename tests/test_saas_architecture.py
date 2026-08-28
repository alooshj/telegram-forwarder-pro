"""
Test Suite for SaaS Enterprise Architecture:
- Fernet AES Encryption Engine
- Telegram Dialogs Picker API
- Dynamic Multi-Tenant Worker Pool
"""

import unittest
import asyncio
import time
from unittest.mock import patch, MagicMock, AsyncMock
from src.utils.encryption import encrypt_session, decrypt_session
from src.utils.database import SQLiteDB
from src.web.auth import UserManager, generate_auth_token
from src.web.api import app, _db_cache, _db_initialized
from src.forwarder.worker_pool import WorkerPool, UserWorker


class SaaSArchitectureTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        self.db = SQLiteDB(":memory:")

    def test_fernet_encryption_and_decryption(self):
        """Test that sessions are strongly encrypted and decrypted correctly."""
        raw_session = "1BJWNx1wBuxKq248TelethonSessionSecretKey998877=="
        encrypted = encrypt_session(raw_session)
        self.assertTrue(encrypted.startswith("enc:"))
        self.assertNotEqual(encrypted, raw_session)

        # Double encrypting should return existing enc token safely
        double_enc = encrypt_session(encrypted)
        self.assertEqual(double_enc, encrypted)

        # Decrypting
        decrypted = decrypt_session(encrypted)
        self.assertEqual(decrypted, raw_session)

        # Plain unencrypted session passes through safely
        plain = decrypt_session("1BJWNxPlainLegacy==")
        self.assertEqual(plain, "1BJWNxPlainLegacy==")

    def test_user_manager_stores_encrypted_session(self):
        """Test UserManager encrypts session on update and decrypts via getter."""
        user = UserManager.create_user(self.db, "crypto@test.com", "pass12345")
        raw_session = "1BJWNxUserSessionToken12345=="
        
        UserManager.update_telegram_account(self.db, user["_id"], {
            "telegram_user_id": 11223344,
            "username": "cryptouser",
            "session_string": raw_session
        })

        # Verify in database that it is encrypted with enc:
        raw_user = UserManager.get_user_by_id(self.db, user["_id"])
        stored_session = raw_user["telegram_account"]["session_string"]
        self.assertTrue(stored_session.startswith("enc:"))

        # Verify getter returns decrypted session
        decrypted_session = UserManager.get_user_telegram_session(self.db, user["_id"])
        self.assertEqual(decrypted_session, raw_session)

    @patch("src.web.telegram_auth.fetch_user_telegram_dialogs")
    def test_api_telegram_dialogs_endpoint(self, mock_dialogs):
        """Test GET /api/telegram/dialogs endpoint."""
        user = UserManager.create_user(self.db, "dialog_user@test.com", "pass12345")
        token = generate_auth_token(user["_id"], user["email"])
        raw_session = "1BJWNxDialogTestSession=="

        UserManager.update_telegram_account(self.db, user["_id"], {
            "telegram_user_id": 998877,
            "username": "dialogbot",
            "session_string": raw_session
        })

        mock_dialogs.return_value = {
            "success": True,
            "count": 2,
            "dialogs": [
                {"id": -100111, "title": "Channel 1", "type": "channel", "is_channel": True},
                {"id": -100222, "title": "Group 2", "type": "group", "is_group": True}
            ]
        }

        with patch("src.web.api.get_db", return_value=self.db):
            res = self.client.get(
                "/api/telegram/dialogs",
                headers={"Authorization": f"Bearer {token}"}
            )
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertTrue(data["success"])
            self.assertEqual(len(data["dialogs"]), 2)
            self.assertEqual(data["dialogs"][0]["title"], "Channel 1")

    def test_worker_pool_lifecycle(self):
        """Test WorkerPool singleton starting, querying, and stopping workers."""
        pool = WorkerPool()
        user_id = "user_pool_test_123"
        config = {"API_ID": 12345, "API_HASH": "hash"}
        raw_session = "1BJWNxValidPoolTestSessionString=="
        valid_enc = encrypt_session(raw_session)

        # Mock engine async start to run until stopped
        async def mock_start(engine_self):
            engine_self._running = True
            while engine_self._running:
                await asyncio.sleep(0.05)

        with patch("src.forwarder.engine.ForwarderEngine.start", side_effect=mock_start, autospec=True):
            started = pool.start_user_worker(user_id, valid_enc, config, self.db)
            self.assertTrue(started)
            import time
            time.sleep(0.05)
            self.assertTrue(pool.is_user_running(user_id))

            stopped = pool.stop_user_worker(user_id)
            self.assertTrue(stopped)
            self.assertFalse(pool.is_user_running(user_id))

    @patch("src.web.telegram_auth.fetch_channel_avatar")
    def test_api_telegram_avatar_endpoint(self, mock_avatar):
        """Test GET /api/telegram/avatar/<entity_id> endpoint."""
        user = UserManager.create_user(self.db, "avatar_user@test.com", "pass12345")
        token = generate_auth_token(user["_id"], user["email"])
        UserManager.update_telegram_account(self.db, user["_id"], {
            "telegram_user_id": 998877,
            "username": "avataruser",
            "session_string": "1BJWNxAvatarTestSession=="
        })

        mock_avatar.return_value = b"\xff\xd8\xff\xe0\x00\x10JFIF"  # Fake JPEG bytes

        with patch("src.web.api.get_db", return_value=self.db):
            res = self.client.get(
                "/api/telegram/avatar/12345678",
                headers={"Authorization": f"Bearer {token}"}
            )
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.mimetype, "image/jpeg")
            self.assertEqual(res.data, b"\xff\xd8\xff\xe0\x00\x10JFIF")

    def test_multi_tenant_isolation_rules_and_channels(self):
        """Verify that User B cannot see User A's rules or connected channels."""
        # Create User A with a rule
        user_a = UserManager.create_user(self.db, "user_a@test.com", "passA123")
        token_a = generate_auth_token(user_a["_id"], user_a["email"])
        UserManager.update_telegram_account(self.db, user_a["_id"], {
            "telegram_user_id": 111,
            "username": "usera_tg",
            "session_string": "1BJWNxSessionA=="
        })

        # Create User B with NO connected telegram account
        user_b = UserManager.create_user(self.db, "user_b@test.com", "passB123")
        token_b = generate_auth_token(user_b["_id"], user_b["email"])

        with patch("src.web.api.get_db", return_value=self.db):
            # User A creates a rule
            res_create = self.client.post(
                "/api/rules",
                headers={"Authorization": f"Bearer {token_a}"},
                json={"name": "User A Private Rule", "source_id": "-100111", "target_id": "-100222"}
            )
            self.assertEqual(res_create.status_code, 200)
            rule_id = res_create.get_json()["rule"]["_id"]

            # User A sees 1 rule
            res_a = self.client.get("/api/rules", headers={"Authorization": f"Bearer {token_a}"})
            self.assertEqual(len(res_a.get_json()["rules"]), 1)

            # User B sees 0 rules (isolated!)
            res_b = self.client.get("/api/rules", headers={"Authorization": f"Bearer {token_b}"})
            self.assertEqual(len(res_b.get_json()["rules"]), 0)

            # User B cannot delete or update User A's rule (403 Forbidden)
            res_del = self.client.delete(f"/api/rules/{rule_id}", headers={"Authorization": f"Bearer {token_b}"})
            self.assertEqual(res_del.status_code, 403)

            # User B cannot see channels when they haven't connected their own Telegram account
            res_chan = self.client.get("/api/channels", headers={"Authorization": f"Bearer {token_b}"})
            self.assertEqual(res_chan.get_json()["channels"], [])
            self.assertFalse(res_chan.get_json()["connected"])


if __name__ == "__main__":
    unittest.main()

