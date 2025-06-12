# logger_setup.py
import logging
import sys
from logging.handlers import RotatingFileHandler


def setup_logger():
    """Configures the root logger to output to both console and a rotating file."""
    # Create a logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)  # Set the lowest level of messages to handle

    # Create a formatter
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    # --- File Handler ---
    # This will write logs to 'trading_bot.log', create a new file when it reaches 5MB,
    # and keep up to 5 old log files as backups.
    file_handler = RotatingFileHandler("trading_bot.log", maxBytes=5 * 1024 * 1024, backupCount=5)
    file_handler.setFormatter(formatter)

    # --- Console Handler ---
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    # Add handlers to the logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    # --- Redirect stdout and stderr to the logger ---
    # This is a powerful trick to capture ALL print statements and errors from any library.
    class LoggerWriter:
        def __init__(self, level):
            self.level = level

        def write(self, message):
            if message != "\n":
                self.level(message.strip())

        def flush(self):
            pass  # Required for stream interface

    sys.stdout = LoggerWriter(logger.info)
    sys.stderr = LoggerWriter(logger.error)
