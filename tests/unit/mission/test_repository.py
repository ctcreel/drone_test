"""Tests for mission repository."""

import boto3
import pytest
from moto import mock_aws

from src.exceptions.client_errors import ConflictError, NotFoundError
from src.mission.models import (
    Coordinate,
    DroneAssignment,
    FlightSegment,
    Mission,
    MissionObjective,
    MissionPlan,
    MissionStatus,
    SearchArea,
    SearchPattern,
    Waypoint,
)
from src.mission.repository import MissionRepository
from src.utils.dynamodb import DynamoDBClient


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


def _make_plan() -> MissionPlan:
    return MissionPlan(
        search_pattern=SearchPattern.PARALLEL_TRACKS,
        reasoning="Test",
        drone_assignments=[
            DroneAssignment(
                drone_id="drone-001",
                role="search",
                segments=[
                    FlightSegment(
                        waypoints=[
                            Waypoint(
                                latitude=40.0,
                                longitude=-74.0,
                                altitude=50.0,
                            ),
                        ],
                        altitude=50.0,
                    ),
                ],
            ),
        ],
        estimated_duration_seconds=600,
        estimated_coverage_percent=95.0,
    )


@pytest.fixture()
def mission_repo():
    """Create a mission repository backed by mock DynamoDB."""
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
        yield MissionRepository(db_client)


class TestMissionRepositoryCreate:
    """Tests for creating missions."""

    def test_create_and_get(self, mission_repo: MissionRepository) -> None:
        mission = Mission(
            mission_id="m-001",
            objective=_make_objective(),
            operator_id="user-001",
        )
        created = mission_repo.create(mission)
        assert created.mission_id == "m-001"

        retrieved = mission_repo.get("m-001")
        assert retrieved.mission_id == "m-001"
        assert retrieved.operator_id == "user-001"
        assert retrieved.status == MissionStatus.CREATED

    def test_get_nonexistent_raises(self, mission_repo: MissionRepository) -> None:
        with pytest.raises(NotFoundError):
            mission_repo.get("nonexistent")


class TestMissionRepositoryUpdateStatus:
    """Tests for status updates."""

    def test_valid_transition(self, mission_repo: MissionRepository) -> None:
        mission = Mission(
            mission_id="m-status",
            objective=_make_objective(),
            status=MissionStatus.PLANNED,
        )
        mission_repo.create(mission)

        updated = mission_repo.update_status("m-status", MissionStatus.APPROVED)
        assert updated.status == MissionStatus.APPROVED

    def test_invalid_transition_raises(self, mission_repo: MissionRepository) -> None:
        mission = Mission(
            mission_id="m-invalid",
            objective=_make_objective(),
            status=MissionStatus.CREATED,
        )
        mission_repo.create(mission)

        with pytest.raises(ConflictError):
            mission_repo.update_status("m-invalid", MissionStatus.APPROVED)


class TestMissionRepositoryUpdatePlan:
    """Tests for plan updates."""

    def test_update_plan(self, mission_repo: MissionRepository) -> None:
        mission = Mission(
            mission_id="m-plan",
            objective=_make_objective(),
        )
        mission_repo.create(mission)

        plan = _make_plan()
        updated = mission_repo.update_plan("m-plan", plan)
        assert updated.status == MissionStatus.PLANNED
        assert updated.plan is not None
        assert updated.plan.search_pattern == SearchPattern.PARALLEL_TRACKS


class TestMissionRepositoryList:
    """Tests for listing missions."""

    def test_list_by_status(self, mission_repo: MissionRepository) -> None:
        for i in range(3):
            mission = Mission(
                mission_id=f"m-list-{i}",
                objective=_make_objective(),
                status=MissionStatus.PLANNED,
            )
            mission_repo.create(mission)

        missions = mission_repo.list_by_status(MissionStatus.PLANNED)
        assert len(missions) == 3

    def test_list_by_status_empty(self, mission_repo: MissionRepository) -> None:
        missions = mission_repo.list_by_status(MissionStatus.EXECUTING)
        assert missions == []

    def test_list_all(self, mission_repo: MissionRepository) -> None:
        mission_repo.create(Mission(
            mission_id="m-all-1",
            objective=_make_objective(),
            status=MissionStatus.CREATED,
        ))
        mission_repo.create(Mission(
            mission_id="m-all-2",
            objective=_make_objective(),
            status=MissionStatus.PLANNED,
        ))

        missions = mission_repo.list_all()
        assert len(missions) == 2

    def test_list_all_respects_limit(self, mission_repo: MissionRepository) -> None:
        for i in range(5):
            mission_repo.create(Mission(
                mission_id=f"m-lim-{i}",
                objective=_make_objective(),
            ))
        missions = mission_repo.list_all(limit=3)
        assert len(missions) == 3
