"""Tests for mission executor data models."""

import pytest
from pydantic import ValidationError

from edge.mission_executor.models import (
    ExecutorState,
    MissionSegment,
    Waypoint,
    WaypointProgress,
)


class TestExecutorState:
    def test_idle_value(self):
        assert ExecutorState.IDLE.value == "idle"

    def test_loading_value(self):
        assert ExecutorState.LOADING.value == "loading"

    def test_executing_value(self):
        assert ExecutorState.EXECUTING.value == "executing"

    def test_paused_value(self):
        assert ExecutorState.PAUSED.value == "paused"

    def test_completing_value(self):
        assert ExecutorState.COMPLETING.value == "completing"

    def test_completed_value(self):
        assert ExecutorState.COMPLETED.value == "completed"

    def test_aborted_value(self):
        assert ExecutorState.ABORTED.value == "aborted"

    def test_all_states_count(self):
        assert len(ExecutorState) == 7

    def test_values_are_lowercase(self):
        for state in ExecutorState:
            assert state.value == state.value.lower()

    def test_is_string_enum(self):
        assert isinstance(ExecutorState.IDLE, str)
        assert ExecutorState.IDLE == "idle"


class TestWaypoint:
    def test_valid_waypoint(self):
        waypoint = Waypoint(
            latitude=40.7128,
            longitude=-74.0060,
            altitude=50.0,
        )
        assert waypoint.latitude == 40.7128
        assert waypoint.longitude == -74.0060
        assert waypoint.altitude == 50.0

    def test_default_speed(self):
        waypoint = Waypoint(latitude=0, longitude=0, altitude=0)
        assert waypoint.speed == 5.0

    def test_custom_speed(self):
        waypoint = Waypoint(latitude=0, longitude=0, altitude=0, speed=10.0)
        assert waypoint.speed == 10.0

    def test_speed_minimum(self):
        waypoint = Waypoint(latitude=0, longitude=0, altitude=0, speed=0.5)
        assert waypoint.speed == 0.5

    def test_speed_maximum(self):
        waypoint = Waypoint(latitude=0, longitude=0, altitude=0, speed=20.0)
        assert waypoint.speed == 20.0

    def test_speed_below_minimum_rejected(self):
        with pytest.raises(ValidationError):
            Waypoint(latitude=0, longitude=0, altitude=0, speed=0.1)

    def test_speed_above_maximum_rejected(self):
        with pytest.raises(ValidationError):
            Waypoint(latitude=0, longitude=0, altitude=0, speed=25.0)

    def test_default_loiter_time(self):
        waypoint = Waypoint(latitude=0, longitude=0, altitude=0)
        assert waypoint.loiter_time_seconds == 0

    def test_custom_loiter_time(self):
        waypoint = Waypoint(latitude=0, longitude=0, altitude=0, loiter_time_seconds=10)
        assert waypoint.loiter_time_seconds == 10

    def test_negative_loiter_time_rejected(self):
        with pytest.raises(ValidationError):
            Waypoint(latitude=0, longitude=0, altitude=0, loiter_time_seconds=-1)

    def test_serialization_roundtrip(self):
        waypoint = Waypoint(
            latitude=40.7128,
            longitude=-74.0060,
            altitude=50.0,
            speed=8.0,
            loiter_time_seconds=5,
        )
        data = waypoint.model_dump()
        restored = Waypoint(**data)
        assert restored == waypoint


class TestMissionSegment:
    def test_valid_segment(self):
        segment = MissionSegment(
            segment_id="seg-001",
            mission_id="mission-001",
            waypoints=[
                Waypoint(latitude=40.0, longitude=-74.0, altitude=50.0),
                Waypoint(latitude=40.1, longitude=-74.1, altitude=50.0),
            ],
        )
        assert segment.segment_id == "seg-001"
        assert segment.mission_id == "mission-001"
        assert len(segment.waypoints) == 2

    def test_default_capture_images(self):
        segment = MissionSegment(
            segment_id="seg-001",
            mission_id="mission-001",
            waypoints=[Waypoint(latitude=0, longitude=0, altitude=0)],
        )
        assert segment.capture_images is True

    def test_capture_images_disabled(self):
        segment = MissionSegment(
            segment_id="seg-001",
            mission_id="mission-001",
            waypoints=[Waypoint(latitude=0, longitude=0, altitude=0)],
            capture_images=False,
        )
        assert segment.capture_images is False

    def test_empty_waypoints_allowed_by_model(self):
        # The model itself allows empty waypoints; the executor validates this
        segment = MissionSegment(
            segment_id="seg-001",
            mission_id="mission-001",
            waypoints=[],
        )
        assert len(segment.waypoints) == 0

    def test_serialization_roundtrip(self):
        segment = MissionSegment(
            segment_id="seg-002",
            mission_id="mission-002",
            waypoints=[
                Waypoint(latitude=40.0, longitude=-74.0, altitude=50.0),
            ],
            capture_images=False,
        )
        data = segment.model_dump()
        restored = MissionSegment(**data)
        assert restored == segment


class TestWaypointProgress:
    def test_valid_progress(self):
        progress = WaypointProgress(
            segment_id="seg-001",
            current_waypoint_index=2,
            total_waypoints=5,
            distance_to_next_meters=150.0,
            estimated_time_remaining_seconds=90.0,
        )
        assert progress.segment_id == "seg-001"
        assert progress.current_waypoint_index == 2
        assert progress.total_waypoints == 5
        assert progress.distance_to_next_meters == 150.0
        assert progress.estimated_time_remaining_seconds == 90.0

    def test_default_values(self):
        progress = WaypointProgress(
            segment_id="seg-001",
            total_waypoints=3,
        )
        assert progress.current_waypoint_index == 0
        assert progress.distance_to_next_meters == 0.0
        assert progress.estimated_time_remaining_seconds == 0.0

    def test_current_waypoint_index_minimum(self):
        progress = WaypointProgress(
            segment_id="seg-001",
            current_waypoint_index=0,
            total_waypoints=1,
        )
        assert progress.current_waypoint_index == 0

    def test_current_waypoint_index_negative_rejected(self):
        with pytest.raises(ValidationError):
            WaypointProgress(
                segment_id="seg-001",
                current_waypoint_index=-1,
                total_waypoints=5,
            )

    def test_total_waypoints_minimum(self):
        progress = WaypointProgress(
            segment_id="seg-001",
            total_waypoints=1,
        )
        assert progress.total_waypoints == 1

    def test_total_waypoints_zero_rejected(self):
        with pytest.raises(ValidationError):
            WaypointProgress(
                segment_id="seg-001",
                total_waypoints=0,
            )

    def test_distance_to_next_negative_rejected(self):
        with pytest.raises(ValidationError):
            WaypointProgress(
                segment_id="seg-001",
                total_waypoints=3,
                distance_to_next_meters=-1.0,
            )

    def test_estimated_time_negative_rejected(self):
        with pytest.raises(ValidationError):
            WaypointProgress(
                segment_id="seg-001",
                total_waypoints=3,
                estimated_time_remaining_seconds=-1.0,
            )

    def test_serialization_roundtrip(self):
        progress = WaypointProgress(
            segment_id="seg-001",
            current_waypoint_index=2,
            total_waypoints=5,
            distance_to_next_meters=100.0,
            estimated_time_remaining_seconds=60.0,
        )
        data = progress.model_dump()
        restored = WaypointProgress(**data)
        assert restored == progress
