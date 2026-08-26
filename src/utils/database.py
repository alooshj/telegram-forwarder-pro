# Telegram Forwarder Pro - Project Structure
# -------------------------------------------
# This module handles MongoDB storage operations including
# post history tracking, session data, user rules, and blacklist management.

from pymongo import MongoClient
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class MongoDB:
    """MongoDB connection manager for storing rules, sessions, and post history."""

    def __init__(self, mongo_uri: str, db_name: str):
        self.client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        self.db = self.client[db_name]
        self._test_connection()

    def _test_connection(self):
        try:
            self.client.admin.command('ping')
            logger.info("MongoDB connected successfully")
        except Exception as e:
            logger.error(f"MongoDB connection failed: {e}")
            raise

    def close(self):
        self.client.close()

    # --- Collections ---
    @property
    def rules(self):
        return self.db.forwarding_rules

    @property
    def sessions(self):
        return self.db.sessions

    @property
    def processed_posts(self):
        return self.db.processed_posts

    @property
    def blacklist(self):
        return self.db.blacklist

    @property
    def logs(self):
        return self.db.forwarding_logs
