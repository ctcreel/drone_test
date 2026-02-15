"""MAVLink bridge data models."""

from enum import StrEnum

from pydantic import BaseModel, Field


class AutopilotState(StrEnum):
    """Autopilot state enumeration."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ARMED = "armed"
    FLYING = "flying"
    LANDING = "landing"
    LANDED = "landed"


class MavlinkCommand(BaseModel):
    """Command to send via MAVLink."""

    command_type: str  # e.g., "SET_MODE", "ARM", "TAKEOFF", "GOTO", "LAND", "RTL"
    parameters: dict[str, float] = Field(default_factory=dict)
    target_system: int = Field(default=1)
    target_component: int = Field(default=1)


class TelemetryData(BaseModel):
    """Telemetry data from the autopilot."""

    latitude: float
    longitude: float
    altitude: float
    heading: float = Field(ge=0.0, le=360.0)
    ground_speed: float = Field(ge=0.0)
    vertical_speed: float
    battery_voltage: float = Field(ge=0.0)
    battery_remaining: int = Field(ge=0, le=100)
    gps_fix_type: int = Field(ge=0)
    satellites_visible: int = Field(ge=0)


class GpsPosition(BaseModel):
    """GPS position."""

    latitude: float
    longitude: float
    altitude: float
