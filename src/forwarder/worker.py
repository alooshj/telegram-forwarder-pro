"""
Forwarder Worker
----------------
Standalone entry point for running a single user's forwarder with
MongoDB-backed channel cooldown tracking.

Usage:
    python -m src.forwarder.worker <user_id> [--once]

Or import and use directly:
    from src.forwarder.worker import run_worker
    await run_worker(db, user_id, session_string, config)
"""

import asyncio
import logging
import sys
import time

logger = logging.getLogger(__name__)


async def run_worker(db, user_id: str, session_string: str, config: dict, run_once: bool = False):
    """
    Run the forwarder engine for a single user with cooldown-aware processing.

    Args:
        db: Database instance (MongoDB or SQLite)
        user_id: User ID
        session_string: Encrypted Telegram session string
        config: Forwarder config dict (must include API_ID, API_HASH)
        run_once: If True, process one cycle then return
    """
    from src.forwarder.engine import ForwarderEngine
    from src.utils.encryption import decrypt_session

    decrypted = decrypt_session(session_string)
    cfg = dict(config)
    cfg["SESSION_STRING"] = decrypted
    cfg["USER_ID"] = user_id

    engine = ForwarderEngine(cfg, db, user_id=user_id)
    engine._running = True

    logger.info(f"Worker starting for user {user_id}")

    try:
        await engine.start()

        if run_once:
            await engine._run_forwarding_loop_once()
        else:
            await engine._run_forwarding_loop()
    except Exception as e:
        logger.error(f"Worker for user {user_id} crashed: {e}", exc_info=True)
    finally:
        engine._running = False
        logger.info(f"Worker stopped for user {user_id}")


async def process_cooldown_channels(db, user_id: str):
    """
    Utility: list all channels currently in cooldown for a user.
    Returns a list of dicts with channel_id, cooldown_until, cooldown_seconds.
    """
    if not db:
        return []

    results = []
    try:
        from datetime import datetime, timezone
        cursor = db.channel_cooldowns.find({"user_id": str(user_id)})
        for doc in cursor:
            cooldown_until = doc.get("cooldown_until")
            if cooldown_until and hasattr(cooldown_until, "tzinfo") and cooldown_until.tzinfo is None:
                cooldown_until = cooldown_until.replace(tzinfo=timezone.utc)
            if cooldown_until and datetime.now(timezone.utc) < cooldown_until:
                results.append({
                    "channel_id": doc.get("channel_id"),
                    "cooldown_until": cooldown_until,
                    "cooldown_seconds": doc.get("cooldown_seconds", 0),
                })
    except Exception as e:
        logger.debug(f"Error listing cooldowns for user {user_id}: {e}")

    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    print("Use: from src.forwarder.worker import run_worker")
    print("Or:  python -m src.forwarder.worker <user_id>")
