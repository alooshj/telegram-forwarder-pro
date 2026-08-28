"""
Dynamic Multi-Tenant Client Manager (Worker Pool)
-------------------------------------------------
Manages isolated Telethon forwarder client instances per tenant/user.
Provides:
- Independent ForwarderEngine per user session
- Per-user FloodWait isolation
- Safe concurrency and lifecycle management
"""

import asyncio
import logging
import threading
import time
from typing import Dict, Optional
from src.utils.encryption import decrypt_session

logger = logging.getLogger(__name__)


class UserWorker:
    """Represents an isolated forwarder worker for a single user."""

    def __init__(self, user_id: str, session_string: str, config: dict, db):
        self.user_id = user_id
        self.raw_session = session_string
        self.decrypted_session = decrypt_session(session_string)
        self.config = dict(config)
        self.config["SESSION_STRING"] = self.decrypted_session
        self.db = db
        self.engine = None
        self.thread: Optional[threading.Thread] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.is_running = False
        self.started_at = 0
        self.last_error = None

    def start(self):
        """Start the user forwarder engine in a dedicated thread."""
        if self.is_running:
            return True

        from src.forwarder.engine import ForwarderEngine

        def _runner():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            try:
                self.engine = ForwarderEngine(self.config, self.db)
                self.is_running = True
                self.started_at = time.time()
                logger.info(f"Worker started for user {self.user_id}")
                self.loop.run_until_complete(self.engine.start())
            except Exception as e:
                self.last_error = str(e)
                logger.error(f"Worker for user {self.user_id} encountered an error: {e}", exc_info=True)
            finally:
                self.is_running = False
                if self.loop and not self.loop.is_closed():
                    try:
                        self.loop.close()
                    except Exception:
                        pass

        self.thread = threading.Thread(target=_runner, daemon=True, name=f"Worker-{self.user_id}")
        self.thread.start()
        return True

    def stop(self):
        """Stop the user forwarder engine gracefully."""
        self.is_running = False
        if self.engine:
            try:
                self.engine._running = False
            except Exception:
                pass


class WorkerPool:
    """Central singleton managing all active user workers."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(WorkerPool, cls).__new__(cls)
                cls._instance._workers: Dict[str, UserWorker] = {}
        return cls._instance

    def start_user_worker(self, user_id: str, session_string: str, config: dict, db) -> bool:
        """Start or restart a worker for a specific user."""
        with self._lock:
            if user_id in self._workers:
                self.stop_user_worker(user_id)

            worker = UserWorker(user_id, session_string, config, db)
            started = worker.start()
            if started:
                self._workers[user_id] = worker
            return started

    def stop_user_worker(self, user_id: str) -> bool:
        """Stop and remove a user's active worker."""
        with self._lock:
            worker = self._workers.pop(user_id, None)
            if worker:
                worker.stop()
                logger.info(f"Stopped worker for user {user_id}")
                return True
            return False

    def is_user_running(self, user_id: str) -> bool:
        """Check if a specific user worker is currently active."""
        with self._lock:
            worker = self._workers.get(user_id)
            return bool(worker and worker.is_running)

    def stop_all(self):
        """Stop all workers in the pool."""
        with self._lock:
            for uid, worker in list(self._workers.items()):
                worker.stop()
            self._workers.clear()


# Global pool singleton
worker_pool = WorkerPool()
