"""
Web API
-------
Flask REST API for the Telegram Forwarder Pro dashboard.
Provides endpoints for:
- Starting/stopping the forwarder
- Managing forwarding rules (CRUD)
- Managing blacklist
- Viewing real-time logs
- Session management
"""

import os
import logging
import threading
import asyncio
from datetime import datetime, timezone
from flask import Flask, request, jsonify, render_template, send_from_directory
try:
    from flask_cors import CORS
except ImportError:
    # Minimal fallback CORS wrapper if flask_cors is not installed
    def CORS(app, **kwargs):
        pass

from dotenv import load_dotenv

from src.utils.config import load_config, get_config

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "config", ".env"))

app = Flask(
    __name__,
    template_folder=os.path.join(os.path.dirname(__file__), "..", "dashboard", "templates"),
    static_folder=os.path.join(os.path.dirname(__file__), "..", "dashboard", "static"),
)
CORS(app, supports_credentials=True)

# Global state
forwarder_status = {"running": False, "connected": False, "last_update": None}
_db_cache = None
_db_initialized = False
_engine_instance = None
_engine_thread = None
_engine_lock = threading.Lock()


def _to_db_id(raw_id):
    """Safely convert an ID to ObjectId if it's a valid 24-hex MongoDB ObjectId, else string."""
    if not raw_id:
        return raw_id
    try:
        import bson
        str_id = str(raw_id)
        if len(str_id) == 24 and bson.ObjectId.is_valid(str_id):
            return bson.ObjectId(str_id)
    except Exception:
        pass
    return str(raw_id)


def _log_event(db, level: str, message: str):
    """Log an operational event to logger and db.logs collection."""
    if level == "INFO":
        logger.info(message)
    elif level == "WARNING":
        logger.warning(message)
    elif level == "ERROR":
        logger.error(message)
    else:
        logger.debug(message)

    if db and hasattr(db, "logs"):
        try:
            db.logs.insert_one({
                "timestamp": datetime.now(timezone.utc),
                "level": level,
                "message": message,
            })
        except Exception:
            pass


def _start_forwarder_engine(config, db):
    """Start the forwarder engine in a background thread if not already running."""
    global _engine_instance, _engine_thread
    with _engine_lock:
        if _engine_instance and getattr(_engine_instance, "_running", False):
            return True

        from src.forwarder.engine import ForwarderEngine

        def run_forwarder():
            global _engine_instance
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                engine = ForwarderEngine(config, db)
                _engine_instance = engine
                loop.run_until_complete(engine.start())
            except Exception as e:
                logger.error(f"Forwarder engine worker failed: {e}", exc_info=True)
                forwarder_status["running"] = False
                forwarder_status["connected"] = False
            finally:
                loop.close()

        thread = threading.Thread(target=run_forwarder, daemon=True)
        _engine_thread = thread
        thread.start()
        _log_event(db, "INFO", "Forwarder engine thread spawned")
        return True


def _stop_forwarder_engine():
    """Stop the forwarder engine gracefully."""
    global _engine_instance
    with _engine_lock:
        if _engine_instance:
            try:
                _engine_instance._running = False
            except Exception as e:
                logger.warning(f"Error stopping forwarder engine: {e}")
        forwarder_status["running"] = False
        forwarder_status["connected"] = False
        forwarder_status["last_update"] = datetime.now(timezone.utc).isoformat()
        db = get_db()
        if db:
            _log_event(db, "INFO", "Forwarder engine stopped by user request")


def get_db():
    """Get the database connection, initializing if needed.

    Uses a module-level cache to avoid repeated initialization.
    Returns None if initialization fails.
    """
    global _db_cache, _db_initialized
    if _db_initialized:
        return _db_cache

    try:
        config = load_config()
        from src.utils.database import get_db_connection
        db = get_db_connection(config.get("MONGODB_URI", ""), config.get("MONGO_DB", "telegram_forwarder"))

        # Create default rules if none exist — wrapped so a failure here
        # never disables the entire database (e.g. MongoDB unreachable).
        try:
            if db.rules.count_documents({}) == 0:
                db.rules.insert_many([
                    {"name": "Strip @usernames", "type": "regex", "pattern": r"@\w+", "replacement": "[username]", "priority": 1, "active": True},
                    {"name": "Branding Footer", "type": "footer", "replacement": "Forwarded by Telegram Forwarder Pro", "priority": 99, "active": True},
                ])
                logger.info("Created default transformation rules")
        except Exception as e:
            logger.warning(f"Could not seed default rules (non-fatal): {e}")

        _db_cache = db
        _db_initialized = True
        logger.info(f"Database initialized: {type(db).__name__}")

        # Start forwarder engine only if explicitly enabled via AUTO_START_ENGINE
        if os.environ.get("AUTO_START_ENGINE", "").lower() in ("true", "1") and config.get("SESSION_STRING") and config.get("API_ID"):
            _start_forwarder_engine(config, db)

    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        _db_initialized = False
        _db_cache = None
        return None
    return _db_cache


