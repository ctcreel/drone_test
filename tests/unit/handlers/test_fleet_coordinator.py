"""Tests for fleet coordinator Lambda handler."""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import boto3
import pytest
from moto import mock_aws

from src.fleet.models import Drone, DroneHealth, DroneStatus
from src.fleet.repository import DroneRepository
from src.handlers.fleet_coordinator import handler
from src.utils.dynamodb import DynamoDBClient


def _make_context() -> MagicMock:
    context = MagicMock()
    context.aws_request_id = "test-request-id"
    return context


@pytest.fixture()
def _mock_dynamodb(monkeypatch):
    """Set up mock DynamoDB with test drones."""
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

        # Healthy active drone
        repo.create(Drone(
            drone_id="d-healthy",
            name="Healthy",
            status=DroneStatus.ACTIVE,
            health=DroneHealth(
                battery_voltage=12.0,
                battery_remaining_percent=80.0,
                estimated_flight_time_seconds=3000,
            ),
            last_seen=datetime.now(UTC).isoformat(),
        ))

        # Low battery drone
        repo.create(Drone(
            drone_id="d-low-bat",
            name="Low Battery",
            status=DroneStatus.ACTIVE,
            health=DroneHealth(
                battery_voltage=10.5,
                battery_remaining_percent=15.0,
                estimated_flight_time_seconds=300,
            ),
            last_seen=datetime.now(UTC).isoformat(),
        ))

        # Disconnected drone
        old_time = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
        repo.create(Drone(
            drone_id="d-disconnected",
            name="Disconnected",
            status=DroneStatus.ASSIGNED,
            last_seen=old_time,
        ))

        # Available drone (not checked for health)
        repo.create(Drone(
            drone_id="d-available",
            name="Available",
            status=DroneStatus.AVAILABLE,
        ))

        yield


@pytest.mark.usefixtures("_mock_dynamodb")
class TestFleetCoordinator:
    """Tests for fleet coordinator handler."""

    def test_coordinator_returns_fleet_state(self) -> None:
        result = handler({}, _make_context())
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert "fleet_state" in body
        assert body["fleet_state"]["total_drones"] == 4
        assert body["fleet_state"]["active_drones"] == 2
        assert body["fleet_state"]["available_drones"] == 1

    def test_detects_low_battery(self) -> None:
        result = handler({}, _make_context())
        body = json.loads(result["body"])
        battery_alerts = [
            a for a in body["alerts"] if a["type"] == "low_battery"
        ]
        assert len(battery_alerts) == 1
        assert battery_alerts[0]["drone_id"] == "d-low-bat"

    def test_detects_connection_loss(self) -> None:
        result = handler({}, _make_context())
        body = json.loads(result["body"])
        connection_alerts = [
            a for a in body["alerts"] if a["type"] == "connection_lost"
        ]
        assert len(connection_alerts) == 1
        assert connection_alerts[0]["drone_id"] == "d-disconnected"

    def test_includes_checked_at_timestamp(self) -> None:
        result = handler({}, _make_context())
        body = json.loads(result["body"])
        assert "checked_at" in body
