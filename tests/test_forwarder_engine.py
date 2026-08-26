"""
Tests for the ForwarderEngine.
Tests duplicate prevention and FLOOD_WAIT handling using mock objects.
No real Telegram credentials or network calls are required.
"""
import asyncio
import time
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import tests.conftest  # noqa: F401

import src.forwarder.engine as fe


def make_engine(db=None):
    """Create a ForwarderEngine with Telethon client mocked out."""
    if db is None:
        db = MagicMock()
    config = {
        "API_ID": 123456,
        "API_HASH": "testhash",
        "SESSION_STRING": "test",
        "MONGO_URI": "mongodb://localhost",
        "MONGO_DB": "test",
        "CHECK_INTERVAL": 30,
        "MAX_RETRIES": 3,
        "RETRY_DELAY": 10,
    }
    with patch.object(fe, "TelegramClient", MagicMock()), \
         patch.object(fe, "StringSession", MagicMock()):
        return fe.ForwarderEngine(config, db)


class DuplicatePreventionTest(unittest.TestCase):
    """Test ForwarderEngine._is_duplicate with a mock DB."""

    def test_new_post_is_not_duplicate(self):
        db = MagicMock()
        db.processed_posts.find_one.return_value = None
        engine = make_engine(db)
        self.assertFalse(engine._is_duplicate("12345:1"))

    def test_existing_post_is_duplicate(self):
        db = MagicMock()
        db.processed_posts.find_one.return_value = {"_id": "12345:1"}
        engine = make_engine(db)
        self.assertTrue(engine._is_duplicate("12345:1"))

    def test_duplicate_uses_post_key(self):
        db = MagicMock()
        db.processed_posts.find_one.return_value = None
        engine = make_engine(db)
        engine._is_duplicate("source:42")
        # Verify find_one was called with the correct _id
        db.processed_posts.find_one.assert_called_with({"_id": "source:42"})

    def test_mark_processed_inserts_record(self):
        db = MagicMock()
        engine = make_engine(db)
        engine._mark_processed("12345:1", message_id=1, source_id=12345, target_id=67890)
        db.processed_posts.insert_one.assert_called_once()
        call_args = db.processed_posts.insert_one.call_args[0][0]
        self.assertEqual(call_args["_id"], "12345:1")
        self.assertEqual(call_args["message_id"], 1)
        self.assertEqual(call_args["source_id"], 12345)
        self.assertEqual(call_args["target_id"], 67890)
        self.assertIn("forwarded_at", call_args)


class FloodWaitTest(unittest.TestCase):
    """Test FLOOD_WAIT handling logic."""

    def test_no_flood_wait_by_default(self):
        engine = make_engine()
        self.assertFalse(engine._is_flood_waited(12345))

    @patch.object(fe.asyncio, "sleep", new_callable=AsyncMock)
    def test_is_flood_waited_after_handle(self, mock_sleep):
        """After _handle_flood_wait, the channel should be flood-waited."""
        engine = make_engine()

        async def run():
            await engine._handle_flood_wait(12345, 30)

        asyncio.get_event_loop().run_until_complete(run())
        # Should now be in flood wait (timestamp set to future)
        self.assertTrue(engine._is_flood_waited(12345))
        # Verify the timestamp is set and in the future
        wait_until = engine._last_flood_wait[12345]
        self.assertGreater(wait_until, time.time())
        # Verify sleep was awaited with the correct duration
        mock_sleep.assert_awaited_with(30)

    @patch.object(fe.asyncio, "sleep", new_callable=AsyncMock)
    def test_handle_flood_wait_sets_future_timestamp(self, mock_sleep):
        """_handle_flood_wait stores time.time() + seconds + 5 (buffer)."""
        engine = make_engine()

        async def run():
            await engine._handle_flood_wait(999, 60)

        asyncio.get_event_loop().run_until_complete(run())
        wait_until = engine._last_flood_wait[999]
        # Buffer of +5 seconds is added
        expected_min = time.time() + 60 + 5 - 1  # allow 1s slack
        self.assertGreater(wait_until, expected_min)
        mock_sleep.assert_awaited_with(60)

    def test_flood_wait_expires(self):
        """After the flood wait period expires, _is_flood_waited returns False."""
        engine = make_engine()
        # Set a past timestamp
        engine._last_flood_wait[555] = time.time() - 1
        self.assertFalse(engine._is_flood_waited(555))

    def test_flood_wait_different_channels_independent(self):
        engine = make_engine()
        engine._last_flood_wait[111] = time.time() + 100  # future
        self.assertTrue(engine._is_flood_waited(111))
        self.assertFalse(engine._is_flood_waited(222))

    def test_pending_flood_queue_initialized(self):
        engine = make_engine()
        self.assertEqual(engine._pending_flood, [])
        self.assertEqual(engine._last_flood_wait, {})


if __name__ == "__main__":
    unittest.main(verbosity=2)
