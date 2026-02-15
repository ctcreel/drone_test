"""Application configuration using Pydantic BaseSettings.

All settings are loaded from environment variables.
No .env files - use AWS Secrets Manager or parameter store.

Usage:
    from src.config import get_settings

    settings = get_settings()
    print(settings.environment)
    print(settings.table_name)
"""

from enum import StrEnum
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    """Valid deployment environments."""

    DEVELOPMENT = "development"
    TESTING = "testing"
    DEMO = "demo"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Attributes:
        service_name: Name of this service for logging/tracing.
        environment: Deployment environment.
        aws_region: AWS region for service calls.
        table_name: DynamoDB table name.
        image_bucket_name: S3 bucket for drone images.
        iot_endpoint: AWS IoT Core endpoint.
        bedrock_model_id: Claude model ID for Bedrock.
        log_level: Logging level.
        enable_tracing: Whether to enable X-Ray tracing.
        api_timeout_seconds: Timeout for API calls.
        max_fleet_size: Maximum drones in a fleet.
    """

    model_config = SettingsConfigDict(
        env_file=None,
        case_sensitive=False,
        extra="ignore",
        str_strip_whitespace=True,
    )

    # Service identification
    service_name: str = Field(default="drone-fleet-search", min_length=1)
    environment: Environment = Field(default=Environment.DEVELOPMENT)

    # AWS Configuration
    aws_region: str = Field(default="us-east-1", min_length=1)
    table_name: str = Field(default="drone-fleet-development", min_length=1)
    image_bucket_name: str = Field(default="drone-fleet-images-development", min_length=1)
    iot_endpoint: str = Field(default="", description="AWS IoT Core endpoint")

    # AI Configuration
    bedrock_model_id: str = Field(
        default="anthropic.claude-sonnet-4-5-20250929-v1:0",
        min_length=1,
    )

    # Logging
    log_level: str = Field(default="INFO")

    # Feature flags
    enable_tracing: bool = Field(default=False)
    enable_metrics: bool = Field(default=False)

    # Timeouts and limits
    api_timeout_seconds: int = Field(default=30, ge=1, le=300)
    max_fleet_size: int = Field(default=5, ge=1, le=20)
    mission_planning_timeout_seconds: int = Field(default=60, ge=10, le=300)

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        """Validate log level is one of the allowed values."""
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper_value = value.upper()
        if upper_value not in allowed:
            error_message = f"log_level must be one of {allowed}, got '{value}'"
            raise ValueError(error_message)
        return upper_value

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == Environment.PRODUCTION

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == Environment.DEVELOPMENT


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance.

    Returns:
        Cached Settings instance.
    """
    return Settings()


def validate_startup_config() -> Settings:
    """Validate configuration on application startup.

    Returns:
        Validated Settings instance.

    Raises:
        pydantic.ValidationError: If configuration is invalid.
    """
    return get_settings()
