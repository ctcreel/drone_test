"""Analysis domain models for image detection pipeline."""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from src.constants import PARTITION_KEY_MISSION


class BoundingBox(BaseModel):
    """Bounding box for a detected object in an image."""

    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(ge=1)
    height: int = Field(ge=1)


class DetectionItem(BaseModel):
    """Single detection from Bedrock Vision analysis."""

    label: str
    confidence: float = Field(ge=0.0, le=1.0)
    bounding_box: BoundingBox
    reasoning: str


class AnalysisResult(BaseModel):
    """Complete result from Bedrock Vision image analysis."""

    detections: list[DetectionItem] = []
    scene_description: str = ""
    search_relevant: bool = False


class CapturedImage(BaseModel):
    """Image capture metadata from a drone."""

    mission_id: str
    drone_id: str
    image_key: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    altitude: float = Field(ge=0, le=500)
    heading: float = Field(ge=0, le=360)
    capture_time: str


class ReviewDecision(BaseModel):
    """Operator review decision for a detection."""

    decision: str = Field(pattern=r"^(confirmed|dismissed)$")
    operator_id: str = Field(min_length=1)
    notes: str = Field(default="")


class Detection(BaseModel):
    """Persisted detection entity."""

    detection_id: str
    mission_id: str
    drone_id: str
    image_key: str
    source_image_key: str
    label: str
    confidence: float = Field(ge=0.0, le=1.0)
    bounding_box: BoundingBox
    reasoning: str
    latitude: float
    longitude: float
    altitude: float
    heading: float
    capture_time: str
    reviewed: str = Field(default="pending")
    reviewed_by: str = Field(default="")
    reviewed_at: str = Field(default="")
    created_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
    )

    def to_dynamodb_item(self) -> dict[str, Any]:
        """Convert to DynamoDB item format."""
        return {
            "pk": f"{PARTITION_KEY_MISSION}{self.mission_id}",
            "sk": f"DETECTION#{self.detection_id}",
            "detection_id": self.detection_id,
            "mission_id": self.mission_id,
            "drone_id": self.drone_id,
            "image_key": self.image_key,
            "source_image_key": self.source_image_key,
            "label": self.label,
            "confidence": self.confidence,
            "bounding_box": self.bounding_box.model_dump(),
            "reasoning": self.reasoning,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "altitude": self.altitude,
            "heading": self.heading,
            "capture_time": self.capture_time,
            "reviewed": self.reviewed,
            "reviewed_by": self.reviewed_by,
            "reviewed_at": self.reviewed_at,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dynamodb_item(cls, item: dict[str, Any]) -> "Detection":
        """Create from DynamoDB item format."""
        return cls(
            detection_id=item["detection_id"],
            mission_id=item["mission_id"],
            drone_id=item["drone_id"],
            image_key=item["image_key"],
            source_image_key=item["source_image_key"],
            label=item["label"],
            confidence=item["confidence"],
            bounding_box=BoundingBox(**item["bounding_box"]),
            reasoning=item["reasoning"],
            latitude=item["latitude"],
            longitude=item["longitude"],
            altitude=item["altitude"],
            heading=item["heading"],
            capture_time=item["capture_time"],
            reviewed=item.get("reviewed", "pending"),
            reviewed_by=item.get("reviewed_by", ""),
            reviewed_at=item.get("reviewed_at", ""),
            created_at=item["created_at"],
        )