# Initialize database at module load time (for gunicorn compatibility)
try:
    get_db()
except Exception as e:
    logger.error(f"Background DB initialization failed: {e}")


# --- API Routes ---

@app.route("/")
def dashboard():
    """Serve the main dashboard page."""
    return render_template("index.html")


@app.route("/api/status")
def api_status():
    """Get forwarder status."""
    return jsonify({
        "running": forwarder_status["running"],
        "connected": forwarder_status["connected"],
        "last_update": forwarder_status["last_update"],
    })


@app.route("/api/debug")
def api_debug():
    """Debug endpoint — shows config and DB connection status (development only)."""
    db = get_db()
    db_type = "none"
    db_error = None
    if db:
        db_type = type(db).__name__
    # Capture the last MongoDB connection error if any (from database module)
    try:
        from src.utils import database as _dbmod
        db_error = getattr(_dbmod, "_last_mongo_error", None)
    except Exception:
        db_error = None
    config = load_config()
    mongo_raw = config.get("MONGODB_URI", "")
    mongo_clean = mongo_raw.split("?")[0] if mongo_raw else ""
    # Show current deployed commit for diagnosis
    try:
        import subprocess
        _commit = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        _commit = "unknown"
    # Safe diagnostics without leaking credentials
    mongo_host = ""
    mongo_user = ""
    if mongo_clean:
        try:
            # mongodb+srv://user:pass@host/db
            rest = mongo_clean.split("://", 1)[1]
            user_part, host_part = rest.split("@", 1)
            mongo_user = user_part.split(":")[0] if ":" in user_part else user_part
            mongo_host = host_part.split("/")[0]
        except Exception:
            mongo_host = "(unparseable)"
    config_info = {
        "db_connected": db is not None,
        "db_type": db_type,
        "deploy_commit": _commit,
        "mongo_error": db_error,
        "mongo_uri_set": bool(os.environ.get("MONGODB_URI") or os.environ.get("MONGO_URI")),
        "mongo_force_fallback": os.environ.get("MONGODB_FORCE_FALLBACK", "false"),
        "mongo_user": mongo_user,
        "mongo_host": mongo_host,
        "mongo_uri_len": len(mongo_raw),
        "api_id_set": bool(os.environ.get("API_ID")),
        "api_hash_set": bool(os.environ.get("API_HASH")),
        "session_string_set": bool(os.environ.get("SESSION_STRING")),
        "config_mongodb_uri_set": bool(mongo_raw),
    }
    return jsonify(config_info)


@app.route("/api/rules")
def api_get_rules():
    """Get all forwarding rules for the authenticated user."""
    db = get_db()
    if not db:
        return jsonify({"rules": [], "warning": "Database not connected"}), 200

    from src.web.auth import get_current_user_from_request
    user = get_current_user_from_request(db)
    if not user:
        # Not logged in: show empty rules list for privacy
        return jsonify({"rules": [], "authenticated": False})

    user_id = str(user["_id"])
    try:
        rules = list(db.rules.find({"$or": [{"user_id": user_id}, {"user_id": None}, {"user_id": {"$exists": False}}]}))
        for rule in rules:
            rule["_id"] = str(rule["_id"])
        return jsonify({"rules": rules, "authenticated": True})
    except Exception as e:
        logger.error(f"Failed to fetch rules: {e}")
        return jsonify({"rules": [], "error": str(e)}), 200


