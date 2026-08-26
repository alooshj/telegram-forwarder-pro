"""
Database Module
---------------
Handles persistent storage for Telegram Forwarder Pro.

Supports two backends:
1. MongoDB (primary) — for production with Atlas free tier
2. SQLite (fallback) — for local dev or when MongoDB is unavailable

The backend is selected automatically based on which URI is provided.
"""

import os
import sqlite3
import threading
from datetime import datetime

# Re-export bson.ObjectId for external use, with fallback
try:
    from bson import ObjectId
    from bson.objectid import ObjectId as BsonObjectId
    from pymongo import MongoClient
    MONGO_AVAILABLE = True
except ImportError:
    MONGO_AVAILABLE = False
    BsonObjectId = None
    MongoClient = None
    class ObjectId:
        """Fallback ObjectId — returns the string as-is."""
        def __init__(self, str_rep=None):
            self._str = str(str_rep) if str_rep else ""
        def __str__(self):
            return self._str

import logging

logger = logging.getLogger(__name__)


class SQLiteDB:
    """SQLite fallback database — used when MongoDB is unavailable."""

    _lock = threading.Lock()

    def __init__(self, db_path: str = "data/forwarder.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_schema()
        logger.info(f"SQLite database initialized at {db_path}")

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self):
        with self._lock:
            conn = self._get_conn()
            try:
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS forwarding_rules (
                        _id TEXT PRIMARY KEY,
                        name TEXT,
                        type TEXT,
                        source_id TEXT,
                        target_id TEXT,
                        pattern TEXT,
                        replacement TEXT,
                        priority INTEGER DEFAULT 0,
                        active BOOLEAN DEFAULT 1
                    );
                    CREATE TABLE IF NOT EXISTS blacklist (
                        _id TEXT PRIMARY KEY,
                        channel_id INTEGER UNIQUE,
                        reason TEXT,
                        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE TABLE IF NOT EXISTS processed_posts (
                        _id TEXT PRIMARY KEY,
                        message_id INTEGER,
                        source_id INTEGER,
                        target_id INTEGER,
                        forwarded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE TABLE IF NOT EXISTS forwarding_logs (
                        _id TEXT PRIMARY KEY,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        level TEXT,
                        message TEXT
                    );
                """)
                conn.commit()
            finally:
                conn.close()

    # --- Forwarding Rules ---
    @property
    def rules(self):
        return _SQLiteCollection(self, "forwarding_rules")

    @property
    def blacklist(self):
        return _SQLiteCollection(self, "blacklist")

    @property
    def processed_posts(self):
        return _SQLiteCollection(self, "processed_posts")

    @property
    def logs(self):
        return _SQLiteCollection(self, "forwarding_logs")

    def create_collection(self, name):
        """Mongo-style compatibility."""
        pass

    def close(self):
        pass


class _SQLiteCollection:
    """Wrapper that mimics MongoDB collection interface for SQLite."""

    def __init__(self, db, table_name):
        self.db = db
        self.table = table_name

    def find(self, filter=None, **kwargs):
        """Find documents matching filter."""
        query = f"SELECT * FROM {self.table}"
        params = []

        if filter:
            conditions = []
            for key, value in filter.items():
                if key == "_id":
                    conditions.append("_id = ?")
                    params.append(value)
                elif isinstance(value, dict):
                    # Handle MongoDB-style operators ($eq, $ne, etc.) — basic support
                    for op, val in value.items():
                        if op == "$eq":
                            conditions.append(f"{key} = ?")
                            params.append(val)
                        elif op == "$ne":
                            conditions.append(f"{key} != ?")
                            params.append(val)
                        elif op == "$in":
                            placeholders = ",".join(["?" for _ in val])
                            conditions.append(f"{key} IN ({placeholders})")
                            params.extend(val)
                else:
                    conditions.append(f"{key} = ?")
                    params.append(str(value))
            if conditions:
                query += " WHERE " + " AND ".join(conditions)

        if kwargs.get("sort"):
            sort_key, sort_dir = kwargs["sort"]
            query += f" ORDER BY {sort_key} {'DESC' if sort_dir else 'ASC'}"

        if kwargs.get("limit"):
            query += f" LIMIT {kwargs['limit']}"

        with self.db._lock:
            conn = self.db._get_conn()
            try:
                cursor = conn.execute(query, params)
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
            finally:
                conn.close()

    def find_one(self, filter=None, **kwargs):
        """Find a single document."""
        results = self.find(filter, **kwargs)
        return results[0] if results else None

    def insert_one(self, document):
        """Insert a new document."""
        keys = list(document.keys())
        placeholders = ",".join(["?" for _ in keys])
        columns = ",".join(keys)
        values = tuple(str(v) if isinstance(v, datetime) else v for v in document.values())

        with self.db._lock:
            conn = self.db._get_conn()
            try:
                conn.execute(
                    f"INSERT INTO {self.table} ({columns}) VALUES ({placeholders})",
                    values
                )
                conn.commit()
            except sqlite3.IntegrityError:
                # Update instead of duplicate
                pass
            finally:
                conn.close()

        # Return mock ObjectId
        class _InsertedId:
            def __str__(self):
                return str(document.get("_id", ""))
        return type("InsertResult", (), {"inserted_id": _InsertedId()})

    def delete_one(self, filter):
        """Delete a document matching filter."""
        conditions = []
        params = []
        for key, value in filter.items():
            if key == "_id":
                conditions.append("_id = ?")
                params.append(value)
            else:
                conditions.append(f"{key} = ?")
                params.append(str(value))
        if conditions:
            query = f"DELETE FROM {self.table} WHERE {' AND '.join(conditions)}"
            with self.db._lock:
                conn = self.db._get_conn()
                try:
                    conn.execute(query, params)
                    conn.commit()
                finally:
                    conn.close()

    def update_one(self, filter, update, **kwargs):
        """Update documents matching filter."""
        set_clause = update.get("$set", {})
        if not set_clause:
            return
        conditions = []
        params = []
        for key, value in filter.items():
            if key == "_id":
                conditions.append("_id = ?")
                params.append(value)
            else:
                conditions.append(f"{key} = ?")
                params.append(str(value))

        set_parts = [f"{k} = ?" for k in set_clause.keys()]
        set_params = list(set_clause.values()) + params

        with self.db._lock:
            conn = self.db._get_conn()
            try:
                conn.execute(
                    f"UPDATE {self.table} SET {', '.join(set_parts)} WHERE {' AND '.join(conditions)}",
                    set_params
                )
                conn.commit()
            finally:
                conn.close()

    def count_documents(self, filter=None):
        """Count documents matching filter."""
        query = f"SELECT COUNT(*) as count FROM {self.table}"
        params = []
        if filter:
            conditions = [f"{k} = ?" for k in filter]
            params = [str(v) for v in filter.values()]
            query += " WHERE " + " AND ".join(conditions)

        with self.db._lock:
            conn = self.db._get_conn()
            try:
                cursor = conn.execute(query, params)
                return cursor.fetchone()["count"]
            finally:
                conn.close()

    def create_index(self, field, **kwargs):
        """No-op for SQLite — indexes handled by schema."""
        pass

    def insert_many(self, documents):
        """Insert multiple documents."""
        if not documents:
            return
        first = documents[0]
        keys = list(first.keys())
        placeholders = ",".join(["?" for _ in keys])
        columns = ",".join(keys)

        rows = []
        for doc in documents:
            vals = tuple(str(v) if isinstance(v, datetime) else v for v in doc.values())
            rows.append(vals)

        with self.db._lock:
            conn = self.db._get_conn()
            try:
                conn.executemany(
                    f"INSERT INTO {self.table} ({columns}) VALUES ({placeholders})",
                    rows
                )
                conn.commit()
            except sqlite3.IntegrityError:
                pass
            finally:
                conn.close()

    def sort(self, key, direction):
        """Mongo-style sort."""
        return self.find(sort=(key, direction != -1))


class MongoDB:
    """MongoDB connection manager for storing rules, sessions, and post history."""

    def __init__(self, mongo_uri: str, db_name: str):
        if not MONGO_AVAILABLE:
            raise ImportError("pymongo is not installed")

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


def get_db_connection(mongo_uri: str, db_name: str):
    """Factory: try MongoDB first, fall back to SQLite if MongoDB is unavailable."""
    # Log what we're working with
    logger.info(f"Attempting DB connection with URI: {mongo_uri[:50]}...{mongo_uri[-10:] if len(mongo_uri) > 60 else ''}")
    logger.info(f"DB name: {db_name}, URI starts with: {mongo_uri[:20]}")

    # If MongoDB URI is explicitly set and looks valid, try MongoDB
    if mongo_uri and not mongo_uri.startswith("mongodb://localhost") and not mongo_uri.startswith("mongodb+srv://"):
        logger.warning(f"Unrecognized MongoDB URI scheme — falling back to SQLite")

    if mongo_uri and (mongo_uri.startswith("mongodb://") or mongo_uri.startswith("mongodb+srv://")):
        try:
            db = MongoDB(mongo_uri, db_name)
            logger.info("Using MongoDB backend")
            return db
        except Exception as e:
            logger.error(f"MongoDB connection failed with URI '{mongo_uri[:80]}...': {e}")
            logger.error(f"Falling back to SQLite...")

    # Fallback to SQLite
    sqlite_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "..", "data", f"{db_name}.db"
    )
    os.makedirs(os.path.dirname(sqlite_path), exist_ok=True)
    db = SQLiteDB(sqlite_path)
    logger.info("Using SQLite fallback backend")
    return db
