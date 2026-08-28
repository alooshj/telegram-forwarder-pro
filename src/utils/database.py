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
import json
from datetime import datetime, timezone

# Re-export bson.ObjectId for external use, with fallback
# certifi provides CA certificates needed for MongoDB Atlas TLS on some platforms (Render, etc.)
try:
    import certifi
    _MONGO_TLS_CA = certifi.where()
except ImportError:
    _MONGO_TLS_CA = None

# Re-export bson.ObjectId for external use, with fallback
try:
    from pymongo import MongoClient
    import bson
    ObjectId = bson.ObjectId
    BsonObjectId = bson.ObjectId
    MONGO_AVAILABLE = True
except ImportError:
    MONGO_AVAILABLE = False
    BsonObjectId = None
    MongoClient = None
    import uuid
    class ObjectId:
        """Fallback ObjectId — returns generated hex id if None, else string representation."""
        def __init__(self, str_rep=None):
            self._str = str(str_rep) if str_rep is not None and str_rep != "" else uuid.uuid4().hex[:24]
        def __str__(self):
            return self._str
        def __repr__(self):
            return self._str

import logging

logger = logging.getLogger(__name__)


class SQLiteDB:
    """SQLite fallback database — used when MongoDB is unavailable."""

    _lock = threading.Lock()

    def __init__(self, db_path: str = "data/forwarder.db"):
        self.db_path = db_path
        self._mem_conn = None
        if db_path == ":memory:":
            self._mem_conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._mem_conn.row_factory = sqlite3.Row
        else:
            dirname = os.path.dirname(db_path)
            if dirname:
                os.makedirs(dirname, exist_ok=True)
        self._init_schema()
        logger.info(f"SQLite database initialized at {db_path}")

    def _get_conn(self):
        if self._mem_conn is not None:
            return self._mem_conn
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _close_conn(self, conn):
        if self._mem_conn is None and conn:
            conn.close()

    def _init_schema(self):
        with self._lock:
            conn = self._get_conn()
            try:
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS forwarding_rules (
                        _id TEXT PRIMARY KEY,
                        user_id TEXT,
                        name TEXT,
                        type TEXT,
                        source_id TEXT,
                        target_id TEXT,
                        target_ids TEXT,
                        media_types TEXT,
                        forward_mode TEXT,
                        forward_delay REAL DEFAULT 0,
                        whitelist_keywords TEXT,
                        blacklist_keywords TEXT,
                        strip_mentions BOOLEAN DEFAULT 0,
                        strip_links BOOLEAN DEFAULT 0,
                        header_template TEXT,
                        footer_template TEXT,
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
                        user_id TEXT,
                        message_id INTEGER,
                        source_id INTEGER,
                        target_id INTEGER,
                        forwarded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE TABLE IF NOT EXISTS forwarding_logs (
                        _id TEXT PRIMARY KEY,
                        user_id TEXT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        level TEXT,
                        message TEXT
                    );
                    CREATE TABLE IF NOT EXISTS users (
                        _id TEXT PRIMARY KEY,
                        email TEXT UNIQUE,
                        name TEXT,
                        password_hash TEXT,
                        plan TEXT DEFAULT 'trial',
                        role TEXT DEFAULT 'client',
                        subscription_status TEXT DEFAULT 'trial',
                        subscription_expires_at TIMESTAMP,
                        max_target_channels INTEGER DEFAULT 2,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        telegram_account TEXT,
                        updated_at TIMESTAMP
                    );
                    CREATE TABLE IF NOT EXISTS transactions (
                        _id TEXT PRIMARY KEY,
                        order_id TEXT UNIQUE,
                        user_id TEXT,
                        plan_id TEXT,
                        plan_name TEXT,
                        amount REAL,
                        currency TEXT DEFAULT 'USD',
                        payment_provider TEXT,
                        transaction_id TEXT,
                        status TEXT DEFAULT 'pending',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        completed_at TIMESTAMP
                    );
                    CREATE TABLE IF NOT EXISTS license_keys (
                        _id TEXT PRIMARY KEY,
                        key_code TEXT UNIQUE,
                        plan_id TEXT,
                        plan_name TEXT,
                        duration_days INTEGER,
                        created_by TEXT,
                        is_redeemed INTEGER DEFAULT 0,
                        redeemed_by TEXT,
                        redeemed_at TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        notes TEXT
                    );
                    CREATE TABLE IF NOT EXISTS pending_auth (
                        _id TEXT PRIMARY KEY,
                        phone TEXT,
                        phone_code_hash TEXT,
                        temp_session TEXT,
                        created_at REAL
                    );
                """)
                # Migrations for forwarding_rules
                for col in ["target_ids", "media_types", "user_id", "forward_mode", "forward_delay", "whitelist_keywords", "blacklist_keywords", "strip_mentions", "strip_links", "header_template", "footer_template"]:
                    try:
                        conn.execute(f"ALTER TABLE forwarding_rules ADD COLUMN {col} TEXT;")
                    except sqlite3.OperationalError:
                        pass
                # Migrations for users
                for col in ["subscription_status", "subscription_expires_at", "max_target_channels", "plan", "role", "is_frozen", "frozen_reason"]:
                    try:
                        conn.execute(f"ALTER TABLE users ADD COLUMN {col} TEXT;")
                    except sqlite3.OperationalError:
                        pass
                conn.commit()
            finally:
                self._close_conn(conn)

    # --- Forwarding Rules & Auth ---
    @property
    def users(self):
        return _SQLiteCollection(self, "users")

    @property
    def transactions(self):
        return _SQLiteCollection(self, "transactions")

    @property
    def license_keys(self):
        return _SQLiteCollection(self, "license_keys")

    @property
    def pending_auth(self):
        return _SQLiteCollection(self, "pending_auth")

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


class _SQLiteCursor:
    """Cursor wrapper for SQLite query results that supports chaining (.sort, .limit) and iteration."""

    def __init__(self, collection, filter_query=None, sort_tuple=None, limit_val=None):
        self.collection = collection
        self.filter_query = filter_query
        self.sort_tuple = sort_tuple
        self.limit_val = limit_val
        self._cached_results = None

    def sort(self, key_or_list, direction=1):
        if isinstance(key_or_list, list):
            self.sort_tuple = key_or_list[0] if key_or_list else None
        elif isinstance(key_or_list, str):
            self.sort_tuple = (key_or_list, direction)
        self._cached_results = None
        return self

    def limit(self, limit_val):
        self.limit_val = int(limit_val) if limit_val is not None else None
        self._cached_results = None
        return self

    def _execute(self):
        if self._cached_results is None:
            self._cached_results = self.collection._execute_find(
                self.filter_query, sort=self.sort_tuple, limit=self.limit_val
            )
        return self._cached_results

    def __iter__(self):
        return iter(self._execute())

    def __len__(self):
        return len(self._execute())

    def __getitem__(self, index):
        return self._execute()[index]


class _SQLiteCollection:
    """Wrapper that mimics MongoDB collection interface for SQLite."""

    def __init__(self, db, table_name):
        self.db = db
        self.table = table_name

    def find(self, filter=None, **kwargs):
        """Find documents matching filter, returns a cursor supporting .sort() and .limit()."""
        sort_val = kwargs.get("sort")
        limit_val = kwargs.get("limit")
        return _SQLiteCursor(self, filter_query=filter, sort_tuple=sort_val, limit_val=limit_val)

    def _execute_find(self, filter=None, sort=None, limit=None):
        """Execute the SQL find query."""
        query = f"SELECT * FROM {self.table}"
        params = []

        if filter:
            conditions = []
            for key, value in filter.items():
                if key == "_id":
                    conditions.append("_id = ?")
                    params.append(str(value))
                elif value is None:
                    conditions.append(f"{key} IS NULL")
                elif isinstance(value, bool):
                    conditions.append(f"{key} = ?")
                    params.append(1 if value else 0)
                elif isinstance(value, dict):
                    # Handle MongoDB-style operators ($eq, $ne, $in, etc.)
                    for op, val in value.items():
                        if op == "$eq":
                            if val is None:
                                conditions.append(f"{key} IS NULL")
                            elif isinstance(val, bool):
                                conditions.append(f"{key} = ?")
                                params.append(1 if val else 0)
                            else:
                                conditions.append(f"{key} = ?")
                                params.append(val)
                        elif op == "$ne":
                            if val is None:
                                conditions.append(f"{key} IS NOT NULL")
                            elif isinstance(val, bool):
                                conditions.append(f"{key} != ?")
                                params.append(1 if val else 0)
                            else:
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

        if sort:
            sort_key, sort_dir = sort
            dir_str = "DESC" if (sort_dir == -1 or sort_dir is False or str(sort_dir).upper() == "DESC") else "ASC"
            query += f" ORDER BY {sort_key} {dir_str}"

        if limit is not None:
            query += f" LIMIT {int(limit)}"

        with self.db._lock:
            conn = self.db._get_conn()
            try:
                cursor = conn.execute(query, params)
                rows = cursor.fetchall()
                results = []
                for row in rows:
                    d = dict(row)
                    for col in ["target_ids", "media_types", "telegram_account", "whitelist_keywords", "blacklist_keywords"]:
                        if col in d and isinstance(d[col], str) and (d[col].startswith("[") or d[col].startswith("{")):
                            try:
                                d[col] = json.loads(d[col])
                            except Exception:
                                pass
                    results.append(d)
                return results
            finally:
                self.db._close_conn(conn)

    def find_one(self, filter=None, **kwargs):
        """Find a single document."""
        results = self._execute_find(filter, sort=kwargs.get("sort"), limit=1)
        return results[0] if results else None

    def insert_one(self, document):
        """Insert a new document."""
        # Auto-generate _id if not present
        doc = dict(document)
        if "_id" not in doc or not doc["_id"]:
            generated_id = str(ObjectId())
            doc["_id"] = generated_id
            if isinstance(document, dict):
                document["_id"] = generated_id
        else:
            generated_id = str(doc["_id"])

        def _ser_val(v):
            if isinstance(v, datetime):
                return str(v)
            if isinstance(v, (list, dict)):
                return json.dumps(v)
            return v

        keys = list(doc.keys())
        placeholders = ",".join(["?" for _ in keys])
        columns = ",".join(keys)
        values = tuple(_ser_val(v) for v in doc.values())

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
                self.db._close_conn(conn)

        # Return mock InsertResult
        class _InsertedId:
            def __init__(self, val):
                self._val = val
            def __str__(self):
                return str(self._val)
            def __repr__(self):
                return str(self._val)
        return type("InsertResult", (), {"inserted_id": _InsertedId(generated_id)})()

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

        def _ser_val(v):
            if isinstance(v, datetime):
                return str(v)
            if isinstance(v, (list, dict)):
                return json.dumps(v)
            return v

        set_parts = [f"{k} = ?" for k in set_clause.keys()]
        set_params = [_ser_val(v) for v in set_clause.values()] + params

        with self.db._lock:
            conn = self.db._get_conn()
            try:
                conn.execute(
                    f"UPDATE {self.table} SET {', '.join(set_parts)} WHERE {' AND '.join(conditions)}",
                    set_params
                )
                conn.commit()
            finally:
                self.db._close_conn(conn)

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
                self.db._close_conn(conn)

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
                self.db._close_conn(conn)

    def sort(self, key, direction):
        """Mongo-style sort."""
        return self.find(sort=(key, direction != -1))


class MongoDB:
    """MongoDB connection manager for storing rules, sessions, and post history."""

    def __init__(self, mongo_uri: str, db_name: str):
        if not MONGO_AVAILABLE:
            raise ImportError("pymongo is not installed")

        # TLS/SSL configuration for MongoDB Atlas.
        # Can be controlled via MONGODB_TLS_ALLOW_INVALID_CERTS env var (defaults to true on Render).
        allow_insecure_tls = os.environ.get("MONGODB_TLS_ALLOW_INVALID_CERTS", "true").lower() in ("true", "1", "yes")
        base_kwargs = {
            "serverSelectionTimeoutMS": 10000,
            "connectTimeoutMS": 10000,
            "socketTimeoutMS": 10000,
            "retryWrites": True,
            "w": "majority",
            "appname": "TelegramForwarderPro",
            "tls": True,
            "tlsAllowInvalidCertificates": allow_insecure_tls,
        }
        if _MONGO_TLS_CA:
            base_kwargs["tlsCAFile"] = _MONGO_TLS_CA

        # IMPORTANT: The Atlas-generated URI sometimes ends with
        # "?appName=Cluster0" (or retryWrites params). Passing appName inside
        # the connection string query can trigger a TLS handshake alert on
        # certain Python/OpenSSL builds (TLSV1_ALERT_INTERNAL_ERROR).
        # We strip query params from the URI and pass appname as a kwarg instead.
        clean_uri = mongo_uri.split("?")[0] if mongo_uri else mongo_uri

        try:
            self.client = MongoClient(clean_uri, **base_kwargs)
            self.db = self.client[db_name]
            self._test_connection()
        except Exception as e:
            logger.error(f"MongoDB connection failed: {e}")
            raise

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
    def users(self):
        return self.db.users

    @property
    def pending_auth(self):
        return self.db.pending_auth

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
        # Strip query params (Atlas appends ?appName=Cluster0&retryWrites=true...).
        # Passing appName inside the URI query can trigger a TLS handshake alert
        # (TLSV1_ALERT_INTERNAL_ERROR) on some OpenSSL builds — pass it as kwarg instead.
        clean_uri = mongo_uri.split("?")[0]
        logger.info(f"Attempting MongoDB connection to: {clean_uri[:40]}... (params stripped)")
        try:
            db = MongoDB(clean_uri, db_name)
            logger.info("Using MongoDB backend")
            return db
        except Exception as e:
            _last_mongo_error = f"{type(e).__name__}: {str(e)[:400]}"
            logger.error(f"MongoDB connection failed: {_last_mongo_error}")
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