@app.route("/api/rules", methods=["POST"])
def api_create_rule():
    """Create a new forwarding rule with multi-target and media types support."""
    db = get_db()
    if not db:
        return jsonify({"error": "Database not connected"}), 500
    try:
        from src.web.auth import get_current_user_from_request
        user = get_current_user_from_request(db)
        user_id = str(user["_id"]) if user else None

        data = request.get_json() or {}
        target_id = data.get("target_id", "")
        target_ids = data.get("target_ids")

        # Normalize target_ids from target_id if string with commas or list
        if not target_ids:
            if isinstance(target_id, list):
                target_ids = target_id
                target_id = ", ".join(str(t) for t in target_ids)
            elif isinstance(target_id, str) and ("," in target_id or "\n" in target_id):
                target_ids = [p.strip() for p in target_id.replace("\n", ",").split(",") if p.strip()]
            elif target_id:
                target_ids = [str(target_id).strip()]
            else:
                target_ids = []
        elif isinstance(target_ids, list) and not target_id:
            target_id = ", ".join(str(t) for t in target_ids)

        media_types = data.get("media_types")
        if media_types is None or not isinstance(media_types, list):
            media_types = ["photo", "video", "document", "audio", "text", "sticker"]

        rule = {
            "user_id": user_id,
            "name": data.get("name", "Unnamed Rule"),
            "type": data.get("type", "replace"),
            "source_id": data.get("source_id"),
            "target_id": target_id,
            "target_ids": target_ids,
            "media_types": media_types,
            "pattern": data.get("pattern", ""),
            "replacement": data.get("replacement", ""),
            "priority": data.get("priority", 0),
            "active": data.get("active", True),
        }
        result = db.rules.insert_one(rule)
        rule["_id"] = str(result.inserted_id)
        _log_event(db, "INFO", f"Rule '{rule['name']}' created ({rule.get('source_id')} → {rule.get('target_id')})")
        return jsonify({"success": True, "rule": rule})
    except Exception as e:
        logger.error(f"Failed to create rule: {e}")
        return jsonify({"error": "Failed to create rule", "detail": str(e)}), 500


@app.route("/api/rules/<rule_id>", methods=["DELETE"])
def api_delete_rule(rule_id):
    """Delete a forwarding rule."""
    db = get_db()
    if not db:
        return jsonify({"error": "Database not connected"}), 500
    object_id = _to_db_id(rule_id)
    db.rules.delete_one({"_id": object_id})
    _log_event(db, "INFO", f"Rule '{rule_id}' deleted")
    return jsonify({"success": True})


@app.route("/api/rules/<rule_id>", methods=["PUT"])
def api_update_rule(rule_id):
    """Update a forwarding rule."""
    db = get_db()
    if not db:
        return jsonify({"error": "Database not connected"}), 500

    data = request.get_json() or {}
    object_id = _to_db_id(rule_id)

    update_data = {}
    for key in ["name", "type", "pattern", "replacement", "priority", "active", "source_id", "target_id", "target_ids", "media_types"]:
        if key in data:
            update_data[key] = data[key]

    if "target_id" in update_data and "target_ids" not in update_data:
        tid = update_data["target_id"]
        if isinstance(tid, str) and ("," in tid or "\n" in tid):
            update_data["target_ids"] = [p.strip() for p in tid.replace("\n", ",").split(",") if p.strip()]
        elif tid:
            update_data["target_ids"] = [str(tid).strip()]

    db.rules.update_one({"_id": object_id}, {"$set": update_data})
    _log_event(db, "INFO", f"Rule '{rule_id}' updated")
    return jsonify({"success": True})


@app.route("/api/channels")
def api_get_my_channels():
    """Fetch all Telegram channels joined by the active account or user."""
    db = get_db()
    from src.web.auth import get_current_user_from_request, UserManager
    user = get_current_user_from_request(db) if db else None

    session_string = None
    if user and db:
        session_string = UserManager.get_user_telegram_session(db, str(user["_id"]))
    if not session_string:
        config = load_config()
        session_string = config.get("SESSION_STRING")

    if not session_string:
        return jsonify({"channels": [], "connected": False, "error": "No Telegram account connected."}), 200

    config = load_config()
    api_id = int(config.get("API_ID") or config.get("TELEGRAM_API_ID") or os.environ.get("API_ID", 0) or os.environ.get("TELEGRAM_API_ID", 0))
    api_hash = config.get("API_HASH") or config.get("TELEGRAM_API_HASH") or os.environ.get("API_HASH", "") or os.environ.get("TELEGRAM_API_HASH", "")

    from src.web.telegram_auth import fetch_user_telegram_dialogs
    result = asyncio.run(fetch_user_telegram_dialogs(api_id, api_hash, session_string))
    if result.get("success"):
        return jsonify({"channels": result.get("dialogs", []), "dialogs": result.get("dialogs", []), "connected": True})
    return jsonify({"channels": [], "error": result.get("error")}), 200


@app.route("/api/blacklist")
def api_get_blacklist():
    """Get all blacklisted channels."""
    db = get_db()
    if not db:
        return jsonify({"blacklist": [], "warning": "Database not connected"}), 200
    try:
        entries = list(db.blacklist.find({}))
        for entry in entries:
            entry["_id"] = str(entry["_id"])
        return jsonify({"blacklist": entries})
    except Exception as e:
        logger.error(f"Failed to fetch blacklist: {e}")
        return jsonify({"blacklist": [], "error": "Database query failed"}), 200


