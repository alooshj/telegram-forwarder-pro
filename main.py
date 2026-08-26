"""
Telegram Forwarder Pro - Main Entry Point
------------------------------------------
Orchestrates the Telegram forwarder engine and web dashboard.
"""

import os
import sys
import logging
import datetime
from dotenv import load_dotenv

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.utils.database import MongoDB
from src.utils.config import load_config
from src.forwarder.engine import ForwarderEngine
from src.web.api import app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(__file__), "logs", "forwarder.log")),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("telegram-forwarder-pro")


def init_database(config):
    """Initialize MongoDB connection and create default data."""
    try:
        db = MongoDB(config["MONGODB_URI"], config["MONGO_DB"])
        # Create default rules if none exist
        if db.rules.count_documents({}) == 0:
            db.rules.insert_many([
                {"name": "Strip @usernames", "type": "regex", "pattern": r"@\w+", "replacement": "[username]", "priority": 1, "active": True},
                {"name": "Branding Footer", "type": "footer", "replacement": "Forwarded by Telegram Forwarder Pro", "priority": 99, "active": True},
            ])
            logger.info("Created default transformation rules")

        # Create indexes
        db.rules.create_index("source_id")
        db.rules.create_index("target_id")
        db.processed_posts.create_index("forwarded_at", expireAfterSeconds=86400 * 30)  # 30 days TTL
        logger.info("Database indexes created")
        return db
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        return None


def main():
    """Main entry point: starts the web dashboard and forwarder engine."""
    config = load_config()
    logger.info(f"Configuration loaded: API_ID={config['API_ID']}")

    # Initialize database
    db = init_database(config)
    if db:
        app.db = db  # Attach to Flask app

    # Log startup
    logger.info("Telegram Forwarder Pro starting...")
    logger.info(f"Web dashboard: http://{config['WEB_HOST']}:{config['WEB_PORT']}")

    # Start the Flask web server
    app.run(
        host=config["WEB_HOST"],
        port=config["WEB_PORT"],
        debug=False,
        use_reloader=False,
    )


if __name__ == "__main__":
    main()
