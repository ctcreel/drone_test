"""Image analyzer Lambda handler."""

import json
import logging
import os
import uuid
from typing import Any

import boto3

from src.analysis.analyzer import BedrockVisionAnalyzer
from src.analysis.models import Detection
from src.analysis.repository import DetectionRepository
from src.constants import MAX_IMAGE_SIZE_BYTES
from src.exceptions.handlers import create_exception_handler, create_success_response
from src.mission.repository import MissionRepository
from src.utils.dynamodb import DynamoDBClient
from src.utils.s3 import S3Client

logger = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = 0.5


def _get_clients() -> tuple[
    DynamoDBClient,
    S3Client,
    MissionRepository,
    DetectionRepository,
]:
    """Get AWS client instances."""
    table_name = os.environ["TABLE_NAME"]
    bucket_name = os.environ["BUCKET_NAME"]
    db_client = DynamoDBClient(table_name)
    s3_client = S3Client(bucket_name)
    return (
        db_client,
        s3_client,
        MissionRepository(db_client),
        DetectionRepository(db_client, s3_client),
    )


def _parse_sqs_record(record: dict[str, Any]) -> dict[str, Any]:
    """Parse an SQS record body.

    Args:
        record: SQS event record.

    Returns:
        Parsed message body.
    """
    body = record.get("body", "{}")
    parsed: dict[str, Any] = json.loads(body) if isinstance(body, str) else body
    return parsed


def _process_image(
    message: dict[str, Any],
    mission_repo: MissionRepository,
    detection_repo: DetectionRepository,
    analyzer: BedrockVisionAnalyzer,
) -> dict[str, Any]:
    """Process a single image capture message.

    Args:
        message: Parsed SQS message with image metadata.
        s3_client: S3 client for image operations.
        mission_repo: Mission repository.
        detection_repo: Detection repository.
        analyzer: Bedrock Vision analyzer.

    Returns:
        Processing result summary.
    """
    payload: dict[str, Any] = message.get("payload", message)
    image_key: str = payload.get("image_key", "")
    mission_id: str = payload.get("mission_id", "")
    drone_id: str = payload.get("drone_id", message.get("drone_id", ""))

    if not image_key or not mission_id:
        logger.warning("Image message missing required fields")
        return {"processed": False, "reason": "missing fields"}

    # Get mission objective for context
    mission = mission_repo.get(mission_id)
    objective_description = mission.objective.description

    # Download image from S3
    s3_raw = boto3.client("s3")  # type: ignore[call-overload]
    bucket_name = os.environ["BUCKET_NAME"]

    response = s3_raw.get_object(Bucket=bucket_name, Key=image_key)
    image_bytes: bytes = response["Body"].read()

    if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
        logger.warning(
            "Image too large: %d bytes (max %d)",
            len(image_bytes),
            MAX_IMAGE_SIZE_BYTES,
        )
        return {"processed": False, "reason": "image_too_large"}

    # Analyze with Bedrock Vision
    metadata = {
        "drone_id": drone_id,
        "latitude": payload.get("latitude", 0),
        "longitude": payload.get("longitude", 0),
        "altitude": payload.get("altitude", 0),
        "heading": payload.get("heading", 0),
        "capture_time": payload.get("capture_time", ""),
    }
    result = analyzer.analyze_image(image_bytes, objective_description, metadata)

    # Filter by confidence threshold
    relevant_detections = [d for d in result.detections if d.confidence >= CONFIDENCE_THRESHOLD]

    # Store each detection
    created_ids: list[str] = []
    for detection_item in relevant_detections:
        detection_id = str(uuid.uuid4())
        detection_key = f"images/detections/{mission_id}/{detection_id}.jpg"

        # Copy image to detections folder
        s3_raw.copy_object(
            Bucket=bucket_name,
            CopySource={"Bucket": bucket_name, "Key": image_key},
            Key=detection_key,
        )

        detection = Detection(
            detection_id=detection_id,
            mission_id=mission_id,
            drone_id=drone_id,
            image_key=detection_key,
            source_image_key=image_key,
            label=detection_item.label,
            confidence=detection_item.confidence,
            bounding_box=detection_item.bounding_box,
            reasoning=detection_item.reasoning,
            latitude=payload.get("latitude", 0),
            longitude=payload.get("longitude", 0),
            altitude=payload.get("altitude", 0),
            heading=payload.get("heading", 0),
            capture_time=payload.get("capture_time", ""),
        )
        detection_repo.create(detection)
        created_ids.append(detection_id)

    return {
        "processed": True,
        "image_key": image_key,
        "detections_found": len(relevant_detections),
        "detection_ids": created_ids,
        "scene_description": result.scene_description,
    }


@create_exception_handler
def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Process images from SQS queue via Bedrock Vision.

    Args:
        event: SQS event with image references.
        context: Lambda context.

    Returns:
        Processing result.
    """
    _ = context
    _, _, mission_repo, detection_repo = _get_clients()
    analyzer = BedrockVisionAnalyzer()

    records: list[dict[str, Any]] = event.get("Records", [])
    results: list[dict[str, Any]] = []

    for record in records:
        message = _parse_sqs_record(record)
        result = _process_image(
            message,
            mission_repo,
            detection_repo,
            analyzer,
        )
        results.append(result)

    return create_success_response(200, {"results": results})
