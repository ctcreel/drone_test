"""Obstacle avoidance data models."""

from enum import StrEnum

from pydantic import BaseModel, Field


class ObstacleSeverity(StrEnum):
    """Severity level of a detected obstacle."""

    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DepthFrame(BaseModel):
    """Depth camera frame data."""

    width: int = Field(ge=1)
    height: int = Field(ge=1)
    min_distance_meters: float = Field(ge=0.0)
    max_distance_meters: float = Field(ge=0.0)
    timestamp_ms: int = Field(ge=0)


class ObstacleDetection(BaseModel):
    """Detected obstacle."""

    distance_meters: float = Field(ge=0.0)
    bearing_degrees: float = Field(ge=-180.0, le=180.0)
    severity: ObstacleSeverity
    width_meters: float = Field(ge=0.0)
    height_meters: float = Field(ge=0.0)


class AvoidanceManeuver(BaseModel):
    """Computed avoidance maneuver."""

    maneuver_type: str  # "climb", "descend", "lateral_left", "lateral_right", "hold"
    magnitude_meters: float = Field(ge=0.0)
    duration_seconds: float = Field(ge=0.0)
    priority: int = Field(ge=0, le=10)
