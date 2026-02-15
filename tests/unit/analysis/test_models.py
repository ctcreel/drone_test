"""Tests for analysis domain models."""

import pytest
from pydantic import ValidationError

from src.analysis.models import (
    AnalysisResult,
    BoundingBox,
    CapturedImage,
    Detection,
    DetectionItem,
    ReviewDecision,
)


class TestBoundingBox:
    """Tests for BoundingBox model."""

    def test_valid_box(self) -> None:
        box = BoundingBox(x=100, y=200, width=50, height=30)
        assert box.x == 100

    def test_invalid_width(self) -> None:
        with pytest.raises(ValidationError):
            BoundingBox(x=0, y=0, width=0, height=1)


class TestDetectionItem:
    """Tests for DetectionItem model."""

    def test_valid_detection(self) -> None:
        item = DetectionItem(
            label="red vehicle",
            confidence=0.87,
            bounding_box=BoundingBox(x=120, y=340, width=80, height=45),
            reasoning="Matches search criteria",
        )
        assert item.label == "red vehicle"


class TestAnalysisResult:
    """Tests for AnalysisResult model."""

    def test_empty_result(self) -> None:
        result = AnalysisResult()
        assert result.detections == []
        assert not result.search_relevant

    def test_with_detections(self) -> None:
        result = AnalysisResult(
            detections=[
                DetectionItem(
                    label="person",
                    confidence=0.92,
                    bounding_box=BoundingBox(x=10, y=20, width=30, height=60),
                    reasoning="Standing figure visible",
                ),
            ],
            scene_description="Forest clearing",
            search_relevant=True,
        )
        assert len(result.detections) == 1
        assert result.search_relevant


class TestCapturedImage:
    """Tests for CapturedImage model."""

    def test_valid_image(self) -> None:
        image = CapturedImage(
            mission_id="m-001",
            drone_id="d-001",
            image_key="images/captures/m-001/d-001/img.jpg",
            latitude=40.0,
            longitude=-74.0,
            altitude=50.0,
            heading=180.0,
            capture_time="2024-01-01T12:00:00Z",
        )
        assert image.image_key.startswith("images/")


class TestReviewDecision:
    """Tests for ReviewDecision model."""

    def test_confirmed(self) -> None:
        review = ReviewDecision(
            decision="confirmed",
            operator_id="user-001",
        )
        assert review.decision == "confirmed"

    def test_dismissed(self) -> None:
        review = ReviewDecision(
            decision="dismissed",
            operator_id="user-002",
            notes="False positive",
        )
        assert review.notes == "False positive"

    def test_invalid_decision(self) -> None:
        with pytest.raises(ValidationError):
            ReviewDecision(
                decision="maybe",
                operator_id="user-001",
            )


class TestDetection:
    """Tests for Detection model."""

    def _make_detection(self, detection_id: str = "det-001") -> Detection:
        return Detection(
            detection_id=detection_id,
            mission_id="m-001",
            drone_id="d-001",
            image_key=f"images/detections/m-001/{detection_id}.jpg",
            source_image_key="images/captures/m-001/d-001/img.jpg",
            label="red vehicle",
            confidence=0.87,
            bounding_box=BoundingBox(x=120, y=340, width=80, height=45),
            reasoning="Matches search criteria",
            latitude=40.0,
            longitude=-74.0,
            altitude=50.0,
            heading=180.0,
            capture_time="2024-01-01T12:00:00Z",
        )

    def test_create_detection(self) -> None:
        detection = self._make_detection()
        assert detection.reviewed == "pending"
        assert detection.reviewed_by == ""

    def test_to_dynamodb_item(self) -> None:
        detection = self._make_detection()
        item = detection.to_dynamodb_item()
        assert item["pk"] == "MISSION#m-001"
        assert item["sk"] == "DETECTION#det-001"
        assert item["confidence"] == 0.87

    def test_from_dynamodb_item_roundtrip(self) -> None:
        detection = self._make_detection("det-round")
        item = detection.to_dynamodb_item()
        restored = Detection.from_dynamodb_item(item)
        assert restored.detection_id == "det-round"
        assert restored.label == "red vehicle"
        assert restored.bounding_box.width == 80
