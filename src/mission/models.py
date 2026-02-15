"""Mission domain models."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class MissionStatus(StrEnum):
    """Mission lifecycle states."""

    CREATED = "created"
    PLANNED = "planned"
    APPROVED = "approved"
    EXECUTING = "executing"
    COMPLETED = "completed"
    ABORTED = "aborted"


class SearchPattern(StrEnum):
    """Available search patterns for mission planning."""

    PARALLEL_TRACKS = "parallel_tracks"
    EXPANDING_SQUARE = "expanding_square"
    SECTOR_SEARCH = "sector_search"
    BUILDING_PERIMETER = "building_perimeter"
    VERTICAL_SCAN = "vertical_scan"
    CREEPING_LINE = "creeping_line"


class Coordinate(BaseModel):
    """Geographic coordinate."""

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    altitude: float = Field(default=0.0, ge=0, le=500)


class SearchArea(BaseModel):
    """Search area defined as a GeoJSON polygon."""

    coordinates: list[list[Coordinate]]


class Waypoint(BaseModel):
    """Single waypoint in a flight plan."""

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    altitude: float = Field(ge=0, le=500)
    speed: float = Field(default=5.0, ge=0.5, le=20.0)
    camera_interval_seconds: int = Field(default=5, ge=1, le=60)


class FlightSegment(BaseModel):
    """A segment of a drone's flight plan."""

    waypoints: list[Waypoint]
    altitude: float = Field(ge=0, le=500)
    camera_interval_seconds: int = Field(default=5, ge=1, le=60)


class DroneAssignment(BaseModel):
    """Assignment of a drone to mission segments."""

    drone_id: str
    role: str
    segments: list[FlightSegment]


class MissionPlan(BaseModel):
    """AI-generated mission plan."""

    search_pattern: SearchPattern
    reasoning: str
    drone_assignments: list[DroneAssignment]
    estimated_duration_seconds: int = Field(ge=0)
    estimated_coverage_percent: float = Field(ge=0, le=100)
    safety_notes: list[str] = Field(default_factory=list)


class MissionObjective(BaseModel):
    """Operator-submitted mission objective."""

    description: str = Field(min_length=1, max_length=2000)
    search_area: SearchArea
    environment_id: str = Field(min_length=1)


class Mission(BaseModel):
    """Complete mission entity."""

    mission_id: str
    status: MissionStatus = Field(default=MissionStatus.CREATED)
    objective: MissionObjective
    plan: MissionPlan | None = None
    operator_id: str = Field(default="")
    created_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
    )

    def to_dynamodb_item(self) -> dict[str, Any]:
        """Convert to DynamoDB item format."""
        item: dict[str, Any] = {
            "pk": f"MISSION#{self.mission_id}",
            "sk": "METADATA",
            "mission_id": self.mission_id,
            "status": self.status,
            "objective": self.objective.model_dump(),
            "operator_id": self.operator_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "gsi1pk": self.status,
            "gsi1sk": self.created_at,
        }
        if self.plan:
            item["plan"] = self.plan.model_dump()
        return item

    @classmethod
    def from_dynamodb_item(cls, item: dict[str, Any]) -> "Mission":
        """Create from DynamoDB item format."""
        plan_data = item.get("plan")
        return cls(
            mission_id=item["mission_id"],
            status=MissionStatus(item["status"]),
            objective=MissionObjective(**item["objective"]),
            plan=MissionPlan(**plan_data) if plan_data else None,
            operator_id=item.get("operator_id", ""),
            created_at=item["created_at"],
            updated_at=item["updated_at"],
        )


# Valid state transitions
VALID_TRANSITIONS: dict[MissionStatus, set[MissionStatus]] = {
    MissionStatus.CREATED: {MissionStatus.PLANNED},
    MissionStatus.PLANNED: {MissionStatus.APPROVED, MissionStatus.ABORTED},
    MissionStatus.APPROVED: {MissionStatus.EXECUTING, MissionStatus.ABORTED},
    MissionStatus.EXECUTING: {MissionStatus.COMPLETED, MissionStatus.ABORTED},
    MissionStatus.COMPLETED: set(),
    MissionStatus.ABORTED: set(),
}


def validate_transition(current: MissionStatus, target: MissionStatus) -> bool:
    """Check if a mission status transition is valid.

    Args:
        current: Current mission status.
        target: Target mission status.

    Returns:
        True if the transition is valid.
    """
    return target in VALID_TRANSITIONS.get(current, set())
