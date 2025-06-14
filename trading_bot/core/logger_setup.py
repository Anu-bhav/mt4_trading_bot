# trading_bot/core/logger_setup.py
import logging
import os
import sys
from logging.handlers import RotatingFileHandler


def setup_logger():
    """Configures the root logger to output to both console and a rotating file."""
    # Create logs directory if it doesn't exist
    if not os.path.exists("logs"):
        os.makedirs("logs")

    # --- Create a more detailed formatter ---
    # This now includes the file name, line number, and function name.
    log_format = "%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d - %(funcName)s()] - %(message)s"
    formatter = logging.Formatter(log_format, datefmt="%Y-%m-%d %H:%M:%S")

    # Get the root logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)  # Set the lowest level of messages to handle

    # Avoid adding duplicate handlers if this function is called more than once
    if logger.hasHandlers():
        logger.handlers.clear()

    # --- File Handler ---
    # This will write logs to 'logs/trading_bot.log'
    file_handler = RotatingFileHandler("logs/trading_bot.log", maxBytes=5 * 1024 * 1024, backupCount=5)
    file_handler.setFormatter(formatter)

    # --- Console Handler ---
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    # Add handlers to the logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    # --- Redirect stdout and stderr to the logger ---
    class LoggerWriter:
        def __init__(self, level):
            self.level = level

        def write(self, message):
            # Avoid logging empty newlines
            if message.strip() != "":
                self.level(message.strip())

        def flush(self):
            # This is needed for the stream interface but does nothing here.
            pass

    sys.stdout = LoggerWriter(logger.info)
    sys.stderr = LoggerWriter(logger.error)

    logging.info("Logger has been set up.")
