"""Image capture and upload pipeline.

Captures image frames with metadata, queues them for upload to S3 via
MQTT, and processes the upload queue with retry logic. All operations
are deterministic and suitable for edge deployment.
"""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING

from edge.image_pipeline.models import CapturedFrame, UploadRequest, UploadStatus

if TYPE_CHECKING:
    from edge.config import EdgeSettings
    from edge.image_pipeline.models import ImageMetadata

logger = logging.getLogger(__name__)

_MAX_RETRY_COUNT: int = 3
_IMAGE_FILE_EXTENSION: str = ".jpg"
_TIMESTAMP_FORMAT: str = "%Y%m%d_%H%M%S_%f"


class ImagePipeline:
    """Image capture, queueing, and upload pipeline.

    Manages the lifecycle of captured images from the drone camera:
    frame capture with metadata, upload queueing, and processing
    the upload queue with retry logic. Images are uploaded via MQTT
    signaling to trigger cloud-side S3 ingestion.
    """

    def __init__(self, settings: EdgeSettings) -> None:
        """Initialize the image pipeline.

        Args:
            settings: Edge tier configuration with image settings.
        """
        self._compression_quality = settings.image_compression_quality
        self._upload_queue: list[UploadRequest] = []
        self._completed_uploads: list[str] = []
        self._failed_uploads: list[str] = []

    def capture_frame(self, metadata: ImageMetadata) -> CapturedFrame:
        """Capture a frame and generate its storage key.

        Creates a CapturedFrame with a unique identifier and a deterministic
        S3 key based on the mission, drone, and timestamp.

        Args:
            metadata: Metadata for the captured image including position.

        Returns:
            A CapturedFrame ready for upload queueing.
        """
        frame_id = str(uuid.uuid4())
        image_key = self._generate_image_key(metadata=metadata)

        frame = CapturedFrame(
            frame_id=frame_id,
            image_key=image_key,
            metadata=metadata,
            size_bytes=0,
            compression_quality=self._compression_quality,
        )

        logger.info(
            "Captured frame %s (key=%s, lat=%.7f, lon=%.7f)",
            frame_id,
            image_key,
            metadata.latitude,
            metadata.longitude,
        )

        return frame

    def queue_upload(self, frame: CapturedFrame) -> UploadRequest:
        """Add a captured frame to the upload queue.

        Args:
            frame: Captured frame to queue for upload.

        Returns:
            The created upload request.
        """
        upload_request = UploadRequest(
            frame_id=frame.frame_id,
            image_key=frame.image_key,
            metadata=frame.metadata,
            status=UploadStatus.PENDING,
            retry_count=0,
        )

        self._upload_queue.append(upload_request)

        logger.info(
            "Queued upload for frame %s (queue_size=%d)",
            frame.frame_id,
            len(self._upload_queue),
        )

        return upload_request

    def process_upload_queue(self) -> list[UploadRequest]:
        """Process all pending uploads in the queue.

        Iterates through pending upload requests and attempts to process
        each one. Failed uploads are retried up to the maximum retry count
        before being marked as permanently failed.

        Returns:
            List of upload requests that were processed in this batch.
        """
        if not self._upload_queue:
            return []

        processed: list[UploadRequest] = []
        remaining: list[UploadRequest] = []

        for request in self._upload_queue:
            if request.status == UploadStatus.UPLOADED:
                self._completed_uploads.append(request.frame_id)
                processed.append(request)
                continue

            if request.status == UploadStatus.FAILED:
                self._failed_uploads.append(request.frame_id)
                processed.append(request)
                continue

            # Attempt to process pending requests
            request.status = UploadStatus.UPLOADING
            upload_succeeded = self._attempt_upload(request=request)

            if upload_succeeded:
                request.status = UploadStatus.UPLOADED
                self._completed_uploads.append(request.frame_id)
                processed.append(request)
                logger.info("Upload completed for frame %s", request.frame_id)
            elif request.retry_count >= _MAX_RETRY_COUNT:
                request.status = UploadStatus.FAILED
                self._failed_uploads.append(request.frame_id)
                processed.append(request)
                logger.warning(
                    "Upload permanently failed for frame %s after %d retries",
                    request.frame_id,
                    request.retry_count,
                )
            else:
                request.retry_count += 1
                request.status = UploadStatus.PENDING
                remaining.append(request)
                logger.warning(
                    "Upload failed for frame %s, retry %d/%d",
                    request.frame_id,
                    request.retry_count,
                    _MAX_RETRY_COUNT,
                )

        self._upload_queue = remaining

        logger.info(
            "Processed %d uploads, %d remaining in queue",
            len(processed),
            len(remaining),
        )

        return processed

    def get_pending_count(self) -> int:
        """Return the number of pending uploads in the queue.

        Returns:
            Number of upload requests still in the queue.
        """
        return len(self._upload_queue)

    def _generate_image_key(self, metadata: ImageMetadata) -> str:
        """Generate an S3-compatible storage key for an image.

        Key format: images/captures/{mission_id}/{drone_id}/{timestamp}.jpg

        Args:
            metadata: Image metadata with mission and drone identifiers.

        Returns:
            S3 key string for the image.
        """
        timestamp = metadata.capture_time.strftime(_TIMESTAMP_FORMAT)
        return (
            f"images/captures/{metadata.mission_id}/"
            f"{metadata.drone_id}/{timestamp}{_IMAGE_FILE_EXTENSION}"
        )

    def _compress_image(self, data: bytes, quality: int) -> bytes:
        """Compress image data at the specified quality level.

        This is a placeholder for actual JPEG compression logic that
        would use Pillow or a similar library on the Jetson.

        Args:
            data: Raw image data bytes.
            quality: JPEG compression quality (1-100).

        Returns:
            Compressed image data bytes.
        """
        # Placeholder: actual compression would use PIL/Pillow
        logger.debug("Compressing image (%d bytes, quality=%d)", len(data), quality)
        return data

    def _attempt_upload(self, request: UploadRequest) -> bool:
        """Attempt to upload a single image.

        This method signals readiness for upload. The actual data transfer
        is handled by the cloud connector publishing metadata to MQTT,
        which triggers cloud-side S3 ingestion.

        Args:
            request: The upload request to process.

        Returns:
            True if the upload signal was sent successfully, False otherwise.
        """
        logger.debug(
            "Attempting upload for frame %s (key=%s, retry=%d)",
            request.frame_id,
            request.image_key,
            request.retry_count,
        )
        # In the integrated system, this publishes an upload-ready message
        # via the CloudConnector. For now, signal success.
        return True
