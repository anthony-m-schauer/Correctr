"""
Correctr Logging Utilities

Purpose:
    Sets up simple console logging for development.

Privacy note:
    The proof-of-concept logs workflow events and character counts only.
    It should not log the user's selected text.
"""

from __future__ import annotations

import logging


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """
    Creates and returns the Correctr logger.
    """
    logger = logging.getLogger("correctr")

    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    logger.setLevel(numeric_level)

    if not logger.handlers:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(numeric_level)

        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)s | %(message)s",
            datefmt="%H:%M:%S",
        )
        console_handler.setFormatter(formatter)

        logger.addHandler(console_handler)

    logger.propagate = False

    return logger
