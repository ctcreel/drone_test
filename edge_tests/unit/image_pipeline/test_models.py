"""Tests for image pipeline data models."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from edge.image_pipeline.models import (
    CapturedFrame,
    ImageMetadata,
    UploadRequest,
    UploadStatus,
)


class TestUploadStatus:
    def test_pending_value(self):
        assert UploadStatus.PENDING.value == "pending"

    def test_uploading_value(self):
        assert UploadStatus.UPLOADING.value == "uploading"

    def test_uploaded_value(self):
        assert UploadStatus.UPLOADED.value == "uploaded"

    def test_failed_value(self):
        assert UploadStatus.FAILED.value == "failed"

    def test_all_statuses_count(self):
        assert len(UploadStatus) == 4

    def test_values_are_lowercase(self):
        for status in UploadStatus:
            assert status.value == status.value.lower()

    def test_is_string_enum(self):
        assert isinstance(UploadStatus.PENDING, str)
        assert UploadStatus.PENDING == "pending"


class TestImageMetadata:
    def test_valid_metadata(self):
        metadata = ImageMetadata(
            drone_id="drone-001",
            mission_id="mission-001",
            latitude=40.7128,
            longitude=-74.0060,
            altitude=50.0,
            heading=180.0,
        )
        assert metadata.drone_id == "drone-001"
        assert metadata.mission_id == "mission-001"
        assert metadata.latitude == 40.7128
        assert metadata.longitude == -74.0060
        assert metadata.altitude == 50.0
        assert metadata.heading == 180.0
        assert isinstance(metadata.capture_time, datetime)

    def test_custom_capture_time(self):
        custom_time = datetime(2025, 6, 15, 12, 0, 0)
        metadata = ImageMetadata(
            drone_id="drone-001",
            mission_id="mission-001",
            latitude=0.0,
            longitude=0.0,
            altitude=0.0,
            heading=0.0,
            capture_time=custom_time,
        )
        assert metadata.capture_time == custom_time

    def test_heading_minimum(self):
        metadata = ImageMetadata(
            drone_id="drone-001",
            mission_id="mission-001",
            latitude=0.0, longitude=0.0, altitude=0.0, heading=0.0,
        )
        assert metadata.heading == 0.0

    def test_heading_maximum(self):
        metadata = ImageMetadata(
            drone_id="drone-001",
            mission_id="mission-001",
            latitude=0.0, longitude=0.0, altitude=0.0, heading=360.0,
        )
        assert metadata.heading == 360.0

    def test_heading_below_minimum_rejected(self):
        with pytest.raises(ValidationError):
            ImageMetadata(
                drone_id="drone-001",
                mission_id="mission-001",
                latitude=0.0, longitude=0.0, altitude=0.0, heading=-1.0,
            )

    def test_heading_above_maximum_rejected(self):
        with pytest.raises(ValidationError):
            ImageMetadata(
                drone_id="drone-001",
                mission_id="mission-001",
                latitude=0.0, longitude=0.0, altitude=0.0, heading=361.0,
            )

    def test_serialization_roundtrip(self):
        metadata = ImageMetadata(
            drone_id="drone-001",
            mission_id="mission-001",
            latitude=40.7128,
            longitude=-74.0060,
            altitude=50.0,
            heading=180.0,
        )
        data = metadata.model_dump()
        restored = ImageMetadata(**data)
        assert restored.drone_id == metadata.drone_id
        assert restored.latitude == metadata.latitude


class TestCapturedFrame:
    def test_valid_frame(self):
        metadata = ImageMetadata(
            drone_id="drone-001",
            mission_id="mission-001",
            latitude=40.7128,
            longitude=-74.0060,
            altitude=50.0,
            heading=180.0,
        )
        frame = CapturedFrame(
            frame_id="frame-001",
            image_key="images/captures/mission-001/drone-001/20250615.jpg",
            metadata=metadata,
            size_bytes=1024,
            compression_quality=85,
        )
        assert frame.frame_id == "frame-001"
        assert frame.image_key.endswith(".jpg")
        assert frame.size_bytes == 1024
        assert frame.compression_quality == 85

    def test_size_bytes_zero(self):
        metadata = ImageMetadata(
            drone_id="d", mission_id="m",
            latitude=0, longitude=0, altitude=0, heading=0,
        )
        frame = CapturedFrame(
            frame_id="f", image_key="k",
            metadata=metadata, size_bytes=0, compression_quality=50,
        )
        assert frame.size_bytes == 0

    def test_size_bytes_negative_rejected(self):
        metadata = ImageMetadata(
            drone_id="d", mission_id="m",
            latitude=0, longitude=0, altitude=0, heading=0,
        )
        with pytest.raises(ValidationError):
            CapturedFrame(
                frame_id="f", image_key="k",
                metadata=metadata, size_bytes=-1, compression_quality=50,
            )

    def test_compression_quality_minimum(self):
        metadata = ImageMetadata(
            drone_id="d", mission_id="m",
            latitude=0, longitude=0, altitude=0, heading=0,
        )
        frame = CapturedFrame(
            frame_id="f", image_key="k",
            metadata=metadata, size_bytes=0, compression_quality=1,
        )
        assert frame.compression_quality == 1

    def test_compression_quality_maximum(self):
        metadata = ImageMetadata(
            drone_id="d", mission_id="m",
            latitude=0, longitude=0, altitude=0, heading=0,
        )
        frame = CapturedFrame(
            frame_id="f", image_key="k",
            metadata=metadata, size_bytes=0, compression_quality=100,
        )
        assert frame.compression_quality == 100

    def test_compression_quality_zero_rejected(self):
        metadata = ImageMetadata(
            drone_id="d", mission_id="m",
            latitude=0, longitude=0, altitude=0, heading=0,
        )
        with pytest.raises(ValidationError):
            CapturedFrame(
                frame_id="f", image_key="k",
                metadata=metadata, size_bytes=0, compression_quality=0,
            )

    def test_compression_quality_above_100_rejected(self):
        metadata = ImageMetadata(
            drone_id="d", mission_id="m",
            latitude=0, longitude=0, altitude=0, heading=0,
        )
        with pytest.raises(ValidationError):
            CapturedFrame(
                frame_id="f", image_key="k",
                metadata=metadata, size_bytes=0, compression_quality=101,
            )


class TestUploadRequest:
    def test_valid_request(self):
        metadata = ImageMetadata(
            drone_id="drone-001",
            mission_id="mission-001",
            latitude=40.7128,
            longitude=-74.0060,
            altitude=50.0,
            heading=180.0,
        )
        request = UploadRequest(
            frame_id="frame-001",
            image_key="images/test.jpg",
            metadata=metadata,
        )
        assert request.frame_id == "frame-001"
        assert request.status == UploadStatus.PENDING
        assert request.retry_count == 0

    def test_custom_status(self):
        metadata = ImageMetadata(
            drone_id="d", mission_id="m",
            latitude=0, longitude=0, altitude=0, heading=0,
        )
        request = UploadRequest(
            frame_id="f", image_key="k",
            metadata=metadata,
            status=UploadStatus.UPLOADING,
        )
        assert request.status == UploadStatus.UPLOADING

    def test_custom_retry_count(self):
        metadata = ImageMetadata(
            drone_id="d", mission_id="m",
            latitude=0, longitude=0, altitude=0, heading=0,
        )
        request = UploadRequest(
            frame_id="f", image_key="k",
            metadata=metadata,
            retry_count=3,
        )
        assert request.retry_count == 3

    def test_negative_retry_count_rejected(self):
        metadata = ImageMetadata(
            drone_id="d", mission_id="m",
            latitude=0, longitude=0, altitude=0, heading=0,
        )
        with pytest.raises(ValidationError):
            UploadRequest(
                frame_id="f", image_key="k",
                metadata=metadata,
                retry_count=-1,
            )

    def test_all_upload_statuses(self):
        metadata = ImageMetadata(
            drone_id="d", mission_id="m",
            latitude=0, longitude=0, altitude=0, heading=0,
        )
        for status in UploadStatus:
            request = UploadRequest(
                frame_id="f", image_key="k",
                metadata=metadata,
                status=status,
            )
            assert request.status == status

    def test_serialization_roundtrip(self):
        metadata = ImageMetadata(
            drone_id="drone-001",
            mission_id="mission-001",
            latitude=40.7128,
            longitude=-74.0060,
            altitude=50.0,
            heading=180.0,
        )
        request = UploadRequest(
            frame_id="frame-001",
            image_key="images/test.jpg",
            metadata=metadata,
            status=UploadStatus.UPLOADED,
            retry_count=2,
        )
        data = request.model_dump()
        restored = UploadRequest(**data)
        assert restored.frame_id == request.frame_id
        assert restored.status == request.status
        assert restored.retry_count == request.retry_count
