"""
logger.py
---------
Configures application-wide logging for the Email Automation & Reminder System.
Logs informative messages to both the console and a persistent file in logs/.
"""

import logging
from pathlib import Path


def setup_logger(
    name: str = "EmailReminderSystem",
    log_file: str = "logs/email_system.log",
    level: int = logging.INFO
) -> logging.Logger:
    """
    Sets up and returns a configured logger instance with both console and file handlers.

    Args:
        name: Name of the logger.
        log_file: Path to the persistent log file.
        level: Logging level (default: logging.INFO).

    Returns:
        logging.Logger: Configured logger.
    """
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid duplicate handlers if setup_logger is called multiple times
    if not logger.handlers:
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

        # File handler (persists all operational records to disk)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # Console handler (standard output for interactive terminal feedback)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger


# Default logger instance
logger = setup_logger()
