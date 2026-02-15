"""Tests for mission planner Lambda handler."""

import json
from io import BytesIO
from typing import Any
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws

from src.handlers.mission_planner import handler


def _make_context() -> MagicMock:
    context = MagicMock()
    context.aws_request_id = "test-request-id"
    context.function_name = "test-function"
    context.function_version = "$LATEST"
    return context


def _make_plan_response() -> dict[str, Any]:
    plan = {
        "search_pattern": "parallel_tracks",
        "reasoning": "Test reasoning",
        "drone_assignments": [],
        "estimated_duration_seconds": 600,
        "estimated_coverage_percent": 95.0,
        "safety_notes": [],
    }
    body_content = json.dumps({
        "content": [{"text": json.dumps(plan)}],
    }).encode()
    return {"body": BytesIO(body_content)}


def _make_event(body: dict[str, Any] | None = None) -> dict[str, Any]:
    if body is None:
        body = {
            "objective": "Search for missing person",
            "search_area": {
                "coordinates": [[
                    {"latitude": 40.0, "longitude": -74.0},
                    {"latitude": 40.1, "longitude": -74.0},
                    {"latitude": 40.1, "longitude": -73.9},
                    {"latitude": 40.0, "longitude": -74.0},
                ]],
            },
            "environment_id": "env-001",
        }
    return {
        "body": json.dumps(body),
        "requestContext": {
            "authorizer": {
                "claims": {"sub": "user-001"},
            },
        },
    }


@pytest.fixture()
def _mock_aws(monkeypatch):
    """Set up mock AWS services for planner handler."""
    with mock_aws():
        monkeypatch.setenv("TABLE_NAME", "test-table")
        monkeypatch.setenv("BUCKET_NAME", "test-bucket")

        # DynamoDB
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

        # S3
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="test-bucket")

        # Seed environment data in S3
        env_data = {
            "environment_id": "env-001",
            "name": "Test Area",
            "bounds": [[40.0, -74.0], [40.1, -73.9]],
            "building_footprints": [],
            "obstacle_zones": [],
            "no_fly_zones": [],
        }
        s3.put_object(
            Bucket="test-bucket",
            Key="environments/env-001/model.json",
            Body=json.dumps(env_data),
            ContentType="application/json",
        )

        yield


@pytest.mark.usefixtures("_mock_aws")
class TestMissionPlannerHandler:
    """Tests for the mission planner handler."""

    @patch("src.mission.planner.boto3")
    def test_successful_mission_creation(
        self, mock_planner_boto3: MagicMock,
    ) -> None:
        mock_client = MagicMock()
        mock_planner_boto3.client.return_value = mock_client
        mock_client.invoke_model.return_value = _make_plan_response()

        result = handler(_make_event(), _make_context())
        assert result["statusCode"] == 201
        body = json.loads(result["body"])
        assert body["status"] == "planned"
        assert body["plan"] is not None
        assert body["operator_id"] == "user-001"

    def test_missing_body_returns_400(self) -> None:
        event: dict[str, Any] = {"body": None}
        result = handler(event, _make_context())
        assert result["statusCode"] == 400

    def test_invalid_json_body_returns_400(self) -> None:
        event = {"body": "not json{{{"}
        result = handler(event, _make_context())
        assert result["statusCode"] == 400

    def test_invalid_objective_returns_400(self) -> None:
        event = _make_event(body={
            "objective": "",
            "search_area": {"coordinates": []},
            "environment_id": "",
        })
        result = handler(event, _make_context())
        assert result["statusCode"] == 400

    def test_missing_environment_returns_404(self) -> None:
        event = _make_event(body={
            "objective": "Search mission",
            "search_area": {
                "coordinates": [[
                    {"latitude": 40.0, "longitude": -74.0},
                    {"latitude": 40.1, "longitude": -74.0},
                    {"latitude": 40.1, "longitude": -73.9},
                    {"latitude": 40.0, "longitude": -74.0},
                ]],
            },
            "environment_id": "nonexistent",
        })
        result = handler(event, _make_context())
        assert result["statusCode"] == 404

    def test_extracts_operator_id_from_claims(self) -> None:
        event = _make_event()
        event["requestContext"]["authorizer"]["claims"]["sub"] = "op-123"

        with patch("src.mission.planner.boto3") as mock_boto3:
            mock_client = MagicMock()
            mock_boto3.client.return_value = mock_client
            mock_client.invoke_model.return_value = _make_plan_response()

            result = handler(event, _make_context())
            body = json.loads(result["body"])
            assert body["operator_id"] == "op-123"

    def test_missing_claims_uses_empty_operator(self) -> None:
        event = _make_event()
        event["requestContext"] = {}

        with patch("src.mission.planner.boto3") as mock_boto3:
            mock_client = MagicMock()
            mock_boto3.client.return_value = mock_client
            mock_client.invoke_model.return_value = _make_plan_response()

            result = handler(event, _make_context())
            body = json.loads(result["body"])
            assert body["operator_id"] == ""
