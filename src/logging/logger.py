"""Core logging configuration and logger factory."""

import logging
import sys
from dataclasses import dataclass, field
from typing import TextIO

from src.logging.config import LogFormat, LoggingConfig, get_logging_config
from src.logging.formatters import HumanFormatter, JSONFormatter


@dataclass
class LoggingState:
    """Internal state for logging configuration."""

    configured: bool = field(default=False)


_state = LoggingState()


def setup_logging(
    config: LoggingConfig | None = None,
    stream: TextIO | None = None,
    *,
    force: bool = False,
) -> None:
    """Set up the root logger with appropriate formatter and handler.

    Args:
        config: Optional LoggingConfig instance. Loads from environment if not provided.
        stream: Output stream for logs. Defaults to sys.stdout.
        force: If True, reconfigure even if already configured.
    """
    if _state.configured and not force:
        return

    if config is None:
        config = get_logging_config()

    root_logger = logging.getLogger()
    root_logger.setLevel(config.log_level.value)

    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(stream or sys.stdout)

    if config.log_format == LogFormat.JSON:
        formatter = JSONFormatter(
            service_name=config.service_name,
            include_timestamp=config.include_timestamp,
            include_location=config.include_location,
        )
    else:
        formatter = HumanFormatter(use_colors=True)

    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    logging.getLogger("boto3").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    _state.configured = True


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name.

    Args:
        name: Logger name, typically __name__ of the calling module.

    Returns:
        A configured logger instance.
    """
    return logging.getLogger(name)


def reset_logging() -> None:
    """Reset logging configuration. Primarily for testing."""
    _state.configured = False

    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    get_logging_config.cache_clear()
