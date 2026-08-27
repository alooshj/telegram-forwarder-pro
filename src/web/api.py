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

        # Try starting the forwarder engine if credentials are available
        if config.get("SESSION_STRING") and config.get("API_ID"):
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
    """Get all forwarding rules."""
    db = get_db()
    if not db:
        return jsonify({"rules": [], "warning": "Database not connected"}), 200
    try:
        rules = list(db.rules.find({}))
        for rule in rules:
            rule["_id"] = str(rule["_id"])
        return jsonify({"rules": rules})
    except Exception as e:
        logger.error(f"Failed to fetch rules: {e}")
        return jsonify({"rules": [], "error": str(e)}), 200


@app.route("/api/rules", methods=["POST"])
def api_create_rule():
    """Create a new forwarding rule."""
    db = get_db()
    if not db:
        return jsonify({"error": "Database not connected"}), 500
    try:
        data = request.get_json()
        rule = {
            "name": data.get("name", "Unnamed Rule"),
            "type": data.get("type", "replace"),
            "source_id": data.get("source_id"),
            "target_id": data.get("target_id"),
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

    data = request.get_json()
    object_id = _to_db_id(rule_id)

    update_data = {}
    for key in ["name", "type", "pattern", "replacement", "priority", "active", "source_id", "target_id"]:
        if key in data:
            update_data[key] = data[key]

    db.rules.update_one({"_id": object_id}, {"$set": update_data})
    _log_event(db, "INFO", f"Rule '{rule_id}' updated")
    return jsonify({"success": True})


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
    stats = {
        "running": forwarder_status.get("running", False),
        "connected": forwarder_status.get("connected", False),
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
            rules = list(db.rules.find({}))
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
    """Start the forwarder engine."""
    from src.utils.config import load_config as lc
    config = lc()
    db = get_db()
    if not db:
        return jsonify({"error": "Database not connected"}), 500

    if forwarder_status["running"] and _engine_instance and getattr(_engine_instance, "_running", False):
        return jsonify({"success": True, "message": "Forwarder already running"})

    started = _start_forwarder_engine(config, db)
    if started:
        return jsonify({"success": True, "message": "Forwarder started"})
    return jsonify({"error": "Could not start forwarder"}), 500


@app.route("/api/forward/stop", methods=["POST"])
def api_stop_forwarder():
    """Stop the forwarder engine."""
    _stop_forwarder_engine()
    return jsonify({"success": True, "message": "Forwarder stopped"})


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors with JSON response."""
    return jsonify({"error": "Not found"}), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors with JSON response."""
    return jsonify({"error": "Internal server error"}), 500


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