@app.route("/api/blacklist", methods=["POST"])
def api_add_blacklist():
    """Add a channel to the blacklist."""
    db = get_db()
    if not db:
        return jsonify({"error": "Database not connected"}), 500

    data = request.get_json()
    raw_channel_id = data.get("channel_id")
    channel_id = int(raw_channel_id) if str(raw_channel_id).lstrip("-").isdigit() else raw_channel_id

    entry = {
        "channel_id": channel_id,
        "reason": data.get("reason", "Blacklisted"),
        "added_at": datetime.now(timezone.utc),
    }
    result = db.blacklist.insert_one(entry)
    entry["_id"] = str(result.inserted_id)
    _log_event(db, "WARNING", f"Channel {channel_id} added to blacklist ({entry['reason']})")
    return jsonify({"success": True, "entry": entry})


@app.route("/api/blacklist/<channel_id>", methods=["DELETE"])
def api_remove_blacklist(channel_id):
    """Remove a channel from the blacklist."""
    db = get_db()
    if not db:
        return jsonify({"error": "Database not connected"}), 500

    cid = int(channel_id) if str(channel_id).lstrip("-").isdigit() else channel_id
    db.blacklist.delete_one({"channel_id": cid})
    _log_event(db, "INFO", f"Channel {cid} removed from blacklist")
    return jsonify({"success": True})


@app.route("/api/logs")
def api_get_logs():
    """Get recent logs."""
    db = get_db()
    if not db:
        return jsonify({"logs": [], "warning": "Database not connected"}), 200
    try:
        logs = list(db.logs.find({}).sort("timestamp", -1).limit(100))
        for log in logs:
            log["_id"] = str(log["_id"])
            if log.get("timestamp"):
                log["timestamp"] = log["timestamp"].isoformat() if hasattr(log["timestamp"], 'isoformat') else str(log["timestamp"])
        return jsonify({"logs": logs})
    except Exception as e:
        logger.error(f"Failed to fetch logs: {e}")
        return jsonify({"logs": [], "error": "Database query failed"}), 200


@app.route("/api/stats")
def api_get_stats():
    """Get aggregated statistics for the dashboard."""
    db = get_db()
    from src.web.auth import get_current_user_from_request
    user = get_current_user_from_request(db) if db else None

    if not user:
        return jsonify({
            "running": False,
            "connected": False,
            "telegram_connected": False,
            "telegram_username": None,
            "last_update": None,
            "total_rules": 0,
            "active_rules": 0,
            "total_forwarded": 0,
            "blacklist_count": 0,
            "logs_count": 0,
            "db_type": type(db).__name__ if db else "Disconnected",
        })

    user_id = str(user["_id"])
    tg_account = user.get("telegram_account") or {}
    tg_connected = bool(tg_account.get("session_string"))
    tg_username = tg_account.get("username") or tg_account.get("first_name")

    stats = {
        "running": forwarder_status.get("running", False) if tg_connected else False,
        "connected": tg_connected,
        "telegram_connected": tg_connected,
        "telegram_username": tg_username,
        "last_update": forwarder_status.get("last_update"),
        "total_rules": 0,
        "active_rules": 0,
        "total_forwarded": 0,
        "blacklist_count": 0,
        "logs_count": 0,
        "db_type": type(db).__name__ if db else "Disconnected",
    }
    if db:
        try:
            rules = list(db.rules.find({"$or": [{"user_id": user_id}, {"user_id": None}, {"user_id": {"$exists": False}}]}))
            stats["total_rules"] = len(rules)
            stats["active_rules"] = sum(1 for r in rules if r.get("active", True))
            stats["total_forwarded"] = len(list(db.processed_posts.find({})))
            stats["blacklist_count"] = len(list(db.blacklist.find({})))
            stats["logs_count"] = len(list(db.logs.find({})))
        except Exception as e:
            stats["error"] = str(e)
    return jsonify(stats)


@app.route("/api/rules/<rule_id>/toggle", methods=["POST"])
def api_toggle_rule(rule_id):
    """Toggle a rule's active state."""
    db = get_db()
    if not db:
        return jsonify({"error": "Database not connected"}), 500
    object_id = _to_db_id(rule_id)
    rule = db.rules.find_one({"_id": object_id})
    if not rule:
        return jsonify({"error": "Rule not found"}), 404
    new_status = not rule.get("active", True)
    db.rules.update_one({"_id": object_id}, {"$set": {"active": new_status}})
    _log_event(db, "INFO", f"Rule '{rule.get('name', rule_id)}' {'activated' if new_status else 'deactivated'}")
    return jsonify({"success": True, "active": new_status})


