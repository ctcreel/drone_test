"""Tests for telemetry processor Lambda handler."""

import json
from unittest.mock import MagicMock

import boto3
import pytest
from moto import mock_aws

from src.fleet.models import Drone, DroneStatus
from src.fleet.repository import DroneRepository
from src.handlers.telemetry_processor import handler
from src.utils.dynamodb import DynamoDBClient


def _make_context() -> MagicMock:
    context = MagicMock()
    context.aws_request_id = "test-request-id"
    return context


@pytest.fixture()
def _mock_dynamodb(monkeypatch):
    """Set up mock DynamoDB with a registered drone."""
    with mock_aws():
        monkeypatch.setenv("TABLE_NAME", "test-table")

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

        db_client = DynamoDBClient("test-table")
        repo = DroneRepository(db_client)
        repo.create(Drone(
            drone_id="d-001",
            name="Alpha",
            status=DroneStatus.ACTIVE,
        ))
        yield


@pytest.mark.usefixtures("_mock_dynamodb")
class TestPositionTelemetry:
    """Tests for position telemetry processing."""

    def test_process_position(self) -> None:
        event = {
            "drone_id": "d-001",
            "message_type": "position_report",
            "timestamp": "2024-01-01T12:00:00Z",
            "payload": {
                "latitude": 40.7128,
                "longitude": -74.0060,
                "altitude": 50.0,
                "heading": 180.0,
                "speed": 5.0,
            },
        }
        result = handler(event, _make_context())
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["processed"] is True
        assert body["type"] == "position"


@pytest.mark.usefixtures("_mock_dynamodb")
class TestBatteryTelemetry:
    """Tests for battery telemetry processing."""

    def test_process_battery(self) -> None:
        event = {
            "drone_id": "d-001",
            "message_type": "battery_report",
            "timestamp": "2024-01-01T12:00:00Z",
            "payload": {
                "voltage": 11.8,
                "battery_remaining_percent": 72.0,
                "estimated_flight_time_seconds": 1800,
            },
        }
        result = handler(event, _make_context())
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["processed"] is True
        assert body["type"] == "battery"


@pytest.mark.usefixtures("_mock_dynamodb")
class TestObstacleTelemetry:
    """Tests for obstacle event processing."""

    def test_process_obstacle(self) -> None:
        event = {
            "drone_id": "d-001",
            "message_type": "obstacle_event",
            "timestamp": "2024-01-01T12:00:00Z",
            "payload": {
                "obstacle_type": "building",
                "distance_meters": 5.0,
                "avoidance_action": "altitude_increase",
            },
        }
        result = handler(event, _make_context())
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["processed"] is True
        assert body["type"] == "obstacle"


@pytest.mark.usefixtures("_mock_dynamodb")
class TestEdgeCases:
    """Tests for telemetry edge cases."""

    def test_missing_drone_id(self) -> None:
        event = {
            "message_type": "position_report",
            "payload": {},
        }
        result = handler(event, _make_context())
        body = json.loads(result["body"])
        assert body["processed"] is False

    def test_unknown_message_type(self) -> None:
        event = {
            "drone_id": "d-001",
            "message_type": "custom_event",
            "timestamp": "2024-01-01T12:00:00Z",
            "payload": {},
        }
        result = handler(event, _make_context())
        body = json.loads(result["body"])
        assert body["processed"] is False
        assert "unknown type" in body["reason"]
