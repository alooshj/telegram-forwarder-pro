"""
Enterprise Engine Test Suite
----------------------------
Tests for:
- MediaGroupCollector (album debounce and bundling)
- TransformationPipeline (keywords, link/mention stripping, templating)
- Forwarding Modes (FORWARD, COPY, AUTO_FALLBACK)
- forward_delay throttling & per-target FloodWait
"""

import asyncio
import io
import unittest
from unittest.mock import MagicMock, AsyncMock, patch

from src.forwarder.album_collector import MediaGroupCollector
from src.rules.pipeline import TransformationPipeline
from src.rules.engine import RulesEngine
from src.forwarder.engine import ForwarderEngine


class EnterprisePipelineTestCase(unittest.TestCase):
    """Test TransformationPipeline keyword filtering, stripping, and templating."""

    def test_keyword_whitelist_and_blacklist(self):
        pipeline = TransformationPipeline()

        # Whitelist success
        allowed, _ = pipeline.check_keywords("Breaking: Bitcoin hits 100k!", whitelist=["Bitcoin", "Ethereum"])
        self.assertTrue(allowed)

        # Whitelist failure
        allowed, reason = pipeline.check_keywords("Apple releases new iPhone", whitelist=["Bitcoin", "Crypto"])
        self.assertFalse(allowed)
        self.assertIn("whitelist", reason)

        # Blacklist failure
        allowed, reason = pipeline.check_keywords("Special Discount! Contact us for spam", blacklist=["spam", "scam"])
        self.assertFalse(allowed)
        self.assertIn("blacklisted", reason)

        # Clean text passing both
        allowed, _ = pipeline.check_keywords("Daily Market News", whitelist=["Market"], blacklist=["scam"])
        self.assertTrue(allowed)

    def test_strip_mentions_and_links(self):
        pipeline = TransformationPipeline()

        # Mention stripping
        text1 = "Follow @CryptoTrader and @News_Daily for updates!"
        stripped1 = pipeline.strip_mentions(text1)
        self.assertEqual(stripped1, "Follow  and  for updates!")

        # Link stripping
        text2 = "Join us at https://t.me/mychannel or visit https://example.com/news"
        stripped2 = pipeline.strip_links(text2)
        self.assertEqual(stripped2, "Join us at  or visit")

    def test_dynamic_templating(self):
        pipeline = TransformationPipeline()
        context = {
            "source_title": "Tech News",
            "source_id": "-100123456",
            "target_title": "My Archive",
            "target_id": "-100987654",
            "msg_id": "789"
        }

        header = "📢 Source: {source_title} (ID: {source_id})"
        footer = "📅 Forwarded on {date} | Post #{msg_id}"

        result = pipeline.apply_templating("Official Announcement", header, footer, context)
        self.assertIn("📢 Source: Tech News (ID: -100123456)", result)
        self.assertIn("Official Announcement", result)
        self.assertIn("Post #789", result)


class MediaGroupCollectorTestCase(unittest.TestCase):
    """Test MediaGroupCollector debouncing and bundling."""

    def test_is_grouped_detection(self):
        single_msg = MagicMock(grouped_id=None, id=10)
        album_msg = MagicMock(grouped_id=987654321, id=11)

        self.assertFalse(MediaGroupCollector.is_grouped(single_msg))
        self.assertTrue(MediaGroupCollector.is_grouped(album_msg))

    def test_album_collector_debouncing(self):
        collector = MediaGroupCollector(debounce_seconds=0.1)
        dispatched_groups = []

        async def callback(group_data):
            dispatched_groups.append(group_data)

        async def run_collector():
            msg1 = MagicMock(grouped_id=123, id=1, media=MagicMock())
            msg2 = MagicMock(grouped_id=123, id=2, media=MagicMock())

            # Add two messages belonging to the same album
            await collector.add_message(msg1, "@source", ["@target"], {}, callback)
            await collector.add_message(msg2, "@source", ["@target"], {}, callback)

            # Wait for debounce timer to expire
            await asyncio.sleep(0.2)

        asyncio.run(run_collector())

        self.assertEqual(len(dispatched_groups), 1)
        self.assertEqual(len(dispatched_groups[0]["messages"]), 2)
        self.assertEqual(dispatched_groups[0]["grouped_id"], 123)


class EnterpriseForwarderModesTestCase(unittest.TestCase):
    """Test ForwarderEngine FORWARD, COPY, AUTO_FALLBACK modes and delay."""

    def setUp(self):
        self.mock_db = MagicMock()
        self.mock_db.rules.find.return_value = []
        self.mock_db.processed_posts.find_one.return_value = None
        self.mock_db.blacklist.find_one.return_value = None

        config = {
            "SESSION_STRING": "test_session",
            "API_ID": 12345,
            "API_HASH": "test_hash"
        }
        with patch("src.forwarder.engine.TelegramClient"):
            self.engine = ForwarderEngine(config, self.mock_db)
            self.engine.client = MagicMock()
            self.engine.client.send_message = AsyncMock()
            self.engine.client.send_file = AsyncMock()
            self.engine.client.forward_messages = AsyncMock()
            self.engine.client.download_media = AsyncMock(return_value=b"fake_bytes")

    def test_forward_mode_official(self):
        rule = {"forward_mode": "FORWARD", "forward_delay": 0}
        msg = MagicMock(id=101, media=None, message="Official Post")
        target = MagicMock(id=999)

        async def run():
            return await self.engine._forward_message(
                msg, target, "Official Post", media_type="text", source_id="@src", target_id="@tgt", rule=rule
            )

        res = asyncio.run(run())
        self.assertTrue(res)
        self.engine.client.forward_messages.assert_awaited_once_with(target, msg)

    def test_copy_mode_stealth(self):
        rule = {"forward_mode": "COPY", "forward_delay": 0}
        msg = MagicMock(id=102, media=MagicMock(), message="Stealth Caption")
        target = MagicMock(id=999)

        async def run():
            return await self.engine._forward_message(
                msg, target, "Transformed Caption", media_type="photo", source_id="@src", target_id="@tgt", rule=rule
            )

        res = asyncio.run(run())
        self.assertTrue(res)
        self.engine.client.download_media.assert_awaited_once()
        self.engine.client.send_file.assert_awaited_once()

    @patch("asyncio.sleep", new_callable=AsyncMock)
    def test_non_blocking_flood_wait_scheduling(self, mock_sleep):
        channel_a = "-100111"
        channel_b = "-100222"

        # Channel A is flood waited
        asyncio.run(self.engine._handle_flood_wait(channel_a, 60))

        self.assertTrue(self.engine._is_flood_waited(channel_a))
        # Channel B is NOT affected and remains available
        self.assertFalse(self.engine._is_flood_waited(channel_b))
        mock_sleep.assert_awaited_with(60)


if __name__ == "__main__":
    unittest.main(verbosity=2)