@app.route("/api/rules/test", methods=["POST"])
def api_test_rule():
    """Test text transformation against configured rules."""
    db = get_db()
    data = request.get_json() or {}
    text = data.get("text", "")
    source_id = data.get("source_id")
    target_id = data.get("target_id")
    from src.rules.engine import RulesEngine
    engine = RulesEngine(db=db)
    transformed = engine.apply_rules(text, source_id, target_id)
    return jsonify({
        "success": True,
        "original": text,
        "transformed": transformed,
        "changed": text != transformed,
    })


@app.route("/api/logs/clear", methods=["POST"])
def api_clear_logs():
    """Clear all stored logs."""
    db = get_db()
    if not db:
        return jsonify({"error": "Database not connected"}), 500
    try:
        if hasattr(db.logs, "delete_many"):
            db.logs.delete_many({})
        elif hasattr(db.logs, "table"):
            with db._lock:
                conn = db._get_conn()
                try:
                    conn.execute("DELETE FROM forwarding_logs")
                    conn.commit()
                finally:
                    conn.close()
        _log_event(db, "INFO", "Logs cleared by user")
        return jsonify({"success": True, "message": "Logs cleared"})
    except Exception as e:
        logger.error(f"Failed to clear logs: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/forwarder/status")
def api_forwarder_status():
    """Detailed forwarder status: Telegram connection + active forwarding rules."""
    db = get_db()
    info = dict(forwarder_status)
    if db:
        try:
            rules = list(db.rules.find({"active": True, "source_id": {"$ne": None}, "target_id": {"$ne": None}}))
            info["active_forwarding_rules"] = len(rules)
            info["db_type"] = type(db).__name__
        except Exception as e:
            info["db_error"] = str(e)[:200]
            info["active_forwarding_rules"] = 0
            info["db_type"] = None
    else:
        info["active_forwarding_rules"] = 0
        info["db_type"] = None
    return jsonify(info)


@app.route("/api/test-mongo")
def api_test_mongo():
    """Test MongoDB connection and return detailed results."""
    config = load_config()
    mongo_uri = config.get("MONGODB_URI", "")
    db_name = config.get("MONGO_DB", "telegram_forwarder")
    result = {
        "uri_preview": mongo_uri[:60] + "..." if len(mongo_uri) > 60 else mongo_uri,
        "db_name": db_name,
        "attempts": [],
    }

    try:
        from pymongo import MongoClient
        result["pymongo_version"] = "OK"
    except ImportError as e:
        result["pymongo_version"] = f"FAILED: {e}"
        return jsonify(result)

    try:
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=3000, connectTimeoutMS=3000, socketTimeoutMS=3000)
        client.admin.command("ping")
        result["attempts"].append({"step": "full_uri", "status": "success"})
        client.close()
    except Exception as e:
        result["attempts"].append({"step": "full_uri", "status": "failed", "error": str(e)[:300]})

    return jsonify(result)


@app.route("/api/forward/start", methods=["POST"])
def api_start_forwarder():
    """Start the forwarder engine for the active user."""
    from src.utils.config import load_config as lc
    config = lc()
    db = get_db()
    if not db:
        return jsonify({"error": "Database not connected"}), 500

    from src.web.auth import get_current_user_from_request, UserManager
    user = get_current_user_from_request(db)
    user_id = str(user["_id"]) if user else "default"

    session_string = None
    if user:
        session_string = UserManager.get_user_telegram_session(db, user_id)
    if not session_string:
        session_string = config.get("SESSION_STRING")

    if not session_string:
        return jsonify({"success": False, "error": "No Telegram account connected. Please connect your Telegram account first."}), 400

    from src.forwarder.worker_pool import worker_pool
    started = worker_pool.start_user_worker(user_id, session_string, config, db)
    if started:
        forwarder_status["running"] = True
        forwarder_status["connected"] = True
        forwarder_status["last_update"] = datetime.now(timezone.utc).isoformat()
        return jsonify({"success": True, "message": "Forwarder worker started"})
    return jsonify({"error": "Could not start forwarder worker"}), 500


