"""Tests for ImagePipeline capture, queueing, and upload processing."""

from datetime import datetime
from unittest.mock import patch

from edge.config import EdgeSettings
from edge.image_pipeline.models import (
    CapturedFrame,
    ImageMetadata,
    UploadRequest,
    UploadStatus,
)
from edge.image_pipeline.pipeline import ImagePipeline


def _make_settings(**overrides):
    """Create EdgeSettings for testing."""
    defaults = {
        "drone_id": "drone-test",
        "image_compression_quality": 85,
    }
    defaults.update(overrides)
    return EdgeSettings(**defaults)


def _make_metadata(
    drone_id="drone-test",
    mission_id="mission-001",
    capture_time=None,
):
    """Create ImageMetadata for testing."""
    return ImageMetadata(
        drone_id=drone_id,
        mission_id=mission_id,
        latitude=40.7128,
        longitude=-74.0060,
        altitude=50.0,
        heading=180.0,
        capture_time=capture_time or datetime(2025, 6, 15, 12, 0, 0),
    )


class TestImagePipelineInit:
    def test_compression_quality_from_settings(self):
        pipeline = ImagePipeline(_make_settings(image_compression_quality=90))
        assert pipeline._compression_quality == 90

    def test_empty_upload_queue(self):
        pipeline = ImagePipeline(_make_settings())
        assert pipeline._upload_queue == []

    def test_empty_completed_uploads(self):
        pipeline = ImagePipeline(_make_settings())
        assert pipeline._completed_uploads == []

    def test_empty_failed_uploads(self):
        pipeline = ImagePipeline(_make_settings())
        assert pipeline._failed_uploads == []


class TestCaptureFrame:
    def test_capture_returns_frame(self):
        pipeline = ImagePipeline(_make_settings())
        metadata = _make_metadata()

        frame = pipeline.capture_frame(metadata)

        assert isinstance(frame, CapturedFrame)
        assert frame.metadata == metadata

    def test_capture_generates_unique_frame_id(self):
        pipeline = ImagePipeline(_make_settings())
        metadata = _make_metadata()

        frame1 = pipeline.capture_frame(metadata)
        frame2 = pipeline.capture_frame(metadata)

        assert frame1.frame_id != frame2.frame_id

    def test_capture_uses_compression_quality(self):
        pipeline = ImagePipeline(_make_settings(image_compression_quality=70))
        metadata = _make_metadata()

        frame = pipeline.capture_frame(metadata)

        assert frame.compression_quality == 70

    def test_capture_initial_size_is_zero(self):
        pipeline = ImagePipeline(_make_settings())
        metadata = _make_metadata()

        frame = pipeline.capture_frame(metadata)

        assert frame.size_bytes == 0

    def test_capture_generates_image_key(self):
        pipeline = ImagePipeline(_make_settings())
        metadata = _make_metadata()

        frame = pipeline.capture_frame(metadata)

        assert frame.image_key != ""
        assert frame.image_key.endswith(".jpg")


class TestQueueUpload:
    def test_queue_upload_returns_request(self):
        pipeline = ImagePipeline(_make_settings())
        metadata = _make_metadata()
        frame = pipeline.capture_frame(metadata)

        request = pipeline.queue_upload(frame)

        assert isinstance(request, UploadRequest)
        assert request.frame_id == frame.frame_id
        assert request.image_key == frame.image_key
        assert request.status == UploadStatus.PENDING
        assert request.retry_count == 0

    def test_queue_upload_adds_to_queue(self):
        pipeline = ImagePipeline(_make_settings())
        metadata = _make_metadata()
        frame = pipeline.capture_frame(metadata)

        pipeline.queue_upload(frame)

        assert len(pipeline._upload_queue) == 1

    def test_queue_multiple_uploads(self):
        pipeline = ImagePipeline(_make_settings())

        for _ in range(5):
            metadata = _make_metadata()
            frame = pipeline.capture_frame(metadata)
            pipeline.queue_upload(frame)

        assert len(pipeline._upload_queue) == 5


