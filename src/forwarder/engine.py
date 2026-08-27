"""
Forwarder Engine
----------------
Core forwarding logic using Telethon. Handles:
- Fetching posts from source channels
- Applying rules via RulesEngine
- Forwarding to target channels
- Duplicate prevention via MongoDB post history
- FLOOD_WAIT rate limit handling
- Auto-reconnect on connection loss
"""

import asyncio
import logging
import time
from datetime import datetime, timezone

from telethon import TelegramClient, errors
from telethon.sessions import StringSession

from src.rules.engine import RulesEngine
from src.utils.database import MongoDB

logger = logging.getLogger(__name__)


class ForwarderEngine:
    """Telegram post forwarder with transformation, media support, and rate-limit handling."""

    def __init__(self, config: dict, db):
        self.config = config
        self.db = db
        self.rules_engine = RulesEngine(db)

        self._running = False
        self._last_flood_wait = {}  # channel_id -> timestamp
        self._pending_flood = []    # queued messages during flood wait

        # Initialize Telethon client with error handling
        try:
            self.client = TelegramClient(
                StringSession(config["SESSION_STRING"]),
                config["API_ID"],
                config["API_HASH"],
            )
        except Exception as e:
            logger.error(f"Failed to initialize Telegram client: {e}")
            self.client = None

    def _log_event(self, level: str, message: str):
        """Log to standard logger and persist to database logs collection."""
        if level == "INFO":
            logger.info(message)
        elif level == "WARNING":
            logger.warning(message)
        elif level == "ERROR":
            logger.error(message)
        else:
            logger.debug(message)

        if self.db and hasattr(self.db, "logs"):
            try:
                self.db.logs.insert_one({
                    "timestamp": datetime.now(timezone.utc),
                    "level": level,
                    "message": message,
                })
            except Exception:
                pass

    @staticmethod
    def _normalize_entity_id(entity_id):
        """Normalize channel ID to int if numeric, or string if username."""
        if entity_id is None:
            return None
        if isinstance(entity_id, int):
            return entity_id
        s = str(entity_id).strip()
        if (s.startswith("-") and s[1:].isdigit()) or s.isdigit():
            try:
                return int(s)
            except ValueError:
                return s
        return s

    async def start(self):
        """Start the forwarder and begin monitoring source channels."""
        if not self.client:
            self._log_event("ERROR", "Telegram client not initialized — cannot start forwarder")
            return

        try:
            await self.client.start()
            me = await self.client.get_me()
            username = getattr(me, 'username', None) or getattr(me, 'id', 'user')
            self._log_event("INFO", f"Telegram Forwarder engine connected as @{username}")

            self._running = True

            # Update Flask app status if accessible
            try:
                from src.web.api import forwarder_status
                forwarder_status["running"] = True
                forwarder_status["connected"] = True
                forwarder_status["last_update"] = datetime.now(timezone.utc).isoformat()
            except Exception:
                pass  # Flask app may not be running

            await self._run_forwarding_loop()

        except errors.FloodWaitError as e:
            self._log_event("WARNING", f"FLOOD_WAIT on startup: {e.seconds}s")
            await asyncio.sleep(e.seconds)
            if self._running:
                await self.start()  # Retry after flood wait
        except (errors.RPCError, ConnectionError, OSError) as e:
            self._log_event("ERROR", f"Connection error during forwarder start: {e}")
            if self._running:
                await self.auto_reconnect()
        except Exception as e:
            self._log_event("ERROR", f"Unexpected error starting forwarder: {e}")
            if self._running:
                await self.auto_reconnect()

    async def stop(self):
        """Stop the forwarder gracefully."""
        self._running = False
        if self.client:
            try:
                await self.client.disconnect()
            except Exception:
                pass
        try:
            from src.web.api import forwarder_status
            forwarder_status["running"] = False
            forwarder_status["connected"] = False
            forwarder_status["last_update"] = datetime.now(timezone.utc).isoformat()
        except Exception:
            pass
        self._log_event("INFO", "Telegram Forwarder engine stopped")

    async def _run_forwarding_loop(self):
        """Main loop: fetch source rules, process messages."""
        while self._running:
            try:
                # Get all forwarding rules from DB
                forwarding_rules = list(self.db.rules.find({"active": True}))

                for rule in forwarding_rules:
                    if not self._running:
                        break

                    source_id = rule.get("source_id")
                    target_id = rule.get("target_id")

                    if not source_id or not target_id:
                        continue

                    norm_source = self._normalize_entity_id(source_id)
                    norm_target = self._normalize_entity_id(target_id)

                    # Check blacklist
                    if self.rules_engine.is_blacklisted(norm_source) or \
                       self.rules_engine.is_blacklisted(norm_target):
                        logger.info(f"Skipping blacklisted channel: {norm_source} or {norm_target}")
                        continue

                    # Check flood wait
                    if self._is_flood_waited(norm_source):
                        continue

                    await self._process_channel(norm_source, norm_target, rule)

                check_interval = int(self.config.get("CHECK_INTERVAL", 30))
                for _ in range(check_interval):
                    if not self._running:
                        break
                    await asyncio.sleep(1)

            except errors.FloodWaitError as e:
                sid = locals().get("norm_source", 0) or locals().get("source_id", 0)
                await self._handle_flood_wait(sid, e.seconds)
            except errors.RPCError as e:
                logger.error(f"RPCError: {e}")
                await asyncio.sleep(self.config.get("RETRY_DELAY", 10))
            except Exception as e:
                logger.error(f"Unexpected error in forwarding loop: {e}", exc_info=True)
                await asyncio.sleep(self.config.get("RETRY_DELAY", 10))

    def _is_flood_waited(self, channel_id) -> bool:
        """Check if channel is still in flood wait."""
        wait_until = self._last_flood_wait.get(channel_id, 0)
        return time.time() < wait_until

    async def _handle_flood_wait(self, channel_id, seconds: int):
        """Handle FLOOD_WAIT by pausing and retrying later."""
        self._log_event("WARNING", f"⏳ Telegram FLOOD_WAIT on channel {channel_id}: waiting {seconds}s")
        self._last_flood_wait[channel_id] = time.time() + seconds + 5  # extra 5s buffer
        await asyncio.sleep(seconds)

    async def _process_channel(self, source_id, target_id, rule: dict):
        """Fetch new messages (text and media) from a source channel and forward them."""
        try:
            # Get channel entity
            source_entity = await self.client.get_entity(source_id)
            target_entity = await self.client.get_entity(target_id)

            # Fetch recent messages
            async for message in self.client.iter_messages(
                source_entity, limit=50, reverse=True
            ):
                if not self._running:
                    break

                has_text = bool(getattr(message, "message", None))
                has_media = bool(getattr(message, "media", None))

                if not has_text and not has_media:
                    continue

                # Check if already processed (duplicate prevention)
                post_key = f"{source_id}:{message.id}"
                if self._is_duplicate(post_key):
                    continue

                # Apply rules transformation to text if present
                raw_text = message.message or ""
                transformed_text = self.rules_engine.apply_rules(
                    raw_text, source_id, target_id
                ) if raw_text else ""

                # Forward the post (with media if present)
                await self._forward_message(message, target_entity, transformed_text)

                # Mark as processed
                self._mark_processed(post_key, message.id, source_id, target_id)

        except ValueError as e:
            self._log_event("ERROR", f"Entity not found for channel {source_id} → {target_id}: {e}")
        except Exception as e:
            self._log_event("ERROR", f"Error processing channel {source_id}: {e}")

    def _is_duplicate(self, post_key: str) -> bool:
        """Check if a post was already forwarded."""
        existing = self.db.processed_posts.find_one({"_id": post_key})
        return existing is not None

    def _mark_processed(self, post_key: str, message_id: int, source_id, target_id):
        """Record that a post was processed."""
        self.db.processed_posts.insert_one({
            "_id": post_key,
            "message_id": message_id,
            "source_id": source_id,
            "target_id": target_id,
            "forwarded_at": datetime.now(timezone.utc),
        })

    async def _forward_message(self, original_message, target_entity, transformed_text: str):
        """Forward a message (supporting media, photos, documents, and text) to the target."""
        try:
            has_media = bool(getattr(original_message, "media", None))
            src_id = getattr(original_message, 'chat_id', 'source')
            tgt_id = getattr(target_entity, 'id', target_entity)
            msg_id = getattr(original_message, 'id', '?')

            if has_media:
                # Forward media with transformed caption
                await self.client.send_file(
                    target_entity,
                    original_message.media,
                    caption=transformed_text or "",
                )
                self._log_event("INFO", f"✅ Forwarded post #{msg_id} [Media/File] from {src_id} to {tgt_id}")
            elif transformed_text:
                await self.client.send_message(target_entity, transformed_text)
                self._log_event("INFO", f"✅ Forwarded post #{msg_id} [Text] from {src_id} to {tgt_id}")
            else:
                await self.client.send_message(target_entity, "[Content not available]")
                self._log_event("INFO", f"✅ Forwarded post #{msg_id} from {src_id} to {tgt_id}")

        except errors.FloodWaitError as e:
            await self._handle_flood_wait(getattr(target_entity, "id", target_entity), e.seconds)
        except errors.RPCError as e:
            self._log_event("ERROR", f"RPCError forwarding message: {e}")
        except Exception as e:
            self._log_event("ERROR", f"Unexpected error forwarding: {e}")

    async def auto_reconnect(self):
        """Auto-reconnect logic for connection stability."""
        if not self.client:
            self._log_event("ERROR", "Cannot reconnect — Telethon client is not initialized")
            return False

        max_reconnects = self.config.get("MAX_RETRIES", 3)
        retry_delay = self.config.get("RETRY_DELAY", 10)

        for attempt in range(max_reconnects):
            try:
                if not self.client.is_connected():
                    self._log_event("WARNING", f"🔄 Attempting auto-reconnect ({attempt + 1}/{max_reconnects})...")
                    await self.client.connect()
                    self._log_event("INFO", f"✅ Reconnected successfully on attempt {attempt + 1}")
                    return True
            except Exception as e:
                self._log_event("WARNING", f"Reconnect attempt {attempt + 1} failed: {e}")
                await asyncio.sleep(retry_delay * (attempt + 1))

        self._log_event("ERROR", "Max reconnect attempts exceeded")
        return False
