"""Logging configuration for the application."""

import logging
import sys
from typing import Any, Dict

from .config import settings


def setup_logging() -> None:
    """Set up structured logging for the application."""
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper()),
        format=(
            "%(asctime)s - %(name)s - %(levelname)s - "
            "%(message)s"
        ),
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(name)


def log_event(
        logger: logging.Logger,
        event: str,
        data: Dict[str, Any]) -> None:
    """Log an event with structured data."""
    logger.info(f"Event: {event}", extra={"event_data": data})
