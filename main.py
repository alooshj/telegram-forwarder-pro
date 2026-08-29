"""
TeleTips Pro - Main Entry Point
|------------------------------------------
Orchestrates the TeleTips forwarder engine and web dashboard.

This file is kept for backwards compatibility.
The actual app initialization (database, forwarder engine) happens in
src/web/api.py's get_db() function, which is called lazily on first request.
"""

import os
import sys
import logging

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.utils.config import load_config, validate_environment
from src.web.api import app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("teletips-pro")


if __name__ == "__main__":
    validate_environment(raise_on_missing=False)
    config = load_config()
    logger.info(f"Configuration loaded: API_ID={config['API_ID']}")
    logger.info("TeleTips Pro starting...")
    app.run(
        host=config["WEB_HOST"],
        port=int(os.environ.get("PORT", config["WEB_PORT"])),
        debug=False,
        use_reloader=False,
    )
