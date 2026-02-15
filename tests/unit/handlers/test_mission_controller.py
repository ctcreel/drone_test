"""Tests for mission controller Lambda handler."""

import json
from typing import Any
from unittest.mock import MagicMock

import boto3
import pytest
from moto import mock_aws

from src.handlers.mission_controller import handler
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
    context.function_name = "test-function"
    context.function_version = "$LATEST"
    return context


def _make_objective() -> MissionObjective:
    return MissionObjective(
        description="Test search",
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


def _make_event(
    *,
    resource: str = "/api/v1/missions",
    http_method: str = "GET",
    path_parameters: dict[str, str] | None = None,
    query_parameters: dict[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "resource": resource,
        "httpMethod": http_method,
        "pathParameters": path_parameters,
        "queryStringParameters": query_parameters,
    }


@pytest.fixture()
def _mock_dynamodb(monkeypatch):
    """Set up mock DynamoDB and TABLE_NAME env var."""
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

        # Seed test data
        db_client = DynamoDBClient("test-table")
        repo = MissionRepository(db_client)
        repo.create(Mission(
            mission_id="m-001",
            objective=_make_objective(),
            operator_id="user-001",
        ))
        repo.create(Mission(
            mission_id="m-002",
            objective=_make_objective(),
            status=MissionStatus.PLANNED,
        ))

        yield


@pytest.mark.usefixtures("_mock_dynamodb")
class TestListMissions:
    """Tests for GET /api/v1/missions."""

    def test_list_all_missions(self) -> None:
        event = _make_event()
        result = handler(event, _make_context())
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert len(body["missions"]) == 2

    def test_list_missions_filtered_by_status(self) -> None:
        event = _make_event(
            query_parameters={"status": "planned"},
        )
        result = handler(event, _make_context())
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert len(body["missions"]) == 1
        assert body["missions"][0]["status"] == "planned"


@pytest.mark.usefixtures("_mock_dynamodb")
class TestGetMission:
    """Tests for GET /api/v1/missions/{mission_id}."""

    def test_get_existing_mission(self) -> None:
        event = _make_event(
            resource="/api/v1/missions/{mission_id}",
            path_parameters={"mission_id": "m-001"},
        )
        result = handler(event, _make_context())
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["mission_id"] == "m-001"

    def test_get_missing_mission_returns_404(self) -> None:
        event = _make_event(
            resource="/api/v1/missions/{mission_id}",
            path_parameters={"mission_id": "nonexistent"},
        )
        result = handler(event, _make_context())
        assert result["statusCode"] == 404

    def test_missing_path_parameter_returns_400(self) -> None:
        event = _make_event(
            resource="/api/v1/missions/{mission_id}",
        )
        result = handler(event, _make_context())
        assert result["statusCode"] == 400


@pytest.mark.usefixtures("_mock_dynamodb")
class TestApproveMission:
    """Tests for POST /api/v1/missions/{mission_id}/approve."""

    def test_approve_planned_mission(self) -> None:
        event = _make_event(
            resource="/api/v1/missions/{mission_id}/approve",
            http_method="POST",
            path_parameters={"mission_id": "m-002"},
        )
        result = handler(event, _make_context())
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["status"] == "approved"

    def test_approve_created_mission_returns_409(self) -> None:
        event = _make_event(
            resource="/api/v1/missions/{mission_id}/approve",
            http_method="POST",
            path_parameters={"mission_id": "m-001"},
        )
        result = handler(event, _make_context())
        assert result["statusCode"] == 409


@pytest.mark.usefixtures("_mock_dynamodb")
class TestAbortMission:
    """Tests for POST /api/v1/missions/{mission_id}/abort."""

    def test_abort_planned_mission(self) -> None:
        event = _make_event(
            resource="/api/v1/missions/{mission_id}/abort",
            http_method="POST",
            path_parameters={"mission_id": "m-002"},
        )
        result = handler(event, _make_context())
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["status"] == "aborted"


@pytest.mark.usefixtures("_mock_dynamodb")
class TestGetMissionStatus:
    """Tests for GET /api/v1/missions/{mission_id}/status."""

    def test_get_status(self) -> None:
        event = _make_event(
            resource="/api/v1/missions/{mission_id}/status",
            path_parameters={"mission_id": "m-001"},
        )
        result = handler(event, _make_context())
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["mission_id"] == "m-001"
        assert body["status"] == "created"


@pytest.mark.usefixtures("_mock_dynamodb")
class TestDefaultRoutes:
    """Tests for unmatched routes and test endpoints."""

    def test_test_endpoint(self) -> None:
        event = _make_event(resource="/api/v1/test/scenarios")
        result = handler(event, _make_context())
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["message"] == "test endpoint"

    def test_default_route(self) -> None:
        event = _make_event(resource="/unknown")
        result = handler(event, _make_context())
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["message"] == "mission controller"
