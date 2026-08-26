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
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "config", ".env"))

app = Flask(
    __name__,
    template_folder=os.path.join(os.path.dirname(__file__), "..", "dashboard", "templates"),
    static_folder=os.path.join(os.path.dirname(__file__), "..", "dashboard", "static"),
)
CORS(app)

# Global state
forwarder_status = {"running": False, "connected": False, "last_update": None}


def load_config():
    """Load configuration from environment variables.
    
    Supports both MONGODB_URI and MONGO_URI env vars.
    MONGODB_URI takes precedence (MongoDB Atlas standard naming).
    """
    # Support both MONGODB_URI and MONGO_URI (MONGODB_URI takes precedence)
    mongo_uri = os.getenv("MONGODB_URI") or os.getenv("MONGO_URI") or ""
    
    return {
        "API_ID": int(os.getenv("API_ID", 0)),
        "API_HASH": os.getenv("API_HASH", ""),
        "SESSION_STRING": os.getenv("SESSION_STRING", ""),
        "MONGODB_URI": mongo_uri,
        "MONGO_URI": mongo_uri,  # Backward compatibility
        "MONGO_DB": os.getenv("MONGO_DB", "telegram_forwarder"),
        "WEB_HOST": os.getenv("WEB_HOST", "0.0.0.0"),
        "WEB_PORT": int(os.getenv("WEB_PORT", 5000)),
        "CHECK_INTERVAL": int(os.getenv("CHECK_INTERVAL", 30)),
        "MAX_RETRIES": int(os.getenv("MAX_RETRIES", 3)),
        "RETRY_DELAY": int(os.getenv("RETRY_DELAY", 10)),
    }


# --- Database dependency ---
db_ref = None  # Will be set on app start


def get_db():
    return db_ref


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


@app.route("/api/rules")
def api_get_rules():
    """Get all forwarding rules."""
    db = get_db()
    if not db:
        return jsonify({"error": "Database not connected"}), 500

    rules = list(db.rules.find({}))
    for rule in rules:
        rule["_id"] = str(rule["_id"])
    return jsonify({"rules": rules})


@app.route("/api/rules", methods=["POST"])
def api_create_rule():
    """Create a new forwarding rule."""
    db = get_db()
    if not db:
        return jsonify({"error": "Database not connected"}), 500

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


@app.route("/api/rules/<rule_id>", methods=["DELETE"])
def api_delete_rule(rule_id):
    """Delete a forwarding rule."""
    db = get_db()
    if not db:
        return jsonify({"error": "Database not connected"}), 500

    from bson import ObjectId
    db.rules.delete_one({"_id": ObjectId(rule_id)})
    return jsonify({"success": True})


@app.route("/api/rules/<rule_id>", methods=["PUT"])
def api_update_rule(rule_id):
    """Update a forwarding rule."""
    db = get_db()
    if not db:
        return jsonify({"error": "Database not connected"}), 500

    data = request.get_json()
    from bson import ObjectId

    update_data = {}
    for key in ["name", "type", "pattern", "replacement", "priority", "active", "source_id", "target_id"]:
        if key in data:
            update_data[key] = data[key]

    db.rules.update_one({"_id": ObjectId(rule_id)}, {"$set": update_data})
    return jsonify({"success": True})


@app.route("/api/blacklist")
def api_get_blacklist():
    """Get all blacklisted channels."""
    db = get_db()
    if not db:
        return jsonify({"error": "Database not connected"}), 500

    entries = list(db.blacklist.find({}))
    for entry in entries:
        entry["_id"] = str(entry["_id"])
    return jsonify({"blacklist": entries})


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
        "added_at": __import__("datetime").datetime.utcnow(),
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
        return jsonify({"error": "Database not connected"}), 500

    logs = list(db.logs.find().sort("timestamp", -1).limit(100))
    for log in logs:
        log["_id"] = str(log["_id"])
        log["timestamp"] = log["timestamp"].isoformat()
    return jsonify({"logs": logs})


@app.route("/api/forward/start", methods=["POST"])
def api_start_forwarder():
    """Start the forwarder."""
    forwarder_status["running"] = True
    forwarder_status["connected"] = True
    forwarder_status["last_update"] = __import__("datetime").datetime.utcnow().isoformat()
    return jsonify({"success": True, "status": forwarder_status})


@app.route("/api/forward/stop", methods=["POST"])
def api_stop_forwarder():
    """Stop the forwarder."""
    forwarder_status["running"] = False
    forwarder_status["connected"] = False
    forwarder_status["last_update"] = __import__("datetime").datetime.utcnow().isoformat()
    return jsonify({"success": True, "status": forwarder_status})


@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Not found"}), 404


if __name__ == "__main__":
    config = load_config()
    app.run(
        host=config["WEB_HOST"],
        port=config["WEB_PORT"],
        debug=True,
    )
