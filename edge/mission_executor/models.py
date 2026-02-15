"""Mission executor data models."""

from enum import StrEnum

from pydantic import BaseModel, Field


class ExecutorState(StrEnum):
    """State of the mission executor."""

    IDLE = "idle"
    LOADING = "loading"
    EXECUTING = "executing"
    PAUSED = "paused"
    COMPLETING = "completing"
    COMPLETED = "completed"
    ABORTED = "aborted"


class Waypoint(BaseModel):
    """A single waypoint in a mission segment."""

    latitude: float
    longitude: float
    altitude: float
    speed: float = Field(default=5.0, ge=0.5, le=20.0)
    loiter_time_seconds: int = Field(default=0, ge=0)


class MissionSegment(BaseModel):
    """A segment of a mission containing waypoints."""

    segment_id: str
    mission_id: str
    waypoints: list[Waypoint]
    capture_images: bool = Field(default=True)


class WaypointProgress(BaseModel):
    """Progress through waypoints in a mission segment."""

    segment_id: str
    current_waypoint_index: int = Field(default=0, ge=0)
    total_waypoints: int = Field(ge=1)
    distance_to_next_meters: float = Field(default=0.0, ge=0.0)
    estimated_time_remaining_seconds: float = Field(default=0.0, ge=0.0)
