"""
Configuration Module
--------------------
Central configuration management for Telegram Forwarder Pro.
Loads from environment variables (or .env file) with sensible defaults.

Supports both MONGO_URI and MONGODB_URI environment variable names
for compatibility with different deployment platforms.

Priority: OS environment variables > .env file > hardcoded defaults.
This ensures MONGODB_URI and other secrets from Render are never overridden.
"""

import os
import logging
from dotenv import load_dotenv

# Load .env file from config directory — but DON'T override existing env vars (critical for Render)
_config_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")
_env_path = os.path.join(_config_dir, ".env")

# On deployment platforms (Render, etc.), env vars are already set in the OS.
# We use override=False so that OS environment variables take precedence over .env file.
load_dotenv(_env_path, override=False)

logger = logging.getLogger(__name__)


def load_config():
    """Load all configuration from environment variables."""
    # Priority: OS env vars > .env > defaults
    # Using os.environ.get ensures we always read from the system first
    mongo_uri = os.environ.get("MONGODB_URI") or os.environ.get("MONGO_URI") or ""

    config = {
        # Telegram API credentials (https://my.telegram.org)
        "API_ID": int(os.environ.get("API_ID", "0") or "0"),
        "API_HASH": os.environ.get("API_HASH", ""),
        "SESSION_STRING": os.environ.get("SESSION_STRING", ""),

        # MongoDB Atlas connection (MONGODB_URI for Atlas, MONGO_URI as fallback)
        "MONGODB_URI": mongo_uri,
        "MONGO_URI": mongo_uri,  # Backward compatibility
        "MONGO_DB": os.environ.get("MONGO_DB", "telegram_forwarder"),
        "MONGODB_DB": os.environ.get("MONGO_DB", "telegram_forwarder"),

        # Web dashboard settings
        "WEB_HOST": os.environ.get("WEB_HOST", "0.0.0.0"),
        "WEB_PORT": int(os.environ.get("WEB_PORT", "5000") or "5000"),
        "SECRET_KEY": os.environ.get("SECRET_KEY", "dev-secret-key-change-me"),

        # Logging
        "LOG_LEVEL": os.environ.get("LOG_LEVEL", "INFO"),

        # Forwarding behavior
        "CHECK_INTERVAL": int(os.environ.get("CHECK_INTERVAL", "30") or "30"),
        "MAX_RETRIES": int(os.environ.get("MAX_RETRIES", "3") or "3"),
        "RETRY_DELAY": int(os.environ.get("RETRY_DELAY", "10") or "10"),
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
