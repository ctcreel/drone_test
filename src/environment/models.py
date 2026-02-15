"""Environment domain models."""

from typing import Any

from pydantic import BaseModel, Field


class BuildingFootprint(BaseModel):
    """Building footprint with elevation data."""

    coordinates: list[list[float]]
    ground_elevation: float = Field(default=0.0, ge=0)
    height: float = Field(default=0.0, ge=0)


class ObstacleZone(BaseModel):
    """Obstacle zone with clearance requirement."""

    coordinates: list[list[float]]
    clearance_meters: float = Field(default=10.0, ge=0)
    description: str = Field(default="")


class NoFlyZone(BaseModel):
    """No-fly restricted area."""

    coordinates: list[list[float]]
    description: str = Field(default="")


class EnvironmentModel(BaseModel):
    """Complete environment model for mission planning."""

    environment_id: str
    name: str = Field(min_length=1, max_length=200)
    bounds: list[list[float]]
    building_footprints: list[BuildingFootprint] = []
    obstacle_zones: list[ObstacleZone] = []
    no_fly_zones: list[NoFlyZone] = []
    created_at: str = Field(default="")

    def to_dynamodb_item(self) -> dict[str, Any]:
        """Convert to DynamoDB item format."""
        return {
            "pk": f"ENV#{self.environment_id}",
            "sk": "METADATA",
            "environment_id": self.environment_id,
            "name": self.name,
            "bounds": self.bounds,
            "building_count": len(self.building_footprints),
            "obstacle_count": len(self.obstacle_zones),
            "no_fly_count": len(self.no_fly_zones),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dynamodb_item(
        cls,
        item: dict[str, Any],
        full_model: dict[str, Any] | None = None,
    ) -> "EnvironmentModel":
        """Create from DynamoDB item and optional full model from S3.

        Args:
            item: DynamoDB metadata item.
            full_model: Full model loaded from S3.

        Returns:
            EnvironmentModel instance.
        """
        if full_model:
            return cls(**full_model)
        return cls(
            environment_id=item["environment_id"],
            name=item["name"],
            bounds=item["bounds"],
            created_at=item.get("created_at", ""),
        )