@app.route("/api/forward/stop", methods=["POST"])
def api_stop_forwarder():
    """Stop the forwarder engine for the active user."""
    db = get_db()
    from src.web.auth import get_current_user_from_request
    user = get_current_user_from_request(db) if db else None
    user_id = str(user["_id"]) if user else "default"

    from src.forwarder.worker_pool import worker_pool
    worker_pool.stop_user_worker(user_id)
    _stop_forwarder_engine()

    forwarder_status["running"] = False
    forwarder_status["connected"] = False
    forwarder_status["last_update"] = datetime.now(timezone.utc).isoformat()
    return jsonify({"success": True, "message": "Forwarder worker stopped"})


# ==================== SAAS AUTHENTICATION & MULTI-USER ROUTES ====================
from src.web.auth import (
    UserManager,
    generate_auth_token,
    verify_auth_token,
    get_current_user_from_request,
    require_auth,
)
from src.web.telegram_auth import (
    send_telegram_login_code,
    verify_telegram_login_code,
)


@app.route("/api/auth/register", methods=["POST"])
def api_auth_register():
    """Register a new customer account."""
    db = get_db()
    if not db:
        return jsonify({"success": False, "error": "Database not connected"}), 500

    data = request.get_json() or {}
    email = data.get("email", "").strip()
    password = data.get("password", "").strip()
    name = data.get("name", "").strip()

    if not email or not password:
        return jsonify({"success": False, "error": "Email and password are required"}), 400

    try:
        user = UserManager.create_user(db, email, password, name)
        token = generate_auth_token(str(user["_id"]), user["email"])
        resp = jsonify({
            "success": True,
            "user": {
                "id": str(user["_id"]),
                "email": user["email"],
                "name": user.get("name", ""),
                "plan": user.get("plan", "free"),
                "role": user.get("role", "user"),
                "telegram_connected": bool(user.get("telegram_account")),
            },
            "token": token,
            "message": "Account created successfully"
        })
        resp.set_cookie("auth_token", token, max_age=30 * 86400, httponly=True, samesite="Lax")
        return resp
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        logger.error(f"Registration error: {e}")
        return jsonify({"success": False, "error": f"Registration failed: {str(e)}"}), 500


@app.route("/api/auth/login", methods=["POST"])
def api_auth_login():
    """Log in to user account."""
    db = get_db()
    if not db:
        return jsonify({"success": False, "error": "Database not connected"}), 500

    data = request.get_json() or {}
    email = data.get("email", "").strip()
    password = data.get("password", "").strip()

    try:
        user = UserManager.authenticate_user(db, email, password)
        if not user:
            return jsonify({"success": False, "error": "Invalid email or password"}), 401

        token = generate_auth_token(str(user["_id"]), user["email"])
        resp = jsonify({
            "success": True,
            "user": {
                "id": str(user["_id"]),
                "email": user["email"],
                "name": user.get("name", ""),
                "plan": user.get("plan", "free"),
                "role": user.get("role", "user"),
                "telegram_connected": bool(user.get("telegram_account")),
                "telegram_account": {
                    "username": user.get("telegram_account", {}).get("username", "") if user.get("telegram_account") else "",
                    "first_name": user.get("telegram_account", {}).get("first_name", "") if user.get("telegram_account") else "",
                } if user.get("telegram_account") else None
            },
            "token": token,
            "message": "Logged in successfully"
        })
        resp.set_cookie("auth_token", token, max_age=30 * 86400, httponly=True, samesite="Lax")
        return resp
    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({"success": False, "error": f"Login failed: {str(e)}"}), 500


@app.route("/api/auth/logout", methods=["POST"])
def api_auth_logout():
    """Log out and clear session."""
    resp = jsonify({"success": True, "message": "Logged out successfully"})
    resp.delete_cookie("auth_token")
    return resp


@app.route("/api/auth/me", methods=["GET"])
def api_auth_me():
    """Get current authenticated user profile and connected Telegram account status."""
    db = get_db()
    if not db:
        return jsonify({"authenticated": False}), 200

    user = get_current_user_from_request(db)
    if not user:
        return jsonify({
            "authenticated": False,
            "telegram_connected": False,
            "telegram_username": None
        })

    tg_account = user.get("telegram_account") or {}
    has_tg = bool(tg_account.get("session_string"))
    return jsonify({
        "authenticated": True,
        "user": {
            "id": str(user["_id"]),
            "email": user.get("email", ""),
            "name": user.get("name", ""),
            "plan": user.get("plan", "free"),
            "role": user.get("role", "user"),
            "telegram_connected": has_tg,
            "telegram_username": tg_account.get("username", ""),
            "telegram_first_name": tg_account.get("first_name", ""),
            "telegram_phone": tg_account.get("phone", ""),
        }
    })


