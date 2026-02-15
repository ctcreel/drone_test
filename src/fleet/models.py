"""Fleet domain models for drone management."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from src.constants import PARTITION_KEY_DRONE


class DroneStatus(StrEnum):
    """Drone lifecycle states."""

    REGISTERED = "registered"
    AVAILABLE = "available"
    ASSIGNED = "assigned"
    ACTIVE = "active"
    RETURNING = "returning"
    MAINTENANCE = "maintenance"
    DEREGISTERED = "deregistered"


class DroneHealth(BaseModel):
    """Real-time drone health metrics."""

    battery_voltage: float = Field(ge=0)
    battery_remaining_percent: float = Field(ge=0, le=100)
    estimated_flight_time_seconds: int = Field(ge=0)
    connectivity: str = Field(default="connected")
    fail_safe_state: str = Field(default="CONNECTED")
    cpu_temperature_celsius: float = Field(default=0.0, ge=0)
    gpu_utilization_percent: float = Field(default=0.0, ge=0, le=100)


class Drone(BaseModel):
    """Registered drone entity."""

    drone_id: str
    name: str = Field(min_length=1, max_length=200)
    iot_thing_name: str = Field(default="")
    status: DroneStatus = Field(default=DroneStatus.REGISTERED)
    health: DroneHealth | None = None
    last_seen: str = Field(default="")
    registration_date: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
    )
    created_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
    )

    def to_dynamodb_item(self) -> dict[str, Any]:
        """Convert to DynamoDB item format."""
        item: dict[str, Any] = {
            "pk": f"{PARTITION_KEY_DRONE}{self.drone_id}",
            "sk": "METADATA",
            "drone_id": self.drone_id,
            "name": self.name,
            "iot_thing_name": self.iot_thing_name,
            "status": self.status,
            "last_seen": self.last_seen,
            "registration_date": self.registration_date,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "gsi1pk": self.status,
            "gsi1sk": self.created_at,
        }
        if self.health:
            item["health"] = self.health.model_dump()
        return item

    @classmethod
    def from_dynamodb_item(cls, item: dict[str, Any]) -> "Drone":
        """Create from DynamoDB item format."""
        health_data = item.get("health")
        return cls(
            drone_id=item["drone_id"],
            name=item["name"],
            iot_thing_name=item.get("iot_thing_name", ""),
            status=DroneStatus(item["status"]),
            health=DroneHealth(**health_data) if health_data else None,
            last_seen=item.get("last_seen", ""),
            registration_date=item.get("registration_date", ""),
            created_at=item["created_at"],
            updated_at=item["updated_at"],
        )


class FleetState(BaseModel):
    """Summary of current fleet status."""

    total_drones: int = Field(ge=0)
    available_drones: int = Field(ge=0)
    active_drones: int = Field(ge=0)
    maintenance_drones: int = Field(ge=0)
