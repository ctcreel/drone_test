"""Edge tier configuration using Pydantic BaseSettings.

All settings are loaded from environment variables on the Jetson.
"""

from enum import StrEnum
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConnectivityMode(StrEnum):
    """MQTT connectivity mode."""

    AWS_IOT = "aws_iot"
    MOSQUITTO = "mosquitto"


class EdgeSettings(BaseSettings):
    """Edge tier settings loaded from environment variables.

    Attributes:
        drone_id: Unique identifier for this drone.
        mqtt_endpoint: MQTT broker endpoint.
        mqtt_port: MQTT broker port.
        connectivity_mode: AWS IoT Core or local Mosquitto.
        mavlink_connection: MAVLink connection string.
        mavlink_baud_rate: MAVLink serial baud rate.
        certificate_path: Path to IoT device certificate.
        private_key_path: Path to IoT device private key.
        root_ca_path: Path to root CA certificate.
        obstacle_detection_range_meters: Range for obstacle detection.
        minimum_clearance_meters: Minimum clearance from obstacles.
        image_capture_interval_seconds: Interval between image captures.
        telemetry_report_interval_seconds: Interval between telemetry reports.
        log_level: Logging level.
    """

    model_config = SettingsConfigDict(
        env_prefix="DRONE_",
        case_sensitive=False,
        extra="ignore",
        str_strip_whitespace=True,
    )

    # Drone identification
    drone_id: str = Field(min_length=1)

    # MQTT configuration
    mqtt_endpoint: str = Field(default="localhost", min_length=1)
    mqtt_port: int = Field(default=1883, ge=1, le=65535)
    connectivity_mode: ConnectivityMode = Field(default=ConnectivityMode.MOSQUITTO)

    # MAVLink configuration
    mavlink_connection: str = Field(default="tcp:127.0.0.1:5760")
    mavlink_baud_rate: int = Field(default=57600)

    # TLS certificates (required for AWS IoT Core mode)
    certificate_path: str = Field(default="")
    private_key_path: str = Field(default="")
    root_ca_path: str = Field(default="")

    # Obstacle avoidance
    obstacle_detection_range_meters: float = Field(default=10.0, ge=1.0, le=50.0)
    minimum_clearance_meters: float = Field(default=2.0, ge=0.5, le=10.0)

    # Image pipeline
    image_capture_interval_seconds: int = Field(default=5, ge=1, le=60)
    image_compression_quality: int = Field(default=85, ge=1, le=100)

    # Telemetry
    telemetry_report_interval_seconds: int = Field(default=2, ge=1, le=30)

    # Fail-safe timeouts (seconds)
    degraded_threshold_seconds: int = Field(default=10, ge=5, le=60)
    holding_threshold_seconds: int = Field(default=30, ge=15, le=120)
    return_threshold_seconds: int = Field(default=120, ge=60, le=600)

    # Logging
    log_level: str = Field(default="INFO")

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


@lru_cache
def get_edge_settings() -> EdgeSettings:
    """Get cached edge settings instance.

    Returns:
        Cached EdgeSettings instance.
    """
    return EdgeSettings()
