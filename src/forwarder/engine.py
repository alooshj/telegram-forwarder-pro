"""
Forwarder Engine
----------------
Enterprise-Grade Telegram post forwarder using Telethon:
- Smart Forwarding Modes: FORWARD (official), COPY (clean stealth), AUTO_FALLBACK (auto in-memory copy on restricted channels)
- MediaGroupCollector (Debounce album buffering & multi-media batching)
- Advanced Transformation Pipeline: Whitelist/Blacklist keywords, media filters, mention/link stripping, dynamic templating
- Performance Protection: forward_delay (0-30s) and non-blocking per-target FloodWait scheduling
- Zero disk footprint in-memory ByteIO buffers
"""

import asyncio
import io
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from telethon import TelegramClient, errors, events
from telethon.sessions import StringSession

from src.forwarder.album_collector import MediaGroupCollector
from src.rules.engine import RulesEngine

logger = logging.getLogger(__name__)


class ForwarderEngine:
    """Enterprise-grade Telegram post forwarder with transformation, album buffering, and rate-limit handling."""

    def __init__(self, config: dict, db, user_id: str = None):
        self.config = config
        self.db = db
        self.user_id = str(user_id) if user_id else (str(config.get("USER_ID")) if config.get("USER_ID") else None)
        self.rules_engine = RulesEngine(db, user_id=self.user_id)
        self.album_collector = MediaGroupCollector(debounce_seconds=1.2)

        self._running = False
        self._last_flood_wait: Dict[Any, float] = {}  # target_id -> timestamp until available
        self._pending_flood = []
        self._entity_cache: Dict[Any, Any] = {}       # channel_id/invite -> Telegram Entity
        self.username = None
        self._channel_errors: Dict[str, int] = {}          # entity_id -> consecutive error count
        self._permanent_errors: Dict[str, float] = {}      # entity_id -> until timestamp (skip for 1 hour)
        self._channel_error_threshold = 5                   # after N errors, log single warning per cycle
        self._cooldown_base_seconds = 300                   # base cooldown: 5 minutes
        self._cooldown_max_seconds = 3600                   # max cooldown: 1 hour

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
                    "user_id": self.user_id or "system",
                })
            except Exception:
                pass

    def _handle_channel_error(self, entity_id, error: Exception) -> bool:
        """Track per-channel RPC errors, suppress log spam. Returns True if channel should be skipped."""
        err_type = type(error).__name__
        perm_key = f"{entity_id}"
        now = time.time()

        # If channel is in permanent error cooldown, skip silently
        if perm_key in self._permanent_errors and now < self._permanent_errors[perm_key]:
            return True

        # If channel is in MongoDB cooldown, skip silently
        if self._is_mongo_cooldown_active(entity_id):
            return True

        self._channel_errors[perm_key] = self._channel_errors.get(perm_key, 0) + 1
        count = self._channel_errors[perm_key]
        formatted = self._format_telethon_error(error)

        # Permanent errors → skip for 1 hour, log single warning
        if err_type in ("ChannelPrivateError", "ChannelInvalidError", "UserBannedInChannelError",
                         "ChatAdminRequiredError", "PeerIdInvalidError"):
            self._permanent_errors[perm_key] = now + 3600
            self._channel_errors.pop(perm_key, None)
            self._log_event("WARNING", f"⚠️ Channel {entity_id} permanently unavailable: {formatted}")
            return True

        # FloodWait / rate-limit errors → persist cooldown to MongoDB with exponential backoff
        if err_type in ("FloodWaitError", "FloodError") or "flood" in str(error).lower():
            cooldown_sec = self._get_cooldown_seconds(count)
            self._set_mongo_cooldown(entity_id, cooldown_sec)
            self._log_event("WARNING",
                f"Channel {entity_id} rate-limited ({err_type}), "
                f"cooldown {cooldown_sec}s ({cooldown_sec // 60}min). "
                f"Consecutive errors: {count}.")
            return True

        # Transient errors (timeout, connection) → suppress after threshold, set short cooldown
        if count <= self._channel_error_threshold:
            self._log_event("WARNING", f"⚠️ Channel {entity_id} error ({count}): {formatted}")
        elif count == self._channel_error_threshold + 1:
            cooldown_sec = self._get_cooldown_seconds(count)
            self._set_mongo_cooldown(entity_id, cooldown_sec)
            self._log_event("WARNING",
                f"Channel {entity_id} persistent errors ({count}), "
                f"cooldown {cooldown_sec}s ({cooldown_sec // 60}min).")

        return False

    def _clear_channel_error(self, entity_id):
        """Reset error count for a channel after successful operation."""
        self._channel_errors.pop(str(entity_id), None)
        self._permanent_errors.pop(str(entity_id), None)
        self._clear_mongo_cooldown(entity_id)

    # --- MongoDB-backed cooldown persistence ---

    def _set_mongo_cooldown(self, entity_id, seconds: int):
        """Persist a cooldown timestamp to MongoDB for a channel."""
        if not self.db:
            return
        try:
            from datetime import timedelta
            self.db.channel_cooldowns.update_one(
                {"_id": f"{self.user_id}:{entity_id}"},
                {"$set": {
                    "user_id": self.user_id,
                    "channel_id": str(entity_id),
                    "cooldown_until": datetime.now(timezone.utc) + timedelta(seconds=seconds),
                    "cooldown_seconds": seconds,
                    "updated_at": datetime.now(timezone.utc),
                }},
                upsert=True,
            )
        except Exception as e:
            logger.debug(f"Could not set MongoDB cooldown for {entity_id}: {e}")

    def _is_mongo_cooldown_active(self, entity_id) -> bool:
        """Check if a channel is currently in MongoDB-backed cooldown."""
        if not self.db:
            return False
        try:
            doc = self.db.channel_cooldowns.find_one({"_id": f"{self.user_id}:{entity_id}"})
            if not doc:
                return False
            cooldown_until = doc.get("cooldown_until")
            if not cooldown_until:
                return False
            if hasattr(cooldown_until, "tzinfo") and cooldown_until.tzinfo is None:
                from datetime import timezone as tz
                cooldown_until = cooldown_until.replace(tzinfo=tz.utc)
            if datetime.now(timezone.utc) < cooldown_until:
                return True
            self.db.channel_cooldowns.delete_one({"_id": f"{self.user_id}:{entity_id}"})
            return False
        except Exception:
            return False

    def _clear_mongo_cooldown(self, entity_id):
        """Remove cooldown for a channel from MongoDB."""
        if not self.db:
            return
        try:
            self.db.channel_cooldowns.delete_one({"_id": f"{self.user_id}:{entity_id}"})
        except Exception:
            pass

    def _get_cooldown_seconds(self, error_count: int) -> int:
        """Calculate exponential backoff cooldown: 5min -> 10min -> 20min -> ... -> 1hr max."""
        return min(self._cooldown_base_seconds * (2 ** min(error_count - 1, 6)), self._cooldown_max_seconds)

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
            self.username = getattr(me, 'username', None) or getattr(me, 'id', 'user')
            self._log_event("INFO", f"TeleTips engine connected as @{self.username}")

            self._running = True

            # Register real-time push event listener
            self._setup_event_handlers()

            # Update Flask app status if accessible
            try:
                from src.web.api import forwarder_status
                forwarder_status["running"] = True
                forwarder_status["connected"] = True
                forwarder_status["last_update"] = datetime.now(timezone.utc).isoformat()
            except Exception:
                pass

            await self._run_forwarding_loop()

        except errors.FloodWaitError as e:
            self._log_event("WARNING", f"FLOOD_WAIT on startup: {e.seconds}s")
            await asyncio.sleep(e.seconds)
            if self._running:
                await self.start()
        except (errors.RPCError, ConnectionError, OSError) as e:
            self._log_event("ERROR", f"Connection error during forwarder start: {e}")
            if self._running:
                await self.auto_reconnect()
        except Exception as e:
            self._log_event("ERROR", f"Unexpected error starting forwarder: {e}")
            if self._running:
                await self.auto_reconnect()

    def _get_active_rules(self) -> list:
        """Fetch active forwarding rules strictly for this user/tenant."""
        if not self.db or not hasattr(self.db, "rules"):
            return []
        query = {"active": True}
        if self.user_id:
            query["user_id"] = self.user_id
        return list(self.db.rules.find(query))

    def _setup_event_handlers(self):
        """Register real-time push listener so incoming messages and albums are forwarded instantly (< 1s)."""
        if not self.client or getattr(self, "_event_handlers_registered", False):
            return

        @self.client.on(events.NewMessage)
        async def _on_new_message(event):
            if not self._running:
                return

            try:
                chat_id = event.chat_id
                rules = self._get_active_rules()
                for rule in rules:
                    source_id = rule.get("source_id")
                    if not source_id:
                        continue

                    norm_source = self._normalize_entity_id(source_id)
                    matches = False

                    # 1. Match integer ID
                    if isinstance(norm_source, int) and norm_source == chat_id:
                        matches = True
                    # 2. Match username
                    elif hasattr(event.chat, 'username') and event.chat.username:
                        src_str = str(source_id).strip().lstrip('@').lower()
                        if event.chat.username.lower() == src_str:
                            matches = True
                    # 3. Match cached entity
                    elif source_id in self._entity_cache:
                        cached_id = getattr(self._entity_cache[source_id], 'id', None)
                        if cached_id and (cached_id == chat_id or f"-100{cached_id}" == str(chat_id)):
                            matches = True

                    if matches:
                        targets = self._get_rule_targets(rule)
                        if targets:
                            # If message is part of an album / media group, buffer it
                            if self.album_collector.is_grouped(event.message):
                                await self.album_collector.add_message(
                                    event.message, source_id, targets, rule, self._process_album_group
                                )
                            else:
                                await self._forward_event_message(event.message, source_id, targets, rule)
            except Exception as e:
                logger.debug(f"Error in real-time message handler: {e}")

        self._event_handlers_registered = True
        self._log_event("INFO", "⚡ Instant Real-Time Push Forwarding is active (< 1s latency)")

    async def _forward_event_message(self, message, source_id, targets: list, rule: dict):
        """Instantly process and forward a single incoming post in real-time."""
        try:
            has_text = bool(getattr(message, "message", None))
            has_media = bool(getattr(message, "media", None))

            if not has_text and not has_media:
                return

            # Media filtering
            media_type = self._detect_media_type(message)
            if not self._is_media_allowed(rule, media_type):
                self._log_event("INFO", f"⏩ Skipped real-time post #{message.id}: media type '{media_type}' disabled in rule.")
                return

            raw_text = message.message or ""

            for tgt in targets:
                norm_tgt = self._normalize_entity_id(tgt)
                if self.rules_engine.is_blacklisted(norm_tgt):
                    continue
                if self._is_flood_waited(norm_tgt):
                    continue

                post_key = f"{source_id}:{message.id}:{norm_tgt}"
                if self._is_duplicate(post_key, source_id, message.id):
                    continue

                target_entity = await self._get_entity_safe(norm_tgt)
                if not target_entity:
                    continue

                context = {
                    "source_id": source_id,
                    "target_id": norm_tgt,
                    "msg_id": message.id,
                }

                is_allowed, transformed_text, skip_reason = self.rules_engine.validate_and_transform(
                    raw_text, rule, source_id, norm_tgt, context
                )
                if not is_allowed:
                    self._log_event("INFO", f"⏩ Skipped post #{message.id} from {source_id}: {skip_reason}")
                    continue

                success = await self._forward_message(
                    message,
                    target_entity,
                    transformed_text,
                    media_type=media_type,
                    source_id=source_id,
                    target_id=norm_tgt,
                    rule=rule,
                )
                if success:
                    self._mark_processed(post_key, message.id, source_id, norm_tgt)

        except Exception as e:
            self._log_event("ERROR", f"Error in real-time forwarding for post #{getattr(message, 'id', '?')}: {e}")

    async def _process_album_group(self, group_data: dict):
        """Process and dispatch an assembled album / media group."""
        messages = group_data.get("messages", [])
        if not messages:
            return

        source_id = group_data.get("source_id")
        targets = group_data.get("targets", [])
        rule = group_data.get("rule", {})
        grouped_id = group_data.get("grouped_id")

        # Find first non-empty caption / text
        raw_caption = ""
        for m in messages:
            if getattr(m, "message", None):
                raw_caption = m.message
                break

        msg_ids = [getattr(m, "id", "?") for m in messages]
        first_msg = messages[0]

        # Process each target
        for tgt in targets:
            norm_tgt = self._normalize_entity_id(tgt)
            if self.rules_engine.is_blacklisted(norm_tgt) or self._is_flood_waited(norm_tgt):
                continue

            target_entity = await self._get_entity_safe(norm_tgt)
            if not target_entity:
                continue

            # Check if all items in album were already forwarded to this target
            all_dups = all(
                self._is_duplicate(f"{source_id}:{mid}:{norm_tgt}", source_id, mid)
                for mid in msg_ids
            )
            if all_dups:
                continue

            context = {
                "source_id": source_id,
                "target_id": norm_tgt,
                "msg_id": msg_ids[0],
            }

            is_allowed, transformed_caption, skip_reason = self.rules_engine.validate_and_transform(
                raw_caption, rule, source_id, norm_tgt, context
            )
            if not is_allowed:
                self._log_event("INFO", f"⏩ Skipped album #{grouped_id} from {source_id}: {skip_reason}")
                continue

            # Forward delay throttling
            delay = min(30.0, max(0.0, float(rule.get("forward_delay", 0) or 0)))
            if delay > 0:
                await asyncio.sleep(delay)

            success = await self._send_album_to_target(
                messages, target_entity, transformed_caption, source_id, norm_tgt, rule
            )
            if success:
                for mid in msg_ids:
                    post_key = f"{source_id}:{mid}:{norm_tgt}"
                    self._mark_processed(post_key, mid, source_id, norm_tgt)

    async def _send_album_to_target(
        self, messages: list, target_entity, caption: str, source_id, target_id, rule: dict
    ) -> bool:
        """Send bundled album messages to target."""
        mode = str(rule.get("forward_mode", "AUTO_FALLBACK")).upper().strip()
        grouped_id = getattr(messages[0], "grouped_id", "album")

        # 1. Official forward mode
        if mode == "FORWARD":
            try:
                await self.client.forward_messages(target_entity, messages)
                self._log_event("INFO", f"✅ Forwarded Album #{grouped_id} [{len(messages)} items] [FORWARD] from {source_id} ➔ {target_id}")
                return True
            except errors.ChatForwardsRestrictedError:
                if mode == "FORWARD":
                    self._log_event("ERROR", f"❌ Failed to forward album #{grouped_id} to {target_id}: [ChatForwardsRestrictedError] Source channel restricts forwarding.")
                    return False
            except Exception as e:
                self._log_event("ERROR", f"❌ Failed to forward album #{grouped_id} to {target_id}: {self._format_telethon_error(e)}")
                return False

        # 2. In-Memory Copy Mode (or AUTO_FALLBACK)
        try:
            # Download all media items in memory
            file_buffers = []
            for m in messages:
                if getattr(m, "media", None):
                    buf = io.BytesIO()
                    dl = await self.client.download_media(m, file=buf)
                    if dl:
                        buf.seek(0)
                        fn = getattr(getattr(m, "file", None), "name", None)
                        ext = getattr(getattr(m, "file", None), "ext", "") or ".jpg"
                        buf.name = fn or f"album_{getattr(m, 'id', 'item')}{ext}"
                        file_buffers.append(buf)

            if file_buffers:
                await self.client.send_file(
                    target_entity,
                    file_buffers,
                    caption=caption or "",
                )
                self._log_event("INFO", f"✅ Forwarded Album #{grouped_id} [{len(file_buffers)} items] [COPY] from {source_id} ➔ {target_id}")
                return True
            elif caption:
                await self.client.send_message(target_entity, caption)
                return True
            return False

        except errors.FloodWaitError as e:
            await self._handle_flood_wait(target_id, e.seconds)
            return False
        except Exception as e:
            self._log_event("ERROR", f"❌ Failed to send album #{grouped_id} to {target_id}: {self._format_telethon_error(e)}")
            return False

    async def stop(self):
        """Stop the forwarder gracefully."""
        self._running = False
        await self.album_collector.clear()
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
        self._log_event("INFO", "TeleTips engine stopped")

    async def _run_forwarding_loop(self):
        """Main background polling loop."""
        while self._running:
            try:
                forwarding_rules = self._get_active_rules()

                for rule in forwarding_rules:
                    if not self._running:
                        break

                    source_id = rule.get("source_id")
                    targets = self._get_rule_targets(rule)

                    if not source_id or not targets:
                        continue

                    norm_source = self._normalize_entity_id(source_id)

                    if self.rules_engine.is_blacklisted(norm_source) or self._is_flood_waited(norm_source):
                        continue

                    # Check MongoDB-backed cooldown (survives restarts)
                    if self._is_mongo_cooldown_active(norm_source):
                        continue

                    if self._handle_channel_error(norm_source, Exception("cooldown")):
                        continue

                    await self._process_channel_multi(norm_source, targets, rule)

                check_interval = int(self.config.get("CHECK_INTERVAL", 10))
                for _ in range(check_interval):
                    if not self._running:
                        break
                    await asyncio.sleep(1)

            except errors.FloodWaitError as e:
                sid = locals().get("norm_source", 0) or locals().get("source_id", 0)
                if sid:
                    self._set_mongo_cooldown(sid, e.seconds + 10)
                await self._handle_flood_wait(sid, e.seconds)
            except errors.RPCError as e:
                self._log_event("WARNING", f"RPCError in forwarding loop: {self._format_telethon_error(e)}")
                await asyncio.sleep(self.config.get("RETRY_DELAY", 10))
            except (errors.ChannelPrivateError, errors.ChannelInvalidError) as e:
                sid = locals().get("norm_source", 0) or locals().get("source_id", 0)
                self._handle_channel_error(sid, e)
                await asyncio.sleep(1)
            except (ConnectionError, TimeoutError, OSError) as e:
                sid = locals().get("norm_source", 0) or locals().get("source_id", 0)
                if sid:
                    self._set_mongo_cooldown(sid, 120)  # 2-minute cooldown on connection errors
                self._log_event("WARNING", f"⚠️ Connection error in forwarding loop: {e}")
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

    def _extract_invite_hash(self, entity_id) -> Optional[str]:
        """Extract invite hash from private channel link if present (e.g. t.me/+hash or +hash)."""
        if not isinstance(entity_id, str):
            return None
        import re
        m = re.search(r'(?:t\.me\/(?:\+|joinchat\/)|\+)([a-zA-Z0-9_-]+)', entity_id)
        if m:
            return m.group(1)
        return None

    def _is_flood_waited(self, channel_id) -> bool:
        """Non-blocking check if channel is still in flood wait."""
        wait_until = self._last_flood_wait.get(channel_id, 0)
        return time.time() < wait_until

    async def _handle_flood_wait(self, channel_id, seconds: int):
        """Handle FLOOD_WAIT per target — sleep the requested time AND persist to MongoDB."""
        self._last_flood_wait[channel_id] = time.time() + seconds + 5
        # Also persist to MongoDB so cooldown survives restarts
        self._set_mongo_cooldown(channel_id, seconds + 10)
        self._log_event("WARNING", f"⏳ Telegram FloodWait on channel ({channel_id}): rate limited for {seconds}s (cooldown persisted).")
        await asyncio.sleep(seconds)

    async def _get_entity_safe(self, entity_id):
        """Get Telegram entity with automatic cache, dialogs refresh, and private invite handling."""
        if not entity_id:
            return None

        if entity_id in self._entity_cache:
            return self._entity_cache[entity_id]

        if self._is_flood_waited(entity_id):
            return None

        if self._handle_channel_error(entity_id, Exception("cooldown")):
            return None

        invite_hash = self._extract_invite_hash(str(entity_id))

        if invite_hash:
            try:
                from telethon.tl.functions.messages import ImportChatInviteRequest
                updates = await self.client(ImportChatInviteRequest(invite_hash))
                if hasattr(updates, 'chats') and updates.chats:
                    chat = updates.chats[0]
                    self._entity_cache[entity_id] = chat
                    self._clear_channel_error(entity_id)
                    self._log_event("INFO", f"🔗 Joined and resolved private channel: {entity_id}")
                    return chat
            except errors.UserAlreadyParticipantError:
                try:
                    from telethon.tl.functions.messages import CheckChatInviteRequest
                    from telethon.tl.types import ChatInviteAlready
                    res = await self.client(CheckChatInviteRequest(invite_hash))
                    if isinstance(res, ChatInviteAlready) and res.chat:
                        self._entity_cache[entity_id] = res.chat
                        self._clear_channel_error(entity_id)
                        return res.chat
                except Exception:
                    pass
            except errors.FloodWaitError as e:
                await self._handle_flood_wait(entity_id, e.seconds)
                return None
            except (errors.InviteHashExpiredError, errors.InviteHashInvalidError):
                self._last_flood_wait[entity_id] = time.time() + 3600
                self._log_event("WARNING", f"⚠️ Private invite link has expired or is invalid: {entity_id}")
                return None
            except (errors.ChannelPrivateError, errors.ChannelInvalidError) as e:
                self._handle_channel_error(entity_id, e)
                return None
            except Exception as e:
                logger.debug(f"Invite import attempt: {e}")

        try:
            dialogs = await self.client.get_dialogs(limit=100)
            clean_lookup = str(entity_id).strip().lower().lstrip('@')
            for d in dialogs:
                if str(d.title or d.name or "").strip().lower() == clean_lookup:
                    self._entity_cache[entity_id] = d.entity
                    self._clear_channel_error(entity_id)
                    return d.entity
                if getattr(d.entity, 'username', None) and d.entity.username.lower() == clean_lookup:
                    self._entity_cache[entity_id] = d.entity
                    self._clear_channel_error(entity_id)
                    return d.entity
                if str(d.id) == str(entity_id) or str(getattr(d.entity, 'id', '')) == str(entity_id):
                    self._entity_cache[entity_id] = d.entity
                    self._clear_channel_error(entity_id)
                    return d.entity
        except (errors.ChannelPrivateError, errors.ChannelInvalidError) as e:
            self._handle_channel_error(entity_id, e)
            return None
        except Exception:
            pass

        try:
            entity = await self.client.get_entity(entity_id)
            if entity:
                self._entity_cache[entity_id] = entity
                self._clear_channel_error(entity_id)
                return entity
        except (errors.ChannelPrivateError, errors.ChannelInvalidError) as e:
            self._handle_channel_error(entity_id, e)
            return None
        except errors.FloodWaitError as e:
            await self._handle_flood_wait(entity_id, e.seconds)
            return None
        except Exception:
            return None

    async def get_my_channels(self):
        """Fetch all channels and groups joined by the userbot account."""
        if not self.client or not self.client.is_connected():
            return []
        try:
            dialogs = await self.client.get_dialogs(limit=100)
            channels = []
            for d in dialogs:
                if d.is_channel or d.is_group:
                    is_admin = False
                    if hasattr(d.entity, "admin_rights") and d.entity.admin_rights:
                        is_admin = True
                    elif getattr(d.entity, "creator", False):
                        is_admin = True

                    channels.append({
                        "id": str(d.id),
                        "numeric_id": d.id,
                        "title": d.title or d.name or str(d.id),
                        "username": f"@{d.entity.username}" if getattr(d.entity, "username", None) else None,
                        "is_admin": is_admin,
                        "is_channel": bool(d.is_channel),
                        "is_group": bool(d.is_group),
                    })
            return channels
        except Exception as e:
            logger.error(f"Error fetching user channels: {e}")
            return []

    async def _process_channel_multi(self, source_id, targets: list, rule: dict):
        """Fetch recent messages from source and dispatch to targets."""
        source_entity = await self._get_entity_safe(source_id)
        if not source_entity:
            return

        valid_targets = []
        for tgt in targets:
            norm_tgt = self._normalize_entity_id(tgt)
            if self.rules_engine.is_blacklisted(norm_tgt) or self._is_flood_waited(norm_tgt):
                continue
            # Check MongoDB-backed cooldown for target channels
            if self._is_mongo_cooldown_active(norm_tgt):
                continue
            if self._handle_channel_error(norm_tgt, Exception("cooldown")):
                continue
            entity = await self._get_entity_safe(norm_tgt)
            if entity:
                valid_targets.append((norm_tgt, entity))

        if not valid_targets:
            return

        try:
            async for message in self.client.iter_messages(source_entity, limit=50, reverse=True):
                if not self._running:
                    break

                # If message is part of an album, pass to album collector
                if self.album_collector.is_grouped(message):
                    await self.album_collector.add_message(
                        message, source_id, targets, rule, self._process_album_group
                    )
                    continue

                has_text = bool(getattr(message, "message", None))
                has_media = bool(getattr(message, "media", None))

                if not has_text and not has_media:
                    continue

                media_type = self._detect_media_type(message)
                if not self._is_media_allowed(rule, media_type):
                    continue

                raw_text = message.message or ""

                for norm_tgt, target_entity in valid_targets:
                    post_key = f"{source_id}:{message.id}:{norm_tgt}"
                    if self._is_duplicate(post_key, source_id, message.id):
                        continue

                    context = {
                        "source_id": source_id,
                        "target_id": norm_tgt,
                        "msg_id": message.id,
                    }

                    is_allowed, transformed_text, skip_reason = self.rules_engine.validate_and_transform(
                        raw_text, rule, source_id, norm_tgt, context
                    )
                    if not is_allowed:
                        continue

                    success = await self._forward_message(
                        message,
                        target_entity,
                        transformed_text,
                        media_type=media_type,
                        source_id=source_id,
                        target_id=norm_tgt,
                        rule=rule,
                    )
                    if success:
                        self._mark_processed(post_key, message.id, source_id, norm_tgt)
                        self._clear_channel_error(norm_tgt)

            self._clear_channel_error(source_id)

        except errors.FloodWaitError as e:
            await self._handle_flood_wait(source_id, e.seconds)
        except (errors.ChannelPrivateError, errors.ChannelInvalidError,
                errors.UserBannedInChannelError, errors.ChatAdminRequiredError,
                errors.PeerIdInvalidError) as e:
            self._handle_channel_error(source_id, e)
        except Exception as e:
            err_type = type(e).__name__
            if err_type in ("ConnectionError", "TimeoutError", "OSError"):
                self._log_event("WARNING", f"⚠️ Connection error for {source_id}: {self._format_telethon_error(e)}")
            else:
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
            "user_id": self.user_id or "system",
            "forwarded_at": datetime.now(timezone.utc),
        })

    def _format_telethon_error(self, exc: Exception) -> str:
        """Extract exact error class name and detailed, user-friendly explanation from Telethon / Telegram RPC errors."""
        err_type = type(exc).__name__
        err_msg = getattr(exc, "message", "") or str(exc)
        username = getattr(self, "username", None) or "Account"
        user_display = f"@{username}" if not str(username).startswith("@") else str(username)

        detail_map = {
            "ChatWriteForbiddenError": f"Account {user_display} has no permission to send messages. Make sure the account is an Admin with 'Post Messages' rights in target channel.",
            "ChatAdminRequiredError": "Administrator privileges required to post in target channel.",
            "ChannelPrivateError": f"Target channel is private and {user_display} is not a member.",
            "ChannelInvalidError": "Target channel is invalid or inaccessible.",
            "UserBannedInChannelError": f"Account {user_display} is banned or restricted in target channel.",
            "MessageEmptyError": "The message content became empty after text transformation rules.",
            "MediaEmptyError": "The media file was empty or could not be downloaded/retrieved from Telegram.",
            "MediaCaptionTooLongError": f"Caption is too long. Telegram limit is 1024 characters.",
            "PeerIdInvalidError": "Target channel ID or @username is invalid or not accessible by this account.",
            "FloodWaitError": f"Telegram FloodWait rate limit: auto-paused for {getattr(exc, 'seconds', '?')}s.",
            "SlowmodeWaitError": f"Channel slowmode active. Wait {getattr(exc, 'seconds', '?')}s before sending.",
            "MessageNotModifiedError": "Message content was identical to the original message.",
            "MessageTooLongError": "Message text exceeds Telegram's 4096 character limit.",
            "FilePartsInvalidError": "File upload parts failed or timed out.",
            "PhotoInvalidDimensionsError": "Photo dimensions are not supported by Telegram.",
            "BotResponseTimeoutError": "Target bot did not respond in time.",
            "ChatForwardsRestrictedError": "Source channel restricts forwarding. In-memory copy bypass mode activated.",
            "BadRequestError": f"Telegram rejected the request: {err_msg}",
            "RPCError": f"Telegram RPC error: {err_msg}",
        }

        explanation = detail_map.get(err_type)
        if explanation:
            return f"[{err_type}] {explanation}"

        if err_msg and err_msg != "None" and err_msg != "":
            return f"[{err_type}] {err_msg}"
        return f"[{err_type}] {str(exc)}"

    async def _forward_via_memory_copy(
        self, original_message, target_entity, transformed_text: str,
        media_type: str = "text", src_name=None, tgt_name=None, msg_id=None
    ) -> bool:
        """
        Fallback copy mode for restricted channels (ChatForwardsRestrictedError):
        Downloads media into in-memory buffer and sends as a fresh post under userbot account.
        Leaves 0 temporary files on disk.
        """
        try:
            has_media = bool(getattr(original_message, "media", None))
            if has_media:
                buffer = io.BytesIO()
                downloaded = await self.client.download_media(original_message, file=buffer)
                if downloaded:
                    buffer.seek(0)
                    filename = getattr(getattr(original_message, "file", None), "name", None)
                    ext = getattr(getattr(original_message, "file", None), "ext", "") or ".jpg"
                    buffer.name = filename or f"media_{msg_id}{ext}"

                    attributes = getattr(getattr(original_message, "file", None), "attributes", None) or []

                    await self.client.send_file(
                        target_entity,
                        buffer,
                        caption=transformed_text or "",
                        attributes=attributes,
                    )
                    self._log_event(
                        "INFO",
                        f"✅ Forwarded post #{msg_id} [RESTRICTED-BYPASS] [{media_type.upper()}] from {src_name} ➔ {tgt_name}"
                    )
                    return True
                else:
                    text_to_send = transformed_text or getattr(original_message, "message", "")
                    if text_to_send:
                        await self.client.send_message(target_entity, text_to_send)
                        self._log_event(
                            "INFO",
                            f"✅ Forwarded post #{msg_id} [RESTRICTED-TEXT] from {src_name} ➔ {tgt_name}"
                        )
                        return True
                    return False
            else:
                text_to_send = transformed_text or getattr(original_message, "message", "")
                if text_to_send:
                    await self.client.send_message(target_entity, text_to_send)
                    self._log_event(
                        "INFO",
                        f"✅ Forwarded post #{msg_id} [RESTRICTED-TEXT] from {src_name} ➔ {tgt_name}"
                    )
                    return True
                return False
        except Exception as copy_err:
            detailed = self._format_telethon_error(copy_err)
            self._log_event(
                "ERROR",
                f"❌ Failed to copy restricted post #{msg_id} to {tgt_name}: {detailed}"
            )
            return False

    async def _forward_message(
        self, original_message, target_entity, transformed_text: str,
        media_type: str = "text", source_id=None, target_id=None, rule: dict = None
    ) -> bool:
        """
        Forward a single message adhering to forward_mode (FORWARD, COPY, AUTO_FALLBACK)
        and applying forward_delay throttling.
        """
        src_name = source_id or getattr(original_message, 'chat_id', 'source')
        tgt_name = target_id or getattr(target_entity, 'id', target_entity)
        msg_id = getattr(original_message, 'id', '?')
        rule = rule or {}

        # 1. Forward Delay Throttling
        delay = min(30.0, max(0.0, float(rule.get("forward_delay", 0) or 0)))
        if delay > 0:
            await asyncio.sleep(delay)

        mode = str(rule.get("forward_mode", "AUTO_FALLBACK")).upper().strip()

        # 2. Direct Official FORWARD Mode
        if mode == "FORWARD":
            try:
                await self.client.forward_messages(target_entity, original_message)
                self._log_event(
                    "INFO",
                    f"✅ Forwarded post #{msg_id} [FORWARD] from {src_name} ➔ {tgt_name}"
                )
                return True
            except errors.ChatForwardsRestrictedError:
                self._log_event(
                    "ERROR",
                    f"❌ Failed to forward post #{msg_id} to {tgt_name}: [ChatForwardsRestrictedError] Source channel restricts forwarding."
                )
                return False
            except Exception as e:
                self._log_event(
                    "ERROR",
                    f"❌ Failed to forward post #{msg_id} to {tgt_name}: {self._format_telethon_error(e)}"
                )
                return False

        # 3. Clean Stealth COPY Mode
        if mode == "COPY":
            return await self._forward_via_memory_copy(
                original_message, target_entity, transformed_text,
                media_type=media_type, src_name=src_name, tgt_name=tgt_name, msg_id=msg_id
            )

        # 4. AUTO_FALLBACK Mode (Default)
        try:
            has_media = bool(getattr(original_message, "media", None))

            if has_media:
                await self.client.send_file(
                    target_entity,
                    original_message.media,
                    caption=transformed_text or "",
                )
                self._log_event(
                    "INFO",
                    f"✅ Forwarded post #{msg_id} [{media_type.upper()}] from {src_name} ➔ {tgt_name}"
                )
                return True
            elif transformed_text:
                await self.client.send_message(target_entity, transformed_text)
                self._log_event(
                    "INFO",
                    f"✅ Forwarded post #{msg_id} [TEXT] from {src_name} ➔ {tgt_name}"
                )
                return True
            elif getattr(original_message, "message", None):
                await self.client.send_message(target_entity, original_message.message)
                self._log_event(
                    "INFO",
                    f"✅ Forwarded post #{msg_id} [TEXT] from {src_name} ➔ {tgt_name}"
                )
                return True
            else:
                self._log_event(
                    "WARNING",
                    f"⏩ Skipped empty post #{msg_id} from {src_name} (no text or media content)"
                )
                return False

        except errors.FloodWaitError as e:
            await self._handle_flood_wait(tgt_name, e.seconds)
            return False
        except (errors.ChatForwardsRestrictedError, errors.RPCError, Exception) as e:
            err_name = type(e).__name__
            err_msg = getattr(e, "message", "") or str(e)

            # Auto-fallback to In-Memory Copy Mode when forwarding is restricted
            if "ChatForwardsRestricted" in err_name or "FORWARDS_RESTRICTED" in err_msg or "RESTRICTED" in err_msg:
                self._log_event(
                    "WARNING",
                    f"🛡️ Source channel {src_name} has restricted forwarding. Switching to In-Memory Copy Mode for post #{msg_id}..."
                )
                return await self._forward_via_memory_copy(
                    original_message, target_entity, transformed_text,
                    media_type, src_name, tgt_name, msg_id
                )

            detailed_err = self._format_telethon_error(e)
            self._log_event(
                "ERROR",
                f"❌ Failed to forward post #{msg_id} to {tgt_name}: {detailed_err}"
            )
            return False

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
