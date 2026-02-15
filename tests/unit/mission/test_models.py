"""Tests for mission domain models."""

import pytest
from pydantic import ValidationError

from src.mission.models import (
    VALID_TRANSITIONS,
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
    validate_transition,
)


class TestMissionStatus:
    """Tests for MissionStatus enum."""

    def test_all_statuses_exist(self) -> None:
        assert len(MissionStatus) == 6

    def test_values_are_lowercase(self) -> None:
        for status in MissionStatus:
            assert status.value == status.value.lower()


class TestCoordinate:
    """Tests for Coordinate model."""

    def test_valid_coordinate(self) -> None:
        coord = Coordinate(latitude=40.7128, longitude=-74.0060)
        assert coord.latitude == 40.7128
        assert coord.longitude == -74.0060
        assert coord.altitude == 0.0

    def test_with_altitude(self) -> None:
        coord = Coordinate(latitude=0, longitude=0, altitude=100.0)
        assert coord.altitude == 100.0

    def test_invalid_latitude(self) -> None:
        with pytest.raises(ValidationError):
            Coordinate(latitude=91, longitude=0)

    def test_invalid_longitude(self) -> None:
        with pytest.raises(ValidationError):
            Coordinate(latitude=0, longitude=181)

    def test_invalid_altitude(self) -> None:
        with pytest.raises(ValidationError):
            Coordinate(latitude=0, longitude=0, altitude=-1)


class TestWaypoint:
    """Tests for Waypoint model."""

    def test_valid_waypoint(self) -> None:
        waypoint = Waypoint(latitude=40.0, longitude=-74.0, altitude=50.0)
        assert waypoint.speed == 5.0
        assert waypoint.camera_interval_seconds == 5

    def test_custom_speed(self) -> None:
        waypoint = Waypoint(
            latitude=40.0, longitude=-74.0, altitude=50.0, speed=10.0,
        )
        assert waypoint.speed == 10.0


class TestFlightSegment:
    """Tests for FlightSegment model."""

    def test_valid_segment(self) -> None:
        segment = FlightSegment(
            waypoints=[
                Waypoint(latitude=40.0, longitude=-74.0, altitude=50.0),
            ],
            altitude=50.0,
        )
        assert len(segment.waypoints) == 1
        assert segment.camera_interval_seconds == 5


class TestDroneAssignment:
    """Tests for DroneAssignment model."""

    def test_valid_assignment(self) -> None:
        assignment = DroneAssignment(
            drone_id="drone-001",
            role="primary_search",
            segments=[
                FlightSegment(
                    waypoints=[
                        Waypoint(latitude=40.0, longitude=-74.0, altitude=50.0),
                    ],
                    altitude=50.0,
                ),
            ],
        )
        assert assignment.drone_id == "drone-001"
        assert len(assignment.segments) == 1


class TestMissionPlan:
    """Tests for MissionPlan model."""

    def test_valid_plan(self) -> None:
        plan = MissionPlan(
            search_pattern=SearchPattern.PARALLEL_TRACKS,
            reasoning="Best for open area",
            drone_assignments=[],
            estimated_duration_seconds=600,
            estimated_coverage_percent=95.0,
        )
        assert plan.search_pattern == SearchPattern.PARALLEL_TRACKS
        assert plan.safety_notes == []

    def test_with_safety_notes(self) -> None:
        plan = MissionPlan(
            search_pattern=SearchPattern.EXPANDING_SQUARE,
            reasoning="Urban area",
            drone_assignments=[],
            estimated_duration_seconds=1200,
            estimated_coverage_percent=80.0,
            safety_notes=["High winds expected"],
        )
        assert len(plan.safety_notes) == 1


