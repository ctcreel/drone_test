"""Image pipeline data models."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class UploadStatus(StrEnum):
    """Status of an image upload."""

    PENDING = "pending"
    UPLOADING = "uploading"
    UPLOADED = "uploaded"
    FAILED = "failed"


class ImageMetadata(BaseModel):
    """Metadata for a captured image."""

    drone_id: str
    mission_id: str
    latitude: float
    longitude: float
    altitude: float
    heading: float = Field(ge=0.0, le=360.0)
    capture_time: datetime = Field(default_factory=datetime.utcnow)


class CapturedFrame(BaseModel):
    """A captured image frame with metadata."""

    frame_id: str
    image_key: str
    metadata: ImageMetadata
    size_bytes: int = Field(ge=0)
    compression_quality: int = Field(ge=1, le=100)


class UploadRequest(BaseModel):
    """Request to upload a captured image."""

    frame_id: str
    image_key: str
    metadata: ImageMetadata
    status: UploadStatus = Field(default=UploadStatus.PENDING)
    retry_count: int = Field(default=0, ge=0)
