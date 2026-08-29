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
        "SECRET_KEY": os.environ.get("SECRET_KEY", ""),

        # Logging
        "LOG_LEVEL": os.environ.get("LOG_LEVEL", "INFO"),

        # Forwarding behavior
        "CHECK_INTERVAL": int(os.environ.get("CHECK_INTERVAL", "30") or "30"),
        "MAX_RETRIES": int(os.environ.get("MAX_RETRIES", "3") or "3"),
        "RETRY_DELAY": int(os.environ.get("RETRY_DELAY", "10") or "10"),

        # NOWPayments Cryptocurrency Gateway
        "NOWPAYMENTS_API_KEY": os.environ.get("NOWPAYMENTS_API_KEY", ""),
        "NOWPAYMENTS_IPN_SECRET": os.environ.get("NOWPAYMENTS_IPN_SECRET", ""),
        "NOWPAYMENTS_API_URL": os.environ.get("NOWPAYMENTS_API_URL", "https://api.nowpayments.io/v1"),

        # SMTP & Transactional Email Settings (TeleTips Pro)
        "SMTP_HOST": os.environ.get("SMTP_HOST", ""),
        "SMTP_PORT": int(os.environ.get("SMTP_PORT", "587") or "587"),
        "SMTP_USER": os.environ.get("SMTP_USER", "") or os.environ.get("SMTP_EMAIL", ""),
        "SMTP_PASSWORD": os.environ.get("SMTP_PASSWORD", "") or os.environ.get("SMTP_PASS", ""),
        "SMTP_TLS": os.environ.get("SMTP_TLS", "true").lower() in ("true", "1", "yes"),
        "SMTP_SSL": os.environ.get("SMTP_SSL", "false").lower() in ("true", "1", "yes"),
        "SMTP_FROM_EMAIL": os.environ.get("SMTP_FROM_EMAIL", "") or os.environ.get("FROM_EMAIL", ""),
        "SMTP_FROM_NAME": os.environ.get("SMTP_FROM_NAME", "TeleTips Pro"),
        "APP_URL": os.environ.get("APP_URL", ""),

        # Clerk Authentication & User Management
        "CLERK_PUBLISHABLE_KEY": os.environ.get("CLERK_PUBLISHABLE_KEY") or os.environ.get("VITE_CLERK_PUBLISHABLE_KEY") or os.environ.get("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY") or "",
        "CLERK_SECRET_KEY": os.environ.get("CLERK_SECRET_KEY", ""),
        "CLERK_JWT_KEY": os.environ.get("CLERK_JWT_KEY", ""),
        "CLERK_ISSUER": os.environ.get("CLERK_ISSUER", ""),
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


def validate_environment(raise_on_missing: bool = False) -> list:
    """
    Validates environment configuration on application boot-up.
    Identifies missing essential secrets to protect security.
    """
    config = get_config()
    is_prod = os.environ.get("FLASK_ENV") == "production" or os.environ.get("RENDER") == "true" or os.environ.get("ENVIRONMENT") == "production"
    missing = []

    if not config.get("SECRET_KEY") and is_prod:
        missing.append("SECRET_KEY")

    if missing:
        logger.warning(f"⚠️ Security Warning: Missing environment variables: {', '.join(missing)}")
        if raise_on_missing:
            raise RuntimeError(f"Startup aborted: Missing essential environment variables: {', '.join(missing)}")

    return missing
