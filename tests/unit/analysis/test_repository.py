"""Tests for analysis detection repository."""

import boto3
import pytest
from moto import mock_aws

from src.analysis.models import BoundingBox, Detection, ReviewDecision
from src.analysis.repository import DetectionRepository
from src.exceptions.client_errors import NotFoundError
from src.utils.dynamodb import DynamoDBClient
from src.utils.s3 import S3Client


def _make_detection(
    mission_id: str = "m-001",
    detection_id: str = "det-001",
) -> Detection:
    return Detection(
        detection_id=detection_id,
        mission_id=mission_id,
        drone_id="d-001",
        image_key=f"images/detections/{mission_id}/{detection_id}.jpg",
        source_image_key="images/captures/m-001/d-001/img.jpg",
        label="red vehicle",
        confidence=0.87,
        bounding_box=BoundingBox(x=120, y=340, width=80, height=45),
        reasoning="Matches criteria",
        latitude=40.0,
        longitude=-74.0,
        altitude=50.0,
        heading=180.0,
        capture_time="2024-01-01T12:00:00Z",
    )


@pytest.fixture()
def detection_repo():
    """Create a detection repository with mock AWS."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        dynamodb.create_table(
            TableName="test-table",
            KeySchema=[
                {"AttributeName": "pk", "KeyType": "HASH"},
                {"AttributeName": "sk", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "pk", "AttributeType": "S"},
                {"AttributeName": "sk", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="test-bucket")

        db_client = DynamoDBClient("test-table")
        s3_client = S3Client("test-bucket")
        yield DetectionRepository(db_client, s3_client)


class TestDetectionRepositoryCreate:
    """Tests for creating detections."""

    def test_create_and_get(
        self, detection_repo: DetectionRepository,
    ) -> None:
        detection = _make_detection()
        detection_repo.create(detection)
        retrieved = detection_repo.get("m-001", "det-001")
        assert retrieved.label == "red vehicle"
        assert retrieved.confidence == 0.87

    def test_get_nonexistent_raises(
        self, detection_repo: DetectionRepository,
    ) -> None:
        with pytest.raises(NotFoundError):
            detection_repo.get("m-001", "nonexistent")


class TestDetectionRepositoryList:
    """Tests for listing detections."""

    def test_list_for_mission(
        self, detection_repo: DetectionRepository,
    ) -> None:
        for i in range(3):
            detection_repo.create(
                _make_detection(detection_id=f"det-{i:03d}"),
            )
        detections = detection_repo.list_for_mission("m-001")
        assert len(detections) == 3

    def test_list_empty_mission(
        self, detection_repo: DetectionRepository,
    ) -> None:
        detections = detection_repo.list_for_mission("m-empty")
        assert detections == []


class TestDetectionRepositoryReview:
    """Tests for reviewing detections."""

    def test_confirm_detection(
        self, detection_repo: DetectionRepository,
    ) -> None:
        detection_repo.create(_make_detection())
        review = ReviewDecision(
            decision="confirmed",
            operator_id="user-001",
        )
        updated = detection_repo.review("m-001", "det-001", review)
        assert updated.reviewed == "confirmed"
        assert updated.reviewed_by == "user-001"
        assert updated.reviewed_at != ""

    def test_dismiss_detection(
        self, detection_repo: DetectionRepository,
    ) -> None:
        detection_repo.create(_make_detection())
        review = ReviewDecision(
            decision="dismissed",
            operator_id="user-002",
            notes="False positive",
        )
        updated = detection_repo.review("m-001", "det-001", review)
        assert updated.reviewed == "dismissed"
