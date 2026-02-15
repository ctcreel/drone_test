"""Tests for image analyzer Lambda handler."""

import json
from typing import Any
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws

from src.analysis.models import AnalysisResult, BoundingBox, DetectionItem
from src.handlers.image_analyzer import handler
from src.mission.models import (
    Coordinate,
    Mission,
    MissionObjective,
    MissionStatus,
    SearchArea,
)
from src.mission.repository import MissionRepository
from src.utils.dynamodb import DynamoDBClient


def _make_context() -> MagicMock:
    context = MagicMock()
    context.aws_request_id = "test-request-id"
    return context


def _make_objective() -> MissionObjective:
    return MissionObjective(
        description="Find red vehicle",
        search_area=SearchArea(
            coordinates=[[
                Coordinate(latitude=40.0, longitude=-74.0),
                Coordinate(latitude=40.1, longitude=-74.0),
                Coordinate(latitude=40.1, longitude=-73.9),
                Coordinate(latitude=40.0, longitude=-74.0),
            ]],
        ),
        environment_id="env-001",
    )


def _make_sqs_event(
    image_key: str = "images/captures/m-001/d-001/img.jpg",
    mission_id: str = "m-001",
    drone_id: str = "d-001",
) -> dict[str, Any]:
    message = {
        "payload": {
            "image_key": image_key,
            "mission_id": mission_id,
            "drone_id": drone_id,
            "latitude": 40.0,
            "longitude": -74.0,
            "altitude": 50.0,
            "heading": 180.0,
            "capture_time": "2024-01-01T12:00:00Z",
        },
    }
    return {
        "Records": [{"body": json.dumps(message)}],
    }


@pytest.fixture()
def _mock_aws(monkeypatch):
    """Set up mock AWS services."""
    with mock_aws():
        monkeypatch.setenv("TABLE_NAME", "test-table")
        monkeypatch.setenv("BUCKET_NAME", "test-bucket")

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
                {"AttributeName": "gsi1pk", "AttributeType": "S"},
                {"AttributeName": "gsi1sk", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "gsi1-status-created",
                    "KeySchema": [
                        {"AttributeName": "gsi1pk", "KeyType": "HASH"},
                        {"AttributeName": "gsi1sk", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="test-bucket")

        # Seed mission
        db_client = DynamoDBClient("test-table")
        repo = MissionRepository(db_client)
        repo.create(Mission(
            mission_id="m-001",
            objective=_make_objective(),
            status=MissionStatus.EXECUTING,
        ))

        # Seed image in S3
        s3.put_object(
            Bucket="test-bucket",
            Key="images/captures/m-001/d-001/img.jpg",
            Body=b"fake-jpeg-content",
        )

        yield


@pytest.mark.usefixtures("_mock_aws")
class TestImageAnalyzerHandler:
    """Tests for image analyzer handler."""

    @patch("src.handlers.image_analyzer.BedrockVisionAnalyzer")
    def test_process_image_with_detections(
        self, mock_analyzer_cls: MagicMock,
    ) -> None:
        mock_analyzer = MagicMock()
        mock_analyzer_cls.return_value = mock_analyzer
        mock_analyzer.analyze_image.return_value = AnalysisResult(
            detections=[
                DetectionItem(
                    label="red sedan",
                    confidence=0.92,
                    bounding_box=BoundingBox(x=100, y=200, width=80, height=45),
                    reasoning="Matches search criteria",
                ),
            ],
            scene_description="Parking area",
            search_relevant=True,
        )

        result = handler(_make_sqs_event(), _make_context())
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["results"][0]["processed"] is True
        assert body["results"][0]["detections_found"] == 1

    @patch("src.handlers.image_analyzer.BedrockVisionAnalyzer")
    def test_process_image_no_detections(
        self, mock_analyzer_cls: MagicMock,
    ) -> None:
        mock_analyzer = MagicMock()
        mock_analyzer_cls.return_value = mock_analyzer
        mock_analyzer.analyze_image.return_value = AnalysisResult(
            scene_description="Empty field",
        )

        result = handler(_make_sqs_event(), _make_context())
        body = json.loads(result["body"])
        assert body["results"][0]["detections_found"] == 0

    @patch("src.handlers.image_analyzer.BedrockVisionAnalyzer")
    def test_low_confidence_filtered(
        self, mock_analyzer_cls: MagicMock,
    ) -> None:
        mock_analyzer = MagicMock()
        mock_analyzer_cls.return_value = mock_analyzer
        mock_analyzer.analyze_image.return_value = AnalysisResult(
            detections=[
                DetectionItem(
                    label="maybe person",
                    confidence=0.3,
                    bounding_box=BoundingBox(x=10, y=20, width=30, height=60),
                    reasoning="Low confidence",
                ),
            ],
            scene_description="Unclear scene",
            search_relevant=False,
        )

        result = handler(_make_sqs_event(), _make_context())
        body = json.loads(result["body"])
        assert body["results"][0]["detections_found"] == 0

    @patch("src.handlers.image_analyzer.BedrockVisionAnalyzer")
    def test_missing_fields_skipped(
        self, mock_analyzer_cls: MagicMock,
    ) -> None:
        event = {
            "Records": [{"body": json.dumps({"payload": {}})}],
        }
        result = handler(event, _make_context())
        body = json.loads(result["body"])
        assert body["results"][0]["processed"] is False

    def test_empty_records(self) -> None:
        event: dict[str, Any] = {"Records": []}
        result = handler(event, _make_context())
        body = json.loads(result["body"])
        assert body["results"] == []
