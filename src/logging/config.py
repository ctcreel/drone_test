"""Logging configuration using Pydantic settings."""

from enum import StrEnum
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LogLevel(StrEnum):
    """Valid log levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogFormat(StrEnum):
    """Valid log formats."""

    JSON = "json"
    HUMAN = "human"


class LoggingConfig(BaseSettings):
    """Logging configuration loaded from environment variables.

    Attributes:
        log_level: Minimum log level to output.
        log_format: Output format - json for production, human for development.
        service_name: Service identifier for log aggregation.
        include_timestamp: Whether to include timestamp.
        include_location: Whether to include file/function/line info.
    """

    model_config = SettingsConfigDict(
        env_prefix="",
        case_sensitive=False,
    )

    log_level: LogLevel = Field(default=LogLevel.INFO)
    log_format: LogFormat = Field(default=LogFormat.JSON)
    service_name: str = Field(default="drone-fleet-search")
    include_timestamp: bool = Field(default=True)
    include_location: bool = Field(default=True)


@lru_cache
def get_logging_config() -> LoggingConfig:
    """Get cached logging configuration instance."""
    return LoggingConfig()
