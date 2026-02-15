"""Telemetry domain models for drone data processing."""

from typing import Any

from pydantic import BaseModel, Field

from src.constants import PARTITION_KEY_DRONE


class TelemetryReport(BaseModel):
    """Base telemetry report from a drone."""

    drone_id: str
    timestamp: str
    message_type: str = Field(default="telemetry")


class PositionReport(TelemetryReport):
    """Position telemetry from a drone."""

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    altitude: float = Field(ge=0, le=500)
    heading: float = Field(ge=0, le=360)
    speed: float = Field(ge=0)

    def to_dynamodb_item(self) -> dict[str, Any]:
        """Convert to DynamoDB item format."""
        return {
            "pk": f"{PARTITION_KEY_DRONE}{self.drone_id}",
            "sk": f"TELEMETRY#{self.timestamp}",
            "drone_id": self.drone_id,
            "timestamp": self.timestamp,
            "message_type": "position_report",
            "latitude": self.latitude,
            "longitude": self.longitude,
            "altitude": self.altitude,
            "heading": self.heading,
            "speed": self.speed,
            "gsi2pk": f"{PARTITION_KEY_DRONE}{self.drone_id}",
            "gsi2sk": self.timestamp,
        }


class BatteryReport(TelemetryReport):
    """Battery telemetry from a drone."""

    voltage: float = Field(ge=0)
    remaining_percent: float = Field(ge=0, le=100)
    estimated_flight_time_seconds: int = Field(ge=0)

    def to_dynamodb_item(self) -> dict[str, Any]:
        """Convert to DynamoDB item format."""
        return {
            "pk": f"{PARTITION_KEY_DRONE}{self.drone_id}",
            "sk": f"TELEMETRY#{self.timestamp}",
            "drone_id": self.drone_id,
            "timestamp": self.timestamp,
            "message_type": "battery_report",
            "voltage": self.voltage,
            "remaining_percent": self.remaining_percent,
            "estimated_flight_time_seconds": self.estimated_flight_time_seconds,
            "gsi2pk": f"{PARTITION_KEY_DRONE}{self.drone_id}",
            "gsi2sk": self.timestamp,
        }


class ObstacleEvent(TelemetryReport):
    """Obstacle detection event from a drone."""

    obstacle_type: str
    distance_meters: float = Field(ge=0)
    avoidance_action: str

    def to_dynamodb_item(self) -> dict[str, Any]:
        """Convert to DynamoDB item format."""
        return {
            "pk": f"{PARTITION_KEY_DRONE}{self.drone_id}",
            "sk": f"TELEMETRY#{self.timestamp}",
            "drone_id": self.drone_id,
            "timestamp": self.timestamp,
            "message_type": "obstacle_event",
            "obstacle_type": self.obstacle_type,
            "distance_meters": self.distance_meters,
            "avoidance_action": self.avoidance_action,
            "gsi2pk": f"{PARTITION_KEY_DRONE}{self.drone_id}",
            "gsi2sk": self.timestamp,
        }
