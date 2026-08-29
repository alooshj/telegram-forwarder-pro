"""
Shared test fixtures and environment setup.
Ensures env vars are set BEFORE importing application modules so that
load_dotenv() in src/web/api.py does not clobber them.
"""
import os

# Set test environment variables before any app imports
os.environ.setdefault("API_ID", "123456")
os.environ.setdefault("API_HASH", "testhash")
os.environ.setdefault("SESSION_STRING", "test")
os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017/test")
os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017/test")  # backward compat
os.environ.setdefault("MONGO_DB", "telegram_forwarder_test")
os.environ.setdefault("WEB_HOST", "127.0.0.1")
os.environ.setdefault("WEB_PORT", "5000")
os.environ.setdefault("CLERK_PUBLISHABLE_KEY", "pk_test_b3JpZW50ZWQtbXVsbGV0LTU2ODEuY2xlcmsuYWNjb3VudHMuZGV2JA")
os.environ.setdefault("CLERK_SECRET_KEY", "sk_test_secret_key_12345")
os.environ.setdefault("PAYMENT_WEBHOOK_SECRET", "test_webhook_secret_key")
os.environ.setdefault("SECRET_KEY", "test_secret_key_32_bytes_long_123")
os.environ.setdefault("TESTING", "true")

# Ensure project root is importable
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
