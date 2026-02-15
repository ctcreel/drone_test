"""Tests for drone registrar Lambda handler."""

import json
from typing import Any
from unittest.mock import MagicMock

import boto3
import pytest
from moto import mock_aws

from src.fleet.models import Drone, DroneStatus
from src.fleet.repository import DroneRepository
from src.handlers.drone_registrar import handler
from src.utils.dynamodb import DynamoDBClient


def _make_context() -> MagicMock:
    context = MagicMock()
    context.aws_request_id = "test-request-id"
    return context


def _make_event(
    *,
    resource: str = "/api/v1/drones",
    http_method: str = "GET",
    path_parameters: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    event: dict[str, Any] = {
        "resource": resource,
        "httpMethod": http_method,
        "pathParameters": path_parameters,
    }
    if body is not None:
        event["body"] = json.dumps(body)
    return event


@pytest.fixture()
def _mock_dynamodb(monkeypatch):
    """Set up mock DynamoDB."""
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
            iot_thing_name="drone-fleet-d-001",
            status=DroneStatus.AVAILABLE,
        ))
        yield


@pytest.mark.usefixtures("_mock_dynamodb")
class TestListDrones:
    """Tests for GET /api/v1/drones."""

    def test_list_drones(self) -> None:
        result = handler(_make_event(), _make_context())
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert len(body["drones"]) == 1


@pytest.mark.usefixtures("_mock_dynamodb")
class TestRegisterDrone:
    """Tests for POST /api/v1/drones."""

    def test_register_drone(self) -> None:
        event = _make_event(
            http_method="POST",
            body={"name": "Beta"},
        )
        result = handler(event, _make_context())
        assert result["statusCode"] == 201
        body = json.loads(result["body"])
        assert body["name"] == "Beta"
        assert body["status"] == "registered"

    def test_register_drone_missing_body(self) -> None:
        event = _make_event(http_method="POST")
        result = handler(event, _make_context())
        assert result["statusCode"] == 400


@pytest.mark.usefixtures("_mock_dynamodb")
class TestGetDrone:
    """Tests for GET /api/v1/drones/{drone_id}."""

    def test_get_existing_drone(self) -> None:
        event = _make_event(
            resource="/api/v1/drones/{drone_id}",
            path_parameters={"drone_id": "d-001"},
        )
        result = handler(event, _make_context())
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["drone_id"] == "d-001"

    def test_get_missing_drone(self) -> None:
        event = _make_event(
            resource="/api/v1/drones/{drone_id}",
            path_parameters={"drone_id": "nonexistent"},
        )
        result = handler(event, _make_context())
        assert result["statusCode"] == 404
