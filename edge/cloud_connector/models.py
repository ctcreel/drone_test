"""Cloud connector data models."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class MessageDirection(StrEnum):
    """Direction of a cloud message."""

    INBOUND = "inbound"
    OUTBOUND = "outbound"


class CommandType(StrEnum):
    """Type of command from the cloud."""

    MISSION_SEGMENT = "mission_segment"
    RECALL = "recall"
    ABORT = "abort"
    UPDATE_CONFIG = "update_config"


class CloudMessage(BaseModel):
    """Base message for cloud communication."""

    message_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    drone_id: str
    direction: MessageDirection


class CommandMessage(CloudMessage):
    """Command received from cloud."""

    command_type: CommandType
    payload: dict[str, str | int | float | bool | list[str]] = Field(default_factory=dict)


class TelemetryMessage(CloudMessage):
    """Telemetry message sent to cloud."""

    report_type: str
    latitude: float
    longitude: float
    altitude: float
    heading: float
    battery_remaining: int
    ground_speed: float
