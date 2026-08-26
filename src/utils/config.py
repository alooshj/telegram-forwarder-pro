"""
Configuration Module
--------------------
Central configuration management for Telegram Forwarder Pro.
Loads from environment variables (or .env file) with sensible defaults.

Supports both MONGO_URI and MONGODB_URI environment variable names
for compatibility with different deployment platforms.
"""

import os
import logging
from dotenv import load_dotenv

# Load .env file from config directory
_config_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")
_env_path = os.path.join(_config_dir, ".env")
load_dotenv(_env_path)

logger = logging.getLogger(__name__)


def load_config():
    """Load all configuration from environment variables."""
    # Support both MONGO_URI and MONGODB_URI (MONGODB_URI takes precedence)
    mongo_uri = os.getenv("MONGODB_URI") or os.getenv("MONGO_URI") or ""

    config = {
        # Telegram API credentials (https://my.telegram.org)
        "API_ID": int(os.getenv("API_ID", 0) or 0),
        "API_HASH": os.getenv("API_HASH", ""),
        "SESSION_STRING": os.getenv("SESSION_STRING", ""),

        # MongoDB Atlas connection (MONGODB_URI for Atlas, MONGO_URI as fallback)
        "MONGODB_URI": mongo_uri,
        "MONGO_URI": mongo_uri,  # Backward compatibility
        "MONGO_DB": os.getenv("MONGO_DB", "telegram_forwarder"),
        "MONGODB_DB": os.getenv("MONGO_DB", "telegram_forwarder"),

        # Web dashboard settings
        "WEB_HOST": os.getenv("WEB_HOST", "0.0.0.0"),
        "WEB_PORT": int(os.getenv("WEB_PORT", 5000) or 5000),
        "SECRET_KEY": os.getenv("SECRET_KEY", "dev-secret-key-change-me"),

        # Logging
        "LOG_LEVEL": os.getenv("LOG_LEVEL", "INFO"),

        # Forwarding behavior
        "CHECK_INTERVAL": int(os.getenv("CHECK_INTERVAL", 30) or 30),
        "MAX_RETRIES": int(os.getenv("MAX_RETRIES", 3) or 3),
        "RETRY_DELAY": int(os.getenv("RETRY_DELAY", 10) or 10),
    }

    return config


# Singleton config instance
_config = None


def get_config():
    """Get the cached config instance (creates on first call)."""
    global _config
    if _config is None:
        _config = load_config()
    return _config
