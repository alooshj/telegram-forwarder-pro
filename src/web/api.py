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
import uuid
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

        # Migrate unassigned legacy rules to primary user if present
        try:
            if hasattr(db, "users") and hasattr(db, "rules") and db.users.count_documents({}) > 0:
                first_user = db.users.find_one({}, sort=[("created_at", 1)])
                if first_user:
                    first_user_id = str(first_user["_id"])
                    db.rules.update_many(
                        {"$or": [{"user_id": None}, {"user_id": {"$exists": False}}]},
                        {"$set": {"user_id": first_user_id}}
                    )
        except Exception as e:
            logger.debug(f"Could not migrate legacy rules: {e}")

        # Ensure designated super admin account has super_admin role and active subscription
        try:
            if hasattr(db, "users"):
                super_admin_email = "alooshpal@gmail.com"
                sa_user = db.users.find_one({"email": super_admin_email})
                if sa_user:
                    from datetime import timedelta
                    now_utc = datetime.now(timezone.utc)
                    db.users.update_one(
                        {"email": super_admin_email},
                        {"$set": {
                            "role": "super_admin",
                            "plan": "annual",
                            "subscription_status": "active",
                            "subscription_expires_at": now_utc + timedelta(days=3650),
                            "max_target_channels": 999,
                            "updated_at": now_utc
                        }}
                    )
                    logger.info(f"Promoted {super_admin_email} to super_admin")
        except Exception as e:
            logger.debug(f"Could not promote designated super admin: {e}")

        _db_cache = db
        _db_initialized = True
        logger.info(f"Database initialized: {type(db).__name__}")

        # Start subscription auto-expiration background worker
        try:
            from src.billing.expiration import expiration_worker
            expiration_worker.start(get_db)
        except Exception as e:
            logger.debug(f"Could not start expiration worker: {e}")

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
    """Get all forwarding rules strictly for the authenticated user."""
    db = get_db()
    if not db:
        return jsonify({"rules": [], "warning": "Database not connected"}), 200

    from src.web.auth import get_current_user_from_request
    user = get_current_user_from_request(db)
    if not user:
        # Not logged in: return empty rules list
        return jsonify({"rules": [], "authenticated": False})

    user_id = str(user["_id"])
    try:
        rules = list(db.rules.find({"user_id": user_id}))
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
        if not user:
            return jsonify({"error": "Authentication required"}), 401
        user_id = str(user["_id"])

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

        # Check subscription status and target channel limits
        from src.billing.plans import check_subscription_status
        status, is_active, _, _ = check_subscription_status(user)
        if not is_active:
            return jsonify({"error": "Your subscription has expired. Please renew your plan to create or modify rules."}), 403

        max_targets = user.get("max_target_channels", 999) if user.get("role") != "super_admin" else 999
        if status == "trial" and len(target_ids) > max_targets:
            return jsonify({
                "error": f"Plan Limit: Free Trial allows a maximum of {max_targets} target channels per rule. Please upgrade your subscription for unlimited channels."
            }), 400

        rule = {
            "user_id": user_id,
            "name": data.get("name", "Unnamed Rule"),
            "type": data.get("type", "replace"),
            "source_id": data.get("source_id"),
            "target_id": target_id,
            "target_ids": target_ids,
            "media_types": media_types,
            "forward_mode": data.get("forward_mode", "AUTO_FALLBACK"),
            "forward_delay": float(data.get("forward_delay", 0) or 0),
            "whitelist_keywords": data.get("whitelist_keywords", []),
            "blacklist_keywords": data.get("blacklist_keywords", []),
            "strip_mentions": bool(data.get("strip_mentions", False)),
            "strip_links": bool(data.get("strip_links", False)),
            "header_template": data.get("header_template", ""),
            "footer_template": data.get("footer_template", ""),
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

    from src.web.auth import get_current_user_from_request
    user = get_current_user_from_request(db)
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    user_id = str(user["_id"])
    object_id = _to_db_id(rule_id)

    rule = db.rules.find_one({"_id": object_id})
    if not rule:
        return jsonify({"error": "Rule not found"}), 404
    if rule.get("user_id") and rule.get("user_id") != user_id and user.get("role") != "admin":
        return jsonify({"error": "Forbidden: You do not own this rule"}), 403

    db.rules.delete_one({"_id": object_id})
    _log_event(db, "INFO", f"Rule '{rule_id}' deleted")
    return jsonify({"success": True})


@app.route("/api/rules/<rule_id>", methods=["PUT"])
def api_update_rule(rule_id):
    """Update a forwarding rule."""
    db = get_db()
    if not db:
        return jsonify({"error": "Database not connected"}), 500

    from src.web.auth import get_current_user_from_request
    user = get_current_user_from_request(db)
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    user_id = str(user["_id"])
    data = request.get_json() or {}
    object_id = _to_db_id(rule_id)

    rule = db.rules.find_one({"_id": object_id})
    if not rule:
        return jsonify({"error": "Rule not found"}), 404
    if rule.get("user_id") and rule.get("user_id") != user_id and user.get("role") != "admin":
        return jsonify({"error": "Forbidden: You do not own this rule"}), 403

    update_data = {}
    for key in [
        "name", "type", "pattern", "replacement", "priority", "active",
        "source_id", "target_id", "target_ids", "media_types",
        "forward_mode", "forward_delay", "whitelist_keywords", "blacklist_keywords",
        "strip_mentions", "strip_links", "header_template", "footer_template"
    ]:
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
    """Fetch all Telegram channels joined by the active authenticated user."""
    db = get_db()
    from src.web.auth import get_current_user_from_request, UserManager
    user = get_current_user_from_request(db) if db else None
    if not user:
        return jsonify({"channels": [], "dialogs": [], "connected": False, "error": "Please log in first."}), 200

    session_string = UserManager.get_user_telegram_session(db, str(user["_id"]))
    if not session_string:
        return jsonify({"channels": [], "dialogs": [], "connected": False, "error": "No Telegram account connected for your user."}), 200

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
    """Get aggregated statistics for the dashboard isolated by user."""
    db = get_db()
    from src.web.auth import get_current_user_from_request
    from src.forwarder.worker_pool import worker_pool

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
    is_running = worker_pool.is_user_running(user_id) if tg_connected else False

    from src.web.auth import UserManager
    sub_info = UserManager.get_subscription_info(db, user_id)

    stats = {
        "running": is_running,
        "connected": tg_connected,
        "telegram_connected": tg_connected,
        "telegram_username": tg_username,
        "subscription": sub_info,
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
            rules = list(db.rules.find({"user_id": user_id}))
            stats["total_rules"] = len(rules)
            stats["active_rules"] = sum(1 for r in rules if r.get("active", True))
            stats["total_forwarded"] = len(list(db.processed_posts.find({"user_id": user_id}))) if hasattr(db, "processed_posts") else 0
            if stats["total_forwarded"] == 0 and hasattr(db, "processed_posts"):
                stats["total_forwarded"] = db.processed_posts.count_documents({})
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

    from src.web.auth import get_current_user_from_request
    user = get_current_user_from_request(db)
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    user_id = str(user["_id"])
    object_id = _to_db_id(rule_id)
    rule = db.rules.find_one({"_id": object_id})
    if not rule:
        return jsonify({"error": "Rule not found"}), 404
    if rule.get("user_id") and rule.get("user_id") != user_id and user.get("role") != "admin":
        return jsonify({"error": "Forbidden: You do not own this rule"}), 403

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
    if not user:
        return jsonify({"success": False, "error": "Please log in first"}), 401
    user_id = str(user["_id"])

    # Check subscription validity
    if not UserManager.is_subscription_valid(db, user_id):
        return jsonify({
            "success": False,
            "error": "Your subscription or trial period has expired. Please upgrade or renew your plan to start forwarding."
        }), 403

    session_string = UserManager.get_user_telegram_session(db, user_id)
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
    is_super = (user.get("role") == "super_admin" or user.get("email") == "alooshpal@gmail.com")
    return jsonify({
        "authenticated": True,
        "user": {
            "id": str(user["_id"]),
            "email": user.get("email", ""),
            "name": user.get("name", ""),
            "plan": "annual" if is_super else user.get("plan", "trial"),
            "role": "super_admin" if is_super else user.get("role", "client"),
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


# ==========================================
# --- Automated Billing & Webhook Routes ---
# ==========================================

@app.route("/api/v1/plans", methods=["GET"])
def api_get_plans():
    """Retrieve all available subscription plans."""
    from src.billing.plans import PLANS
    return jsonify({
        "success": True,
        "plans": list(PLANS.values())
    })


@app.route("/api/v1/user/subscription", methods=["GET"])
def api_get_user_subscription():
    """Get authenticated user's current subscription details."""
    db = get_db()
    if not db:
        return jsonify({"success": False, "error": "Database not connected"}), 500

    from src.web.auth import get_current_user_from_request, UserManager
    user = get_current_user_from_request(db)
    if not user:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    info = UserManager.get_subscription_info(db, str(user["_id"]))
    return jsonify({"success": True, "subscription": info, "user": {
        "id": str(user["_id"]),
        "email": user.get("email"),
        "name": user.get("name"),
        "role": user.get("role", "client")
    }})


@app.route("/api/v1/payments/create-checkout", methods=["POST"])
def api_create_checkout():
    """Initiate checkout for a chosen subscription plan."""
    db = get_db()
    if not db:
        return jsonify({"success": False, "error": "Database not connected"}), 500

    from src.web.auth import get_current_user_from_request
    user = get_current_user_from_request(db)
    if not user:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    data = request.get_json() or {}
    plan_id = data.get("plan_id", "monthly")
    provider = data.get("provider", "nowpayments")
    base_url = request.host_url

    from src.billing.webhook import WebhookEngine
    success, result = WebhookEngine.create_checkout_order(db, str(user["_id"]), plan_id, provider, base_url=base_url)
    if not success:
        return jsonify({"success": False, "error": result.get("error")}), 400

    return jsonify({"success": True, "checkout": result})


@app.route("/api/v1/payments/check-status/<order_id>", methods=["GET"])
def api_check_order_status(order_id):
    """Check payment status of an order for realtime frontend polling."""
    db = get_db()
    if not db:
        return jsonify({"success": False, "error": "Database not connected"}), 500

    from src.web.auth import get_current_user_from_request, UserManager
    user = get_current_user_from_request(db)
    if not user:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    from src.billing.webhook import WebhookEngine
    tx = WebhookEngine.get_order_status(db, order_id)
    if not tx:
        return jsonify({"success": False, "error": "Order not found"}), 404

    # Security check: User must own the order or be admin
    if tx.get("user_id") != str(user["_id"]) and user.get("role") != "super_admin":
        return jsonify({"success": False, "error": "Forbidden"}), 403

    sub_info = UserManager.get_subscription_info(db, str(user["_id"]))
    return jsonify({
        "success": True,
        "order_id": order_id,
        "status": tx.get("status", "pending"),
        "is_completed": tx.get("status") == "completed",
        "plan_id": tx.get("plan_id"),
        "amount": tx.get("amount"),
        "invoice_url": tx.get("invoice_url"),
        "subscription": sub_info
    })


@app.route("/api/v1/payments/nowpayments-webhook", methods=["POST"])
@app.route("/api/v1/payments/webhook", methods=["POST"])
def api_payments_webhook():
    """
    Zero-touch automated cryptocurrency payment activation Webhook (NOWPayments IPN).
    Verifies cryptographic HMAC signature, updates transactions ledger,
    and instantly activates customer subscription without human intervention.
    """
    db = get_db()
    if not db:
        return jsonify({"status": "error", "message": "Database unavailable"}), 500

    raw_body = request.get_data()
    payload = request.get_json(silent=True) or {}
    signature = (
        request.headers.get("x-nowpayments-sig")
        or request.headers.get("X-NOWPayments-Sig")
        or request.headers.get("X-Signature")
        or request.headers.get("Sign")
        or request.headers.get("Signature")
        or request.args.get("signature")
    )

    from src.billing.webhook import WebhookEngine
    success, res = WebhookEngine.process_webhook_payment(db, payload, raw_body, signature)

    if not success:
        return jsonify(res), 400

    return jsonify(res), 200


@app.route("/api/v1/payments/simulate-success", methods=["POST"])
def api_simulate_payment():
    """Test/Demo simulation endpoint to instantly confirm a pending checkout order."""
    db = get_db()
    if not db:
        return jsonify({"success": False, "error": "Database not connected"}), 500

    from src.web.auth import get_current_user_from_request
    user = get_current_user_from_request(db)
    if not user:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    data = request.get_json() or {}
    order_id = data.get("order_id")
    if not order_id:
        return jsonify({"success": False, "error": "Missing order_id"}), 400

    payload = {
        "order_id": order_id,
        "status": "COMPLETED",
        "transaction_id": f"SIM-TX-{uuid.uuid4().hex[:12].upper()}"
    }

    from src.billing.webhook import WebhookEngine
    success, res = WebhookEngine.process_webhook_payment(db, payload)
    if not success:
        return jsonify({"success": False, "error": res.get("error")}), 400

    return jsonify({"success": True, "result": res})


@app.route("/api/v1/user/redeem-code", methods=["POST"])
def api_user_redeem_code():
    """Client endpoint: Redeem an admin license key / activation code."""
    db = get_db()
    if not db:
        return jsonify({"success": False, "error": "Database not connected"}), 500

    from src.web.auth import get_current_user_from_request
    user = get_current_user_from_request(db)
    if not user:
        return jsonify({"success": False, "error": "Unauthorized. Please log in first."}), 401

    data = request.get_json() or {}
    code = data.get("code", "").strip()
    if not code:
        return jsonify({"success": False, "error": "يرجى إدخال كود التفعيل (Code is required)"}), 400

    from src.billing.keys import LicenseKeyManager
    success, message, sub_info = LicenseKeyManager.redeem_key(db, str(user["_id"]), code)
    if not success:
        return jsonify({"success": False, "error": message}), 400

    _log_event(db, "INFO", f"User {user.get('email')} redeemed license key: {code}")
    return jsonify({
        "success": True,
        "message": message,
        "subscription": sub_info
    })


@app.route("/api/v1/admin/users", methods=["GET"])
def api_admin_list_users():
    """Admin endpoint: List all registered users with subscription and freeze details."""
    db = get_db()
    if not db:
        return jsonify({"success": False, "error": "Database not connected"}), 500

    from src.web.auth import get_current_user_from_request, UserManager
    current_user = get_current_user_from_request(db)
    is_admin = (current_user and (current_user.get("role") in ("admin", "super_admin") or current_user.get("email") == "alooshpal@gmail.com"))
    if not is_admin:
        return jsonify({"success": False, "error": "Forbidden: Admin access required"}), 403

    users_list = []
    try:
        for u in db.users.find({}):
            uid_str = str(u["_id"])
            sub = UserManager.get_subscription_info(db, uid_str)
            rules_count = db.rules.count_documents({"user_id": uid_str}) if hasattr(db, "rules") else 0
            created_at_val = u.get("created_at")
            users_list.append({
                "_id": uid_str,
                "email": u.get("email"),
                "name": u.get("name"),
                "role": u.get("role", "client"),
                "plan": u.get("plan", "trial"),
                "subscription_status": sub.get("status"),
                "is_frozen": u.get("is_frozen") in (True, 1, "1", "true", "True"),
                "frozen_reason": u.get("frozen_reason", ""),
                "subscription_expires_at": sub.get("expires_at"),
                "days_remaining": sub.get("days_remaining"),
                "max_target_channels": sub.get("max_target_channels", 2),
                "rules_count": rules_count,
                "telegram_connected": bool(u.get("telegram_account") and u.get("telegram_account", {}).get("session_string")),
                "telegram_username": (u.get("telegram_account") or {}).get("username"),
                "created_at": created_at_val.isoformat() if hasattr(created_at_val, "isoformat") else str(created_at_val),
            })
    except Exception as e:
        logger.error(f"Failed to fetch admin users: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

    return jsonify({"success": True, "users": users_list})


@app.route("/api/v1/admin/users/<user_id>/freeze", methods=["POST"])
def api_admin_freeze_user(user_id):
    """Admin endpoint: Freeze or unfreeze a user account."""
    db = get_db()
    if not db:
        return jsonify({"success": False, "error": "Database not connected"}), 500

    from src.web.auth import get_current_user_from_request, UserManager
    current_user = get_current_user_from_request(db)
    is_admin = (current_user and (current_user.get("role") in ("admin", "super_admin") or current_user.get("email") == "alooshpal@gmail.com"))
    if not is_admin:
        return jsonify({"success": False, "error": "Forbidden: Admin access required"}), 403

    target_user = db.users.find_one({"_id": user_id})
    if not target_user:
        return jsonify({"success": False, "error": "User not found"}), 404

    if target_user.get("email") == "alooshpal@gmail.com" or target_user.get("role") == "super_admin":
        return jsonify({"success": False, "error": "لا يمكن تجميد حساب السوبر أدمن (Cannot freeze Super Admin)"}), 400

    data = request.get_json() or {}
    freeze = bool(data.get("freeze", True))
    reason = data.get("reason", "Suspended by Administrator")

    UserManager.freeze_user(db, user_id, freeze, reason)
    status_str = "مجمد (Frozen)" if freeze else "مفعل (Unfrozen)"
    _log_event(db, "WARNING" if freeze else "INFO", f"Admin {current_user.get('email')} set user {target_user.get('email')} to {status_str}. Reason: {reason}")

    return jsonify({
        "success": True,
        "message": f"تم {'تجميد' if freeze else 'فك تجميد'} الحساب بنجاح",
        "is_frozen": freeze
    })


@app.route("/api/v1/admin/users/<user_id>/role", methods=["POST"])
def api_admin_change_user_role(user_id):
    """Super Admin endpoint: Promote or demote user role."""
    db = get_db()
    if not db:
        return jsonify({"success": False, "error": "Database not connected"}), 500

    from src.web.auth import get_current_user_from_request
    current_user = get_current_user_from_request(db)
    is_super = (current_user and (current_user.get("role") == "super_admin" or current_user.get("email") == "alooshpal@gmail.com"))
    if not is_super:
        return jsonify({"success": False, "error": "Forbidden: Super Admin access required to change roles"}), 403

    target_user = db.users.find_one({"_id": user_id})
    if not target_user:
        return jsonify({"success": False, "error": "User not found"}), 404

    data = request.get_json() or {}
    new_role = data.get("role", "client").lower().strip()
    if new_role not in ("client", "admin", "super_admin"):
        return jsonify({"success": False, "error": "Invalid role. Options: client, admin, super_admin"}), 400

    db.users.update_one(
        {"_id": user_id},
        {"$set": {"role": new_role, "updated_at": datetime.now(timezone.utc)}}
    )
    _log_event(db, "INFO", f"Super Admin {current_user.get('email')} changed role for user {target_user.get('email')} to {new_role}")

    return jsonify({"success": True, "message": f"تم تعديل رتبة المستخدم إلى {new_role} بنجاح", "role": new_role})


@app.route("/api/v1/admin/keys", methods=["GET"])
def api_admin_list_keys():
    """Admin endpoint: List all generated license keys."""
    db = get_db()
    if not db:
        return jsonify({"success": False, "error": "Database not connected"}), 500

    from src.web.auth import get_current_user_from_request
    current_user = get_current_user_from_request(db)
    is_admin = (current_user and (current_user.get("role") in ("admin", "super_admin") or current_user.get("email") == "alooshpal@gmail.com"))
    if not is_admin:
        return jsonify({"success": False, "error": "Forbidden: Admin access required"}), 403

    from src.billing.keys import LicenseKeyManager
    keys_list = LicenseKeyManager.list_keys(db)
    return jsonify({"success": True, "keys": keys_list})


@app.route("/api/v1/admin/keys/generate", methods=["POST"])
def api_admin_generate_key():
    """Admin endpoint: Generate a new license key with selected plan."""
    db = get_db()
    if not db:
        return jsonify({"success": False, "error": "Database not connected"}), 500

    from src.web.auth import get_current_user_from_request
    current_user = get_current_user_from_request(db)
    is_admin = (current_user and (current_user.get("role") in ("admin", "super_admin") or current_user.get("email") == "alooshpal@gmail.com"))
    if not is_admin:
        return jsonify({"success": False, "error": "Forbidden: Admin access required"}), 403

    data = request.get_json() or {}
    plan_id = data.get("plan_id", "monthly")
    notes = data.get("notes", "")
    custom_days = data.get("custom_days")

    from src.billing.keys import LicenseKeyManager
    try:
        key_doc = LicenseKeyManager.generate_key(db, plan_id, current_user.get("email", "Admin"), notes, custom_days)
        _log_event(db, "INFO", f"Admin {current_user.get('email')} generated license key {key_doc['key_code']} ({plan_id})")
        return jsonify({"success": True, "message": "تم توليد كود التفعيل بنجاح", "key": {
            "key_code": key_doc["key_code"],
            "plan_id": key_doc["plan_id"],
            "plan_name": key_doc["plan_name"],
            "duration_days": key_doc["duration_days"],
            "notes": key_doc["notes"]
        }})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route("/api/v1/admin/keys/<key_id>", methods=["DELETE"])
def api_admin_delete_key(key_id):
    """Admin endpoint: Delete an activation key."""
    db = get_db()
    if not db:
        return jsonify({"success": False, "error": "Database not connected"}), 500

    from src.web.auth import get_current_user_from_request
    current_user = get_current_user_from_request(db)
    is_admin = (current_user and (current_user.get("role") in ("admin", "super_admin") or current_user.get("email") == "alooshpal@gmail.com"))
    if not is_admin:
        return jsonify({"success": False, "error": "Forbidden: Admin access required"}), 403

    from src.billing.keys import LicenseKeyManager
    LicenseKeyManager.delete_key(db, key_id)
    return jsonify({"success": True, "message": "تم حذف الكود بنجاح"})


@app.route("/api/v1/admin/users/<user_id>/subscription", methods=["POST"])
def api_admin_update_subscription(user_id):
    """Admin endpoint: Manually extend or set subscription for a user."""
    db = get_db()
    if not db:
        return jsonify({"success": False, "error": "Database not connected"}), 500

    from src.web.auth import get_current_user_from_request, UserManager
    current_user = get_current_user_from_request(db)
    is_admin = (current_user and (current_user.get("role") in ("admin", "super_admin") or current_user.get("email") == "alooshpal@gmail.com"))
    if not is_admin:
        return jsonify({"success": False, "error": "Forbidden: Admin access required"}), 403

    target_user = db.users.find_one({"_id": user_id})
    if not target_user:
        return jsonify({"success": False, "error": "User not found"}), 404

    data = request.get_json() or {}
    plan_id = data.get("plan_id", "monthly")
    add_days = int(data.get("days", 30))
    new_role = data.get("role")

    from src.billing.plans import calculate_new_expiration, get_plan
    plan = get_plan(plan_id) or {"id": plan_id, "name": plan_id.capitalize(), "max_target_channels": 999}
    curr_expires = target_user.get("subscription_expires_at")
    if isinstance(curr_expires, str):
        try:
            curr_expires = datetime.fromisoformat(curr_expires.replace("Z", "+00:00"))
        except Exception:
            curr_expires = None

    new_expires = calculate_new_expiration(curr_expires, add_days)

    update_fields = {
        "subscription_status": "active",
        "plan": plan_id,
        "subscription_expires_at": new_expires,
        "max_target_channels": plan.get("max_target_channels", 999),
        "is_frozen": False,
        "frozen_reason": "",
        "updated_at": datetime.now(timezone.utc)
    }

    # Only super_admin can change role to super_admin or admin
    if new_role and (current_user.get("role") == "super_admin" or current_user.get("email") == "alooshpal@gmail.com"):
        update_fields["role"] = new_role

    db.users.update_one({"_id": user_id}, {"$set": update_fields})
    _log_event(db, "INFO", f"Admin {current_user.get('email')} updated subscription for user {target_user.get('email')} (+{add_days} days)")

    return jsonify({"success": True, "message": "Subscription updated successfully", "expires_at": new_expires.isoformat()})


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
