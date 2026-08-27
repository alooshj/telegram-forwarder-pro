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
from datetime import datetime
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
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
            import threading
            import asyncio
            from src.forwarder.engine import ForwarderEngine

            def run_forwarder():
                try:
                    engine = ForwarderEngine(config, db)
                    asyncio.run(engine.start())
                except Exception as e:
                    logger.error(f"Forwarder engine failed: {e}", exc_info=True)

            thread = threading.Thread(target=run_forwarder, daemon=True)
            thread.start()
            logger.info("Forwarder engine started in background thread")

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
    config_info = {
        "db_connected": db is not None,
        "db_type": db_type,
        "deploy_commit": _commit,
        "mongo_error": db_error,
        "mongo_uri_set": bool(os.environ.get("MONGODB_URI") or os.environ.get("MONGO_URI")),
        "mongo_force_fallback": os.environ.get("MONGODB_FORCE_FALLBACK", "false"),
        "mongo_raw_preview": (mongo_raw[:60] + "...") if len(mongo_raw) > 60 else mongo_raw,
        "mongo_clean_preview": (mongo_clean[:60] + "...") if len(mongo_clean) > 60 else mongo_clean,
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
    try:
        from bson import ObjectId
        object_id = ObjectId(rule_id)
    except ImportError:
        object_id = rule_id  # Fallback to string ID for SQLite

    db.rules.delete_one({"_id": object_id})
    return jsonify({"success": True})


@app.route("/api/rules/<rule_id>", methods=["PUT"])
def api_update_rule(rule_id):
    """Update a forwarding rule."""
    db = get_db()
    if not db:
        return jsonify({"error": "Database not connected"}), 500

    data = request.get_json()
    try:
        from bson import ObjectId
        object_id = ObjectId(rule_id)
    except ImportError:
        object_id = rule_id

    update_data = {}
    for key in ["name", "type", "pattern", "replacement", "priority", "active", "source_id", "target_id"]:
        if key in data:
            update_data[key] = data[key]

    db.rules.update_one({"_id": object_id}, {"$set": update_data})
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
    entry = {
        "channel_id": data.get("channel_id"),
        "reason": data.get("reason", "Blacklisted"),
        "added_at": datetime.utcnow(),
    }
    result = db.blacklist.insert_one(entry)
    entry["_id"] = str(result.inserted_id)
    return jsonify({"success": True, "entry": entry})


@app.route("/api/blacklist/<channel_id>", methods=["DELETE"])
def api_remove_blacklist(channel_id):
    """Remove a channel from the blacklist."""
    db = get_db()
    if not db:
        return jsonify({"error": "Database not connected"}), 500

    db.blacklist.delete_one({"channel_id": int(channel_id)})
    return jsonify({"success": True})


@app.route("/api/logs")
def api_get_logs():
    """Get recent logs."""
    db = get_db()
    if not db:
        return jsonify({"logs": [], "warning": "Database not connected"}), 200
    try:
        logs = db.logs.find(sort=("timestamp", -1), limit=100)
        for log in logs:
            log["_id"] = str(log["_id"])
            if log.get("timestamp"):
                log["timestamp"] = log["timestamp"].isoformat() if hasattr(log["timestamp"], 'isoformat') else str(log["timestamp"])
        return jsonify({"logs": logs})
    except Exception as e:
        logger.error(f"Failed to fetch logs: {e}")
        return jsonify({"logs": [], "error": "Database query failed"}), 200


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
    from src.forwarder.engine import ForwarderEngine
    from src.utils.config import load_config as lc
    config = lc()
    db = get_db()
    if not db:
        return jsonify({"error": "Database not connected"}), 500

    if forwarder_status["running"]:
        return jsonify({"success": True, "message": "Forwarder already running"})

    import threading
    import asyncio

    def run_forwarder():
        try:
            engine = ForwarderEngine(config, db)
            asyncio.run(engine.start())
            forwarder_status["running"] = True
            forwarder_status["connected"] = True
        except Exception as e:
            logger.error(f"Forwarder start failed: {e}", exc_info=True)
            forwarder_status["running"] = False
            forwarder_status["connected"] = False

    thread = threading.Thread(target=run_forwarder, daemon=True)
    thread.start()
    return jsonify({"success": True, "message": "Forwarder started"})


@app.route("/api/forward/stop", methods=["POST"])
def api_stop_forwarder():
    """Stop the forwarder engine."""
    forwarder_status["running"] = False
    forwarder_status["connected"] = False
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
