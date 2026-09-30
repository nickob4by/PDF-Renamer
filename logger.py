"""
logger.py
Project logging configuration.
"""

import logging
from datetime import datetime
from config import LOG_DIR, LOG_LEVEL

# Create logs folder if it doesn't exist
LOG_DIR.mkdir(exist_ok=True)

# Log filename (one log per day)
log_file = LOG_DIR / f"{datetime.now():%Y-%m-%d}.log"

# Configure logger
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8")
    ]
)

logger = logging.getLogger("PDFAutoRename")