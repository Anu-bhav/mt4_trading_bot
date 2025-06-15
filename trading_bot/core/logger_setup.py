# trading_bot/core/logger_setup.py
import logging
import os
import sys
from logging.handlers import RotatingFileHandler


def setup_logger():
    """Configures the root logger to output to both console and a rotating file."""
    # Create logs directory if it doesn't exist
    logs_dir = "logs"
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)

    log_format = "%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
    formatter = logging.Formatter(log_format, datefmt="%Y-%m-%d %H:%M:%S")

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Prevent adding duplicate handlers
    if logger.hasHandlers():
        logger.handlers.clear()

    # File Handler
    file_handler = RotatingFileHandler(os.path.join(logs_dir, "trading_bot.log"), maxBytes=5 * 1024 * 1024, backupCount=5)
    file_handler.setFormatter(formatter)

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    # --- The stdout/stderr redirection has been REMOVED ---

    # logging.info("Logger has been set up.")
