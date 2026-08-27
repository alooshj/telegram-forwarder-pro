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
        self._entity_cache = {}     # channel_id/invite -> Telegram Entity

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
        clean_msg = message
        if "caused by CheckChatInviteRequest" in clean_msg:
            clean_msg = clean_msg.split("(caused by")[0].strip()
        if "A wait of" in clean_msg and "seconds is required" in clean_msg:
            clean_msg = f"⏳ Telegram Rate Limit: {clean_msg}"

        if level == "INFO":
            logger.info(clean_msg)
        elif level == "WARNING":
            logger.warning(clean_msg)
        elif level == "ERROR":
            logger.error(clean_msg)
        else:
            logger.debug(clean_msg)

        if self.db and hasattr(self.db, "logs"):
            try:
                self.db.logs.insert_one({
                    "timestamp": datetime.now(timezone.utc),
                    "level": level,
                    "message": clean_msg,
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
                    targets = self._get_rule_targets(rule)

                    if not source_id or not targets:
                        continue

                    norm_source = self._normalize_entity_id(source_id)

                    # Check blacklist on source
                    if self.rules_engine.is_blacklisted(norm_source):
                        logger.info(f"Skipping blacklisted source channel: {norm_source}")
                        continue

                    # Check flood wait on source
                    if self._is_flood_waited(norm_source):
                        continue

                    await self._process_channel_multi(norm_source, targets, rule)

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

    def _get_rule_targets(self, rule: dict) -> list:
        """Extract all target channel IDs (supports list, comma/newline-separated strings)."""
        targets = []
        if rule.get("target_ids") and isinstance(rule["target_ids"], list):
            targets.extend([t for t in rule["target_ids"] if t])
        elif rule.get("target_id"):
            raw = str(rule["target_id"])
            if "," in raw or "\n" in raw:
                parts = [p.strip() for p in raw.replace("\n", ",").split(",") if p.strip()]
                targets.extend(parts)
            else:
                targets.append(raw.strip())
        return targets

    def _detect_media_type(self, message) -> str:
        """Detect the media category of a Telethon message."""
        if not message:
            return "text"
        if getattr(message, "photo", None):
            return "photo"
        if getattr(message, "video", None) or getattr(message, "video_note", None):
            return "video"
        if getattr(message, "voice", None) or getattr(message, "audio", None):
            return "audio"
        if getattr(message, "sticker", None) or getattr(message, "gif", None):
            return "sticker"
        if getattr(message, "document", None):
            doc = message.document
            mime = getattr(doc, "mime_type", "") or ""
            if mime.startswith("audio/"):
                return "audio"
            elif mime.startswith("video/"):
                return "video"
            elif mime.startswith("image/"):
                return "photo"
            return "document"
        if getattr(message, "media", None):
            return "document"
        return "text"

    def _is_media_allowed(self, rule: dict, media_type: str) -> bool:
        """Check if media type is permitted by rule."""
        allowed = rule.get("media_types")
        if not allowed or not isinstance(allowed, list) or len(allowed) == 0:
            return True
        return media_type in allowed

    def _extract_invite_hash(self, entity_id) -> str:
        """Extract invite hash from private channel link if present (e.g. t.me/+hash or +hash)."""
        if not isinstance(entity_id, str):
            return None
        import re
        m = re.search(r'(?:t\.me\/(?:\+|joinchat\/)|\+)([a-zA-Z0-9_-]+)', entity_id)
        if m:
            return m.group(1)
        return None

    def _is_flood_waited(self, channel_id) -> bool:
        """Check if channel is still in flood wait."""
        wait_until = self._last_flood_wait.get(channel_id, 0)
        return time.time() < wait_until

    async def _handle_flood_wait(self, channel_id, seconds: int):
        """Handle FLOOD_WAIT by recording timestamp and pausing."""
        self._last_flood_wait[channel_id] = time.time() + seconds + 5  # extra 5s buffer
        self._log_event("WARNING", f"⏳ Telegram FloodWait on channel ({channel_id}): rate limited for {seconds}s (auto-paused).")
        await asyncio.sleep(seconds)

    async def _get_entity_safe(self, entity_id):
        """Get Telegram entity with automatic cache, dialogs refresh, and private invite handling."""
        if not entity_id:
            return None

        # Check in-memory cache
        if entity_id in self._entity_cache:
            return self._entity_cache[entity_id]

        # Check flood wait
        if self._is_flood_waited(entity_id):
            return None

        invite_hash = self._extract_invite_hash(str(entity_id))

        if invite_hash:
            # Handle private invite links
            try:
                # 1. Try to join private channel via invite hash
                from telethon.tl.functions.messages import ImportChatInviteRequest
                updates = await self.client(ImportChatInviteRequest(invite_hash))
                if hasattr(updates, 'chats') and updates.chats:
                    chat = updates.chats[0]
                    self._entity_cache[entity_id] = chat
                    self._log_event("INFO", f"🔗 Joined and resolved private channel: {entity_id}")
                    return chat
            except errors.UserAlreadyParticipantError:
                # Account is already in the channel! Find entity in dialogs
                try:
                    dialogs = await self.client.get_dialogs(limit=100)
                    for dialog in dialogs:
                        if getattr(dialog.entity, 'username', None) == entity_id:
                            self._entity_cache[entity_id] = dialog.entity
                            return dialog.entity
                except Exception:
                    pass
            except errors.FloodWaitError as e:
                await self._handle_flood_wait(entity_id, e.seconds)
                return None
            except (errors.InviteHashExpiredError, errors.InviteHashInvalidError):
                self._last_flood_wait[entity_id] = time.time() + 3600
                self._log_event("WARNING", f"⚠️ Private invite link has expired or is invalid: {entity_id}")
                return None
            except Exception as e:
                logger.debug(f"Invite import attempt: {e}")

        # Regular entity resolution (username, integer ID, etc.)
        try:
            entity = await self.client.get_entity(entity_id)
            if entity:
                self._entity_cache[entity_id] = entity
                return entity
        except errors.FloodWaitError as e:
            await self._handle_flood_wait(entity_id, e.seconds)
            return None
        except (ValueError, errors.RPCError):
            try:
                # Refresh cache by loading recent dialogs
                await self.client.get_dialogs(limit=100)
                entity = await self.client.get_entity(entity_id)
                if entity:
                    self._entity_cache[entity_id] = entity
                    return entity
            except errors.FloodWaitError as e:
                await self._handle_flood_wait(entity_id, e.seconds)
                return None
            except Exception:
                return None
        except Exception:
            return None

        return None

    async def _process_channel(self, source_id, target_id, rule: dict):
        """Backward-compatible single-target channel processing."""
        await self._process_channel_multi(source_id, [target_id], rule)

    async def _process_channel_multi(self, source_id, targets: list, rule: dict):
        """Fetch new messages (text and media) from a source channel and forward to multiple targets."""
        source_entity = await self._get_entity_safe(source_id)
        if not source_entity:
            if not self._is_flood_waited(source_id):
                self._log_event("WARNING", f"⚠️ Cannot access source channel ({source_id}). Ensure @ayg1133 is a member or use @username.")
            return

        # Prepare and validate target entities
        valid_targets = []
        for tgt in targets:
            norm_tgt = self._normalize_entity_id(tgt)
            if self.rules_engine.is_blacklisted(norm_tgt):
                logger.info(f"Skipping blacklisted target channel: {norm_tgt}")
                continue
            if self._is_flood_waited(norm_tgt):
                continue

            entity = await self._get_entity_safe(norm_tgt)
            if entity:
                valid_targets.append((norm_tgt, entity))
            else:
                if not self._is_flood_waited(norm_tgt):
                    self._log_event("WARNING", f"⚠️ Cannot access target channel ({tgt}). Ensure @ayg1133 is an admin.")

        if not valid_targets:
            return

        # Fetch recent messages from source
        try:
            async for message in self.client.iter_messages(
                source_entity, limit=50, reverse=True
            ):
                if not self._running:
                    break

                has_text = bool(getattr(message, "message", None))
                has_media = bool(getattr(message, "media", None))

                if not has_text and not has_media:
                    continue

                # Filter by media type
                media_type = self._detect_media_type(message)
                if not self._is_media_allowed(rule, media_type):
                    continue

                raw_text = message.message or ""

                # Forward to each target channel independently
                for norm_tgt, target_entity in valid_targets:
                    post_key = f"{source_id}:{message.id}:{norm_tgt}"
                    if self._is_duplicate(post_key, source_id, message.id):
                        continue

                    transformed_text = self.rules_engine.apply_rules(
                        raw_text, source_id, norm_tgt
                    ) if raw_text else ""

                    await self._forward_message(message, target_entity, transformed_text)
                    self._mark_processed(post_key, message.id, source_id, norm_tgt)

        except Exception as e:
            self._log_event("ERROR", f"Error processing messages from channel {source_id}: {e}")

    def _is_duplicate(self, post_key: str, source_id=None, message_id=None) -> bool:
        """Check if a post was already forwarded."""
        existing = self.db.processed_posts.find_one({"_id": post_key})
        if existing is not None:
            return True
        if source_id is not None and message_id is not None:
            legacy_key = f"{source_id}:{message_id}"
            legacy = self.db.processed_posts.find_one({"_id": legacy_key})
            if legacy is not None:
                return True
        return False

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
