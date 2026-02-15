"""Log formatters for different output formats."""

import json
import logging
import traceback
from datetime import UTC, datetime
from typing import Any, ClassVar

from src.logging.context import get_correlation_id, get_extra_context

_STANDARD_LOG_ATTRS: frozenset[str] = frozenset(
    {
        "name",
        "msg",
        "args",
        "created",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "exc_info",
        "exc_text",
        "thread",
        "threadName",
        "taskName",
        "message",
    }
)

_MAX_LOGGER_NAME_LENGTH = 30


class JSONFormatter(logging.Formatter):
    """Format log records as JSON for structured logging.

    Compatible with CloudWatch Logs Insights and other JSON log aggregators.
    """

    def __init__(
        self,
        *,
        service_name: str = "drone-fleet-search",
        include_timestamp: bool = True,
        include_location: bool = True,
    ) -> None:
        """Initialize the JSON formatter.

        Args:
            service_name: Service identifier for log aggregation.
            include_timestamp: Whether to include timestamp field.
            include_location: Whether to include module/function/line fields.
        """
        super().__init__()
        self._service_name = service_name
        self._include_timestamp = include_timestamp
        self._include_location = include_location

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record as a JSON string."""
        log_entry: dict[str, Any] = {}

        if self._include_timestamp:
            log_entry["timestamp"] = datetime.now(UTC).isoformat(timespec="milliseconds")

        log_entry["level"] = record.levelname
        log_entry["logger"] = record.name
        log_entry["message"] = record.getMessage()

        corr_id = get_correlation_id()
        if corr_id:
            log_entry["correlation_id"] = corr_id

        log_entry["service"] = self._service_name

        if self._include_location:
            log_entry["module"] = record.module
            log_entry["function"] = record.funcName
            log_entry["line"] = record.lineno

        extra_context = get_extra_context()
        if extra_context:
            log_entry.update(extra_context)

        extra_fields = {
            key: value
            for key, value in record.__dict__.items()
            if key not in _STANDARD_LOG_ATTRS and not key.startswith("_")
        }
        log_entry.update(extra_fields)

        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else "Unknown",
                "message": str(record.exc_info[1]) if record.exc_info[1] else "",
                "traceback": traceback.format_exception(*record.exc_info),
            }

        return json.dumps(log_entry, default=str)


class HumanFormatter(logging.Formatter):
    """Format log records for human readability in development."""

    COLORS: ClassVar[dict[str, str]] = {
        "DEBUG": "\033[36m",
        "INFO": "\033[32m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[35m",
    }
    RESET: ClassVar[str] = "\033[0m"

    def __init__(self, *, use_colors: bool = True) -> None:
        """Initialize the human formatter.

        Args:
            use_colors: Whether to use ANSI colors in output.
        """
        super().__init__()
        self._use_colors = use_colors

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record for human readability."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        level = record.levelname
        if self._use_colors:
            color = self.COLORS.get(level, "")
            level_string = f"{color}{level:<8}{self.RESET}"
        else:
            level_string = f"{level:<8}"

        logger_name = record.name
        if len(logger_name) > _MAX_LOGGER_NAME_LENGTH:
            truncate_at = _MAX_LOGGER_NAME_LENGTH - 3
            logger_name = "..." + logger_name[-truncate_at:]

        message = record.getMessage()

        context_parts: list[str] = []

        corr_id = get_correlation_id()
        if corr_id:
            context_parts.append(f"correlation_id={corr_id}")

        extra_context = get_extra_context()
        for key, value in extra_context.items():
            context_parts.append(f"{key}={value}")

        for key, value in record.__dict__.items():
            if key not in _STANDARD_LOG_ATTRS and not key.startswith("_"):
                context_parts.append(f"{key}={value}")

        context_string = " ".join(context_parts)

        parts = [timestamp, "|", level_string, "|", f"{logger_name:<30}", "|", message]
        if context_string:
            parts.extend(["|", context_string])

        result = " ".join(parts)

        if record.exc_info:
            result += "\n" + "".join(traceback.format_exception(*record.exc_info))

        return result
