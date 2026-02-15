"""Structured logging for drone fleet search services.

Usage:
    from src.logging import setup_logging, get_logger

    setup_logging()
    logger = get_logger(__name__)
    logger.info("Processing mission", extra={"mission_id": "123"})
"""

from src.logging.config import LoggingConfig
from src.logging.context import (
    clear_context,
    correlation_id,
    get_correlation_id,
    get_extra_context,
    set_correlation_id,
    set_extra_context,
)
from src.logging.formatters import HumanFormatter, JSONFormatter
from src.logging.logger import get_logger, setup_logging

__all__ = [
    "HumanFormatter",
    "JSONFormatter",
    "LoggingConfig",
    "clear_context",
    "correlation_id",
    "get_correlation_id",
    "get_extra_context",
    "get_logger",
    "set_correlation_id",
    "set_extra_context",
    "setup_logging",
]