class TestProcessUploadQueue:
    def test_empty_queue_returns_empty(self):
        pipeline = ImagePipeline(_make_settings())

        result = pipeline.process_upload_queue()

        assert result == []

    def test_process_pending_upload_succeeds(self):
        pipeline = ImagePipeline(_make_settings())
        metadata = _make_metadata()
        frame = pipeline.capture_frame(metadata)
        pipeline.queue_upload(frame)

        processed = pipeline.process_upload_queue()

        assert len(processed) == 1
        assert processed[0].status == UploadStatus.UPLOADED
        assert processed[0].frame_id in pipeline._completed_uploads

    def test_process_clears_completed_from_queue(self):
        pipeline = ImagePipeline(_make_settings())
        metadata = _make_metadata()
        frame = pipeline.capture_frame(metadata)
        pipeline.queue_upload(frame)

        pipeline.process_upload_queue()

        assert pipeline.get_pending_count() == 0

    def test_process_already_uploaded_moves_to_completed(self):
        pipeline = ImagePipeline(_make_settings())
        metadata = _make_metadata()
        frame = pipeline.capture_frame(metadata)
        request = pipeline.queue_upload(frame)
        request.status = UploadStatus.UPLOADED

        processed = pipeline.process_upload_queue()

        assert len(processed) == 1
        assert frame.frame_id in pipeline._completed_uploads

    def test_process_already_failed_moves_to_failed(self):
        pipeline = ImagePipeline(_make_settings())
        metadata = _make_metadata()
        frame = pipeline.capture_frame(metadata)
        request = pipeline.queue_upload(frame)
        request.status = UploadStatus.FAILED

        processed = pipeline.process_upload_queue()

        assert len(processed) == 1
        assert frame.frame_id in pipeline._failed_uploads

    def test_failed_upload_retries(self):
        pipeline = ImagePipeline(_make_settings())
        metadata = _make_metadata()
        frame = pipeline.capture_frame(metadata)
        pipeline.queue_upload(frame)

        # Mock _attempt_upload to fail
        with patch.object(pipeline, "_attempt_upload", return_value=False):
            processed = pipeline.process_upload_queue()

        # Should have been retried, so still in queue
        assert len(processed) == 0
        assert pipeline.get_pending_count() == 1

    def test_failed_upload_exceeds_max_retries(self):
        pipeline = ImagePipeline(_make_settings())
        metadata = _make_metadata()
        frame = pipeline.capture_frame(metadata)
        request = pipeline.queue_upload(frame)
        request.retry_count = 3  # Already at max

        with patch.object(pipeline, "_attempt_upload", return_value=False):
            processed = pipeline.process_upload_queue()

        assert len(processed) == 1
        assert processed[0].status == UploadStatus.FAILED
        assert frame.frame_id in pipeline._failed_uploads

    def test_retry_increments_count(self):
        pipeline = ImagePipeline(_make_settings())
        metadata = _make_metadata()
        frame = pipeline.capture_frame(metadata)
        pipeline.queue_upload(frame)

        with patch.object(pipeline, "_attempt_upload", return_value=False):
            pipeline.process_upload_queue()

        # Check the request in the queue has incremented retry count
        assert pipeline._upload_queue[0].retry_count == 1

    def test_process_multiple_uploads(self):
        pipeline = ImagePipeline(_make_settings())

        for _ in range(3):
            metadata = _make_metadata()
            frame = pipeline.capture_frame(metadata)
            pipeline.queue_upload(frame)

        processed = pipeline.process_upload_queue()

        assert len(processed) == 3
        assert pipeline.get_pending_count() == 0


class TestGetPendingCount:
    def test_empty_queue(self):
        pipeline = ImagePipeline(_make_settings())
        assert pipeline.get_pending_count() == 0

    def test_after_queueing(self):
        pipeline = ImagePipeline(_make_settings())
        metadata = _make_metadata()
        frame = pipeline.capture_frame(metadata)
        pipeline.queue_upload(frame)

        assert pipeline.get_pending_count() == 1

    def test_after_processing(self):
        pipeline = ImagePipeline(_make_settings())
        metadata = _make_metadata()
        frame = pipeline.capture_frame(metadata)
        pipeline.queue_upload(frame)
        pipeline.process_upload_queue()

        assert pipeline.get_pending_count() == 0


class TestGenerateImageKey:
    def test_key_format(self):
        pipeline = ImagePipeline(_make_settings())
        metadata = _make_metadata(
            drone_id="drone-alpha",
            mission_id="mission-beta",
            capture_time=datetime(2025, 6, 15, 12, 30, 45, 123456),
        )

        key = pipeline._generate_image_key(metadata)

        assert key.startswith("images/captures/mission-beta/drone-alpha/")
        assert key.endswith(".jpg")
        assert "20250615_123045_123456" in key

    def test_key_includes_mission_id(self):
        pipeline = ImagePipeline(_make_settings())
        metadata = _make_metadata(mission_id="search-42")

        key = pipeline._generate_image_key(metadata)

        assert "search-42" in key

    def test_key_includes_drone_id(self):
        pipeline = ImagePipeline(_make_settings())
        metadata = _make_metadata(drone_id="alpha-007")

        key = pipeline._generate_image_key(metadata)

        assert "alpha-007" in key

    def test_different_timestamps_produce_different_keys(self):
        pipeline = ImagePipeline(_make_settings())
        metadata1 = _make_metadata(capture_time=datetime(2025, 6, 15, 12, 0, 0))
        metadata2 = _make_metadata(capture_time=datetime(2025, 6, 15, 12, 0, 1))

        key1 = pipeline._generate_image_key(metadata1)
        key2 = pipeline._generate_image_key(metadata2)

        assert key1 != key2


class TestCompressImage:
    def test_placeholder_returns_same_data(self):
        pipeline = ImagePipeline(_make_settings())
        data = b"fake image data"

        result = pipeline._compress_image(data, quality=85)

        assert result == data


class TestAttemptUpload:
    def test_placeholder_returns_true(self):
        pipeline = ImagePipeline(_make_settings())
        metadata = _make_metadata()
        frame = pipeline.capture_frame(metadata)
        request = UploadRequest(
            frame_id=frame.frame_id,
            image_key=frame.image_key,
            metadata=metadata,
        )

        result = pipeline._attempt_upload(request)

        assert result is True