@app.route("/api/auth/telegram/send-code", methods=["POST"])
def api_telegram_send_code():
    """Step 1: Send Telegram MTProto verification code to phone."""
    db = get_db()
    config = load_config()
    api_id = int(config.get("API_ID") or config.get("TELEGRAM_API_ID") or os.environ.get("API_ID", 0) or os.environ.get("TELEGRAM_API_ID", 0))
    api_hash = config.get("API_HASH") or config.get("TELEGRAM_API_HASH") or os.environ.get("API_HASH", "") or os.environ.get("TELEGRAM_API_HASH", "")

    if not api_id or not api_hash:
        return jsonify({"success": False, "error": "Telegram API credentials not configured on server"}), 500

    data = request.get_json() or {}
    phone_number = data.get("phone_number", "").strip()
    if not phone_number:
        return jsonify({"success": False, "error": "Phone number is required"}), 400

    user = get_current_user_from_request(db)
    user_id = str(user["_id"]) if user else f"guest_{phone_number}"

    result = asyncio.run(send_telegram_login_code(db, api_id, api_hash, phone_number, user_id))
    return jsonify(result)


@app.route("/api/auth/telegram/verify-code", methods=["POST"])
def api_telegram_verify_code():
    """Step 2: Verify Telegram MTProto login code and save session."""
    db = get_db()
    config = load_config()
    api_id = int(config.get("API_ID") or config.get("TELEGRAM_API_ID") or os.environ.get("API_ID", 0) or os.environ.get("TELEGRAM_API_ID", 0))
    api_hash = config.get("API_HASH") or config.get("TELEGRAM_API_HASH") or os.environ.get("API_HASH", "") or os.environ.get("TELEGRAM_API_HASH", "")

    if not api_id or not api_hash:
        return jsonify({"success": False, "error": "Telegram API credentials not configured on server"}), 500

    data = request.get_json() or {}
    code = data.get("code", "").strip()
    password = data.get("password", "")
    phone_number = data.get("phone_number", "").strip()

    if not code:
        return jsonify({"success": False, "error": "Verification code is required"}), 400

    user = get_current_user_from_request(db)
    user_id = str(user["_id"]) if user else f"guest_{phone_number}"

    result = asyncio.run(verify_telegram_login_code(db, api_id, api_hash, user_id, code, password, phone_number))

    if result.get("success"):
        tg_data = result.get("telegram_account", {})
        if user and db:
            # Save session to user profile
            UserManager.update_telegram_account(db, str(user["_id"]), tg_data)

        # Automatically start or update worker pool with newly connected session
        session_str = tg_data.get("session_string")
        if session_str and db:
            from src.forwarder.worker_pool import worker_pool
            user_id = str(user["_id"]) if user else "default"
            cfg = load_config()
            worker_pool.start_user_worker(user_id, session_str, cfg, db)

        forwarder_status["connected"] = True
        forwarder_status["running"] = True
        forwarder_status["last_update"] = datetime.now(timezone.utc).isoformat()

    return jsonify(result)


@app.route("/api/telegram/dialogs", methods=["GET"])
def api_telegram_dialogs():
    """Fetch list of user's Telegram channels and groups."""
    db = get_db()
    if not db:
        return jsonify({"success": False, "error": "Database not connected"}), 500

    from src.web.auth import get_current_user_from_request, UserManager
    user = get_current_user_from_request(db)
    if not user:
        return jsonify({"success": False, "error": "Please log in first"}), 401

    session_string = UserManager.get_user_telegram_session(db, str(user["_id"]))
    if not session_string:
        return jsonify({"success": False, "error": "No Telegram account connected. Please connect your account first."}), 400

    config = load_config()
    api_id = int(config.get("API_ID") or config.get("TELEGRAM_API_ID") or os.environ.get("API_ID", 0) or os.environ.get("TELEGRAM_API_ID", 0))
    api_hash = config.get("API_HASH") or config.get("TELEGRAM_API_HASH") or os.environ.get("API_HASH", "") or os.environ.get("TELEGRAM_API_HASH", "")

    from src.web.telegram_auth import fetch_user_telegram_dialogs
    result = asyncio.run(fetch_user_telegram_dialogs(api_id, api_hash, session_string))
    return jsonify(result)