class TestMissionObjective:
    """Tests for MissionObjective model."""

    def test_valid_objective(self) -> None:
        objective = MissionObjective(
            description="Search for missing hiker",
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
        assert objective.description == "Search for missing hiker"

    def test_empty_description_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MissionObjective(
                description="",
                search_area=SearchArea(coordinates=[]),
                environment_id="env-001",
            )

    def test_empty_environment_id_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MissionObjective(
                description="Search",
                search_area=SearchArea(coordinates=[]),
                environment_id="",
            )


def _make_objective() -> MissionObjective:
    """Create a test mission objective."""
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
    """Create a test mission plan."""
    return MissionPlan(
        search_pattern=SearchPattern.PARALLEL_TRACKS,
        reasoning="Test reasoning",
        drone_assignments=[
            DroneAssignment(
                drone_id="drone-001",
                role="primary_search",
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


class TestMission:
    """Tests for Mission model."""

    def test_create_mission(self) -> None:
        mission = Mission(
            mission_id="test-123",
            objective=_make_objective(),
        )
        assert mission.mission_id == "test-123"
        assert mission.status == MissionStatus.CREATED
        assert mission.plan is None
        assert mission.operator_id == ""
        assert mission.created_at != ""

    def test_mission_with_plan(self) -> None:
        mission = Mission(
            mission_id="test-456",
            objective=_make_objective(),
            plan=_make_plan(),
            status=MissionStatus.PLANNED,
        )
        assert mission.plan is not None
        assert mission.plan.search_pattern == SearchPattern.PARALLEL_TRACKS

    def test_to_dynamodb_item_without_plan(self) -> None:
        mission = Mission(
            mission_id="test-789",
            objective=_make_objective(),
            operator_id="user-001",
        )
        item = mission.to_dynamodb_item()
        assert item["pk"] == "MISSION#test-789"
        assert item["sk"] == "METADATA"
        assert item["status"] == MissionStatus.CREATED
        assert item["gsi1pk"] == MissionStatus.CREATED
        assert "plan" not in item

    def test_to_dynamodb_item_with_plan(self) -> None:
        mission = Mission(
            mission_id="test-plan",
            objective=_make_objective(),
            plan=_make_plan(),
            status=MissionStatus.PLANNED,
        )
        item = mission.to_dynamodb_item()
        assert "plan" in item
        assert item["plan"]["search_pattern"] == "parallel_tracks"

    def test_from_dynamodb_item(self) -> None:
        mission = Mission(
            mission_id="roundtrip",
            objective=_make_objective(),
            operator_id="user-001",
        )
        item = mission.to_dynamodb_item()
        restored = Mission.from_dynamodb_item(item)
        assert restored.mission_id == "roundtrip"
        assert restored.status == MissionStatus.CREATED
        assert restored.operator_id == "user-001"

    def test_from_dynamodb_item_with_plan(self) -> None:
        mission = Mission(
            mission_id="roundtrip-plan",
            objective=_make_objective(),
            plan=_make_plan(),
            status=MissionStatus.PLANNED,
        )
        item = mission.to_dynamodb_item()
        restored = Mission.from_dynamodb_item(item)
        assert restored.plan is not None
        assert restored.plan.search_pattern == SearchPattern.PARALLEL_TRACKS


class TestValidateTransition:
    """Tests for state transition validation."""

    def test_created_to_planned(self) -> None:
        assert validate_transition(MissionStatus.CREATED, MissionStatus.PLANNED)

    def test_planned_to_approved(self) -> None:
        assert validate_transition(MissionStatus.PLANNED, MissionStatus.APPROVED)

    def test_planned_to_aborted(self) -> None:
        assert validate_transition(MissionStatus.PLANNED, MissionStatus.ABORTED)

    def test_approved_to_executing(self) -> None:
        assert validate_transition(MissionStatus.APPROVED, MissionStatus.EXECUTING)

    def test_executing_to_completed(self) -> None:
        assert validate_transition(MissionStatus.EXECUTING, MissionStatus.COMPLETED)

    def test_executing_to_aborted(self) -> None:
        assert validate_transition(MissionStatus.EXECUTING, MissionStatus.ABORTED)

    def test_completed_cannot_transition(self) -> None:
        for status in MissionStatus:
            assert not validate_transition(MissionStatus.COMPLETED, status)

    def test_aborted_cannot_transition(self) -> None:
        for status in MissionStatus:
            assert not validate_transition(MissionStatus.ABORTED, status)

    def test_invalid_backward_transition(self) -> None:
        assert not validate_transition(MissionStatus.PLANNED, MissionStatus.CREATED)

    def test_all_statuses_in_transitions(self) -> None:
        for status in MissionStatus:
            assert status in VALID_TRANSITIONS
