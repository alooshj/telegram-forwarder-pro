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
import ssl
from datetime import datetime

# Re-export bson.ObjectId for external use, with fallback
try:
    from pymongo import MongoClient
    import bson
    ObjectId = bson.ObjectId
    BsonObjectId = bson.ObjectId
    MONGO_AVAILABLE = True
    # certifi provides CA certificates needed for MongoDB Atlas TLS on some platforms (Render, etc.)
    try:
        import certifi
        _MONGO_TLS_CA = certifi.where()
    except ImportError:
        _MONGO_TLS_CA = None
except ImportError:
    MONGO_AVAILABLE = False
    BsonObjectId = None
    MongoClient = None
    _MONGO_TLS_CA = None
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
        # Auto-generate _id if not present
        doc = dict(document)
        if "_id" not in doc or not doc["_id"]:
            doc["_id"] = str(ObjectId())

        keys = list(doc.keys())
        placeholders = ",".join(["?" for _ in keys])
        columns =",".join(keys)
        values = tuple(str(v) if isinstance(v, datetime) else v for v in doc.values())

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
        # Auto-generate _id and ensure consistent column ordering
        docs = []
        all_keys = set()

        for doc in documents:
            d = dict(doc)
            if "_id" not in d or not d["_id"]:
                d["_id"] = str(ObjectId())
            # Reorder: _id first, then all other keys
            ordered = {"_id": d["_id"]}
            for k in d:
                if k != "_id":
                    ordered[k] = d[k]
            docs.append(ordered)
            all_keys.update(ordered.keys())

        # Use a consistent column order across all documents
        # Sort: _id first, then alphabetical for stability
        sorted_keys = sorted(all_keys, key=lambda x: (x != "_id", x))
        columns = ",".join(sorted_keys)
        placeholders = ",".join(["?" for _ in sorted_keys])

        rows = []
        for doc in docs:
            # Build row in the same column order
            vals = []
            for col in sorted_keys:
                v = doc.get(col)
                if isinstance(v, datetime):
                    v = str(v)
                vals.append(v)
            rows.append(tuple(vals))

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

        # TLS/SSL CA certificates — required for MongoDB Atlas on platforms
        # where the system CA bundle is incomplete (e.g. Render, some Linux images)
        client_kwargs = {
            "serverSelectionTimeoutMS": 10000,
            "connectTimeoutMS": 10000,
            "socketTimeoutMS": 10000,
            "retryWrites": True,
            "w": "majority",
            "appname": "TelegramForwarderPro",
            "tls": True,
            "tlsAllowInvalidCertificates": False,
        }
        if _MONGO_TLS_CA:
            client_kwargs["tlsCAFile"] = _MONGO_TLS_CA

        # IMPORTANT: The Atlas-generated URI sometimes ends with
        # "?appName=Cluster0" (or retryWrites params). Passing appName inside
        # the connection string query can trigger a TLS handshake alert on
        # certain Python/OpenSSL builds (TLSV1_ALERT_INTERNAL_ERROR).
        # We strip query params from the URI and pass appname as a kwarg instead.
        clean_uri = mongo_uri.split("?")[0] if mongo_uri else mongo_uri
        self.client = MongoClient(clean_uri, **client_kwargs)
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
    """Factory: try MongoDB first, fall back to SQLite if MongoDB is unavailable.

    If MONGODB_FORCE_FALLBACK=true is set in env, always use SQLite.
    Otherwise, attempt MongoDB and fall back automatically on any failure.
    """
    global _last_mongo_error
    _last_mongo_error = None

    # Allow forcing SQLite via env var (useful when Atlas rejects SSL/IP)
    force_fallback = os.environ.get("MONGODB_FORCE_FALLBACK", "").lower() in ("true", "1", "yes")

    # If MongoDB URI is explicitly set and looks valid, try MongoDB (unless forced to fallback)
    if not force_fallback and mongo_uri and (mongo_uri.startswith("mongodb://") or mongo_uri.startswith("mongodb+srv://")):
        try:
            db = MongoDB(mongo_uri, db_name)
            logger.info("Using MongoDB backend")
            return db
        except Exception as e:
            _last_mongo_error = f"{type(e).__name__}: {str(e)[:400]}"
            logger.error(f"MongoDB connection failed: {_last_mongo_error}")
            # Check if it's an SRV resolution issue (missing dnspython) — give a clear hint
            if "localhost" in str(e) and "srv" in mongo_uri.lower():
                logger.error("SRV URI failed to resolve — ensure 'dnspython' is installed.")
            logger.warning("Falling back to SQLite...")

    # Fallback to SQLite
    sqlite_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "..", "data", f"{db_name}.db"
    )
    os.makedirs(os.path.dirname(sqlite_path), exist_ok=True)
    db = SQLiteDB(sqlite_path)
    logger.info(f"Using SQLite fallback backend at {sqlite_path}")
    return db


_last_mongo_error = None