@app.route("/api/auth/telegram/disconnect", methods=["POST"])
def api_telegram_disconnect():
    """Disconnect user's Telegram account and terminate active engine."""
    db = get_db()
    user = get_current_user_from_request(db) if db else None
    user_id = str(user["_id"]) if user else "default"

    # Stop active engine & worker completely
    from src.forwarder.worker_pool import worker_pool
    worker_pool.stop_user_worker(user_id)
    _stop_forwarder_engine()

    if user and db:
        UserManager.disconnect_telegram_account(db, str(user["_id"]))

    forwarder_status["running"] = False
    forwarder_status["connected"] = False
    forwarder_status["last_update"] = datetime.now(timezone.utc).isoformat()

    return jsonify({
        "success": True,
        "message": "Telegram account disconnected successfully.",
        "connected": False,
        "running": False
    })


_DEFAULT_CHANNEL_AVATAR_SVG = b"""<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 24 24" fill="#1e1b4b">
<rect width="24" height="24" rx="12" fill="#1e1b4b"/>
<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" fill="none" stroke="#818cf8" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
</svg>"""


@app.route("/api/telegram/avatar/<path:entity_id>")
def api_telegram_avatar(entity_id):
    """Serve channel/group profile avatar image or clean SVG badge (HTTP 200)."""
    entity_str = str(entity_id).strip()
    if not entity_str or entity_str.startswith("http") or entity_str == "undefined":
        from flask import Response
        resp = Response(_DEFAULT_CHANNEL_AVATAR_SVG, mimetype="image/svg+xml")
        resp.headers["Cache-Control"] = "public, max-age=86400"
        return resp

    target_entity = entity_str
    try:
        target_entity = int(entity_str)
    except ValueError:
        target_entity = entity_str.lstrip("@")

    db = get_db()
    from src.web.auth import get_current_user_from_request, UserManager
    user = get_current_user_from_request(db) if db else None

    session_string = None
    if user and db:
        session_string = UserManager.get_user_telegram_session(db, str(user["_id"]))
    if not session_string:
        config = load_config()
        session_string = config.get("SESSION_STRING")

    if session_string:
        try:
            config = load_config()
            api_id = int(config.get("API_ID") or config.get("TELEGRAM_API_ID") or os.environ.get("API_ID", 0) or os.environ.get("TELEGRAM_API_ID", 0))
            api_hash = config.get("API_HASH") or config.get("TELEGRAM_API_HASH") or os.environ.get("API_HASH", "") or os.environ.get("TELEGRAM_API_HASH", "")

            from src.web.telegram_auth import fetch_channel_avatar
            photo_bytes = asyncio.run(fetch_channel_avatar(api_id, api_hash, session_string, target_entity))
            if photo_bytes:
                from flask import Response
                resp = Response(photo_bytes, mimetype="image/jpeg")
                resp.headers["Cache-Control"] = "public, max-age=86400"
                return resp
        except Exception:
            pass

    from flask import Response
    resp = Response(_DEFAULT_CHANNEL_AVATAR_SVG, mimetype="image/svg+xml")
    resp.headers["Cache-Control"] = "public, max-age=86400"
    return resp


@app.errorhandler(400)
def bad_request(error):
    return jsonify({"success": False, "error": "Bad request", "detail": str(error)}), 400


@app.errorhandler(401)
def unauthorized(error):
    return jsonify({"success": False, "error": "Unauthorized", "detail": str(error)}), 401


@app.errorhandler(403)
def forbidden(error):
    return jsonify({"success": False, "error": "Forbidden", "detail": str(error)}), 403


@app.errorhandler(404)
def not_found(error):
    return jsonify({"success": False, "error": "Endpoint not found"}), 404


@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}", exc_info=True)
    return jsonify({"success": False, "error": "Internal server error", "detail": str(error)}), 500


@app.errorhandler(502)
def bad_gateway(error):
    return jsonify({"success": False, "error": "Bad gateway", "detail": str(error)}), 502


@app.errorhandler(503)
def service_unavailable(error):
    return jsonify({"success": False, "error": "Service temporarily unavailable", "detail": str(error)}), 503


@app.errorhandler(Exception)
def handle_unexpected_error(error):
    logger.error(f"Unhandled exception in request: {error}", exc_info=True)
    return jsonify({"success": False, "error": "Unexpected server error", "detail": str(error)}), 500


@app.route("/<path:catch_all>", methods=["GET", "POST"])
def catch_all(catch_all):
    """SPA fallback — serve index.html for any unmatched route."""
    if catch_all.startswith("api/"):
        return jsonify({"error": "Not found"}), 404
    return render_template("index.html")


if __name__ == "__main__":
    from src.utils.config import load_config as lc
    config = lc()
    app.run(
        host=config.get("WEB_HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", config.get("WEB_PORT", 5000))),
        debug=False,
        use_reloader=False,
    )
