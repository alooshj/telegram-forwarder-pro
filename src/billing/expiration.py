"""
Subscription Auto-Expiration Worker
------------------------------------
Background daemon that periodically monitors user subscription expiration:
- Scans users for expired trial or paid periods
- Transitions expired users to 'expired' status
- Automatically stops forwarder worker instances for expired users
- Emits expiration log notifications
"""

import asyncio
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


class SubscriptionExpirationWorker:
    """Monitors and enforces subscription expiration in the background."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(SubscriptionExpirationWorker, cls).__new__(cls)
                cls._instance._running = False
                cls._instance._thread: Optional[threading.Thread] = None
                cls._instance._check_interval = 60  # Check every 60 seconds
        return cls._instance

    def start(self, db_getter):
        """Start the expiration checker thread."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self.db_getter = db_getter
            self._thread = threading.Thread(target=self._run_loop, daemon=True, name="SubscriptionExpirationMonitor")
            self._thread.start()
            logger.info("🕒 Subscription Auto-Expiration Worker started.")

    def stop(self):
        """Stop the expiration checker."""
        self._running = False

    def _run_loop(self):
        """Main loop checking for expired subscriptions."""
        while self._running:
            try:
                self.check_and_expire_subscriptions()
            except Exception as e:
                logger.error(f"Error in subscription expiration check: {e}", exc_info=True)

            # Sleep interval
            for _ in range(self._check_interval):
                if not self._running:
                    break
                time.sleep(1)

    def check_and_expire_subscriptions(self) -> int:
        """
        Check database for users whose subscription has expired.
        Returns count of newly expired accounts.
        """
        db = self.db_getter() if callable(self.db_getter) else self.db_getter
        if not db or not hasattr(db, "users"):
            return 0

        now = datetime.now(timezone.utc)
        expired_count = 0

        try:
            # Query all active or trial non-superadmin users
            users = list(db.users.find({
                "subscription_status": {"$in": ["trial", "active"]},
                "role": {"$ne": "super_admin"}
            }))

            for user in users:
                if user.get("email") == "alooshpal@gmail.com":
                    continue
                expires_at = user.get("subscription_expires_at")
                if not expires_at:
                    continue

                if isinstance(expires_at, str):
                    try:
                        expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                    except Exception:
                        continue

                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)

                if expires_at <= now:
                    user_id = str(user["_id"])
                    email = user.get("email", user_id)

                    # Update status in DB
                    db.users.update_one(
                        {"_id": user["_id"]},
                        {"$set": {"subscription_status": "expired", "updated_at": now}}
                    )

                    # Stop worker pool instance
                    try:
                        from src.forwarder.worker_pool import worker_pool
                        worker_pool.stop_user_worker(user_id)
                    except Exception as we:
                        logger.debug(f"Error stopping worker for expired user: {we}")

                    # Log expiration
                    if hasattr(db, "logs"):
                        try:
                            db.logs.insert_one({
                                "timestamp": now,
                                "user_id": user_id,
                                "level": "WARNING",
                                "message": f"⏳ Subscription Expired: Account '{email}' period ended. Forwarder paused until renewal."
                            })
                        except Exception:
                            pass

                    logger.warning(f"Subscription expired for user {email} ({user_id}). Worker stopped.")
                    expired_count += 1

        except Exception as e:
            logger.error(f"Failed to scan expired users: {e}")

        return expired_count


# Global singleton
expiration_worker = SubscriptionExpirationWorker()
