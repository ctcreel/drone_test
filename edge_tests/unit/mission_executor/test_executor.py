"""Tests for MissionExecutor with mocked bridge."""

from unittest.mock import MagicMock, patch

import pytest

from edge.config import EdgeSettings
from edge.mission_executor.executor import MissionExecutor, _haversine_distance
from edge.mission_executor.models import (
    ExecutorState,
    MissionSegment,
    Waypoint,
    WaypointProgress,
)


def _make_settings(**overrides):
    """Create EdgeSettings for testing."""
    defaults = {"drone_id": "drone-test"}
    defaults.update(overrides)
    return EdgeSettings(**defaults)


def _make_bridge():
    """Create a MagicMock bridge."""
    bridge = MagicMock()
    bridge.goto = MagicMock()
    bridge.set_mode = MagicMock()
    bridge.get_telemetry = MagicMock()
    return bridge


def _make_segment(
    segment_id="seg-001",
    mission_id="mission-001",
    waypoint_count=3,
):
    """Create a MissionSegment with the given number of waypoints."""
    waypoints = [
        Waypoint(
            latitude=40.0 + i * 0.001,
            longitude=-74.0 + i * 0.001,
            altitude=50.0,
        )
        for i in range(waypoint_count)
    ]
    return MissionSegment(
        segment_id=segment_id,
        mission_id=mission_id,
        waypoints=waypoints,
    )


class TestMissionExecutorInit:
    def test_initial_state_is_idle(self):
        bridge = _make_bridge()
        settings = _make_settings()
        executor = MissionExecutor(bridge=bridge, settings=settings)
        assert executor.state == ExecutorState.IDLE

    def test_no_current_segment(self):
        bridge = _make_bridge()
        settings = _make_settings()
        executor = MissionExecutor(bridge=bridge, settings=settings)
        assert executor._current_segment is None

    def test_waypoint_index_starts_at_zero(self):
        bridge = _make_bridge()
        settings = _make_settings()
        executor = MissionExecutor(bridge=bridge, settings=settings)
        assert executor._current_waypoint_index == 0


class TestMissionExecutorLoadSegment:
    def test_load_segment_from_idle(self):
        bridge = _make_bridge()
        settings = _make_settings()
        executor = MissionExecutor(bridge=bridge, settings=settings)

        segment = _make_segment()
        executor.load_segment(segment)

        assert executor.state == ExecutorState.EXECUTING
        assert executor._current_segment == segment
        assert executor._current_waypoint_index == 0

    def test_load_segment_from_completed(self):
        bridge = _make_bridge()
        settings = _make_settings()
        executor = MissionExecutor(bridge=bridge, settings=settings)
        executor._state = ExecutorState.COMPLETED

        segment = _make_segment()
        executor.load_segment(segment)

        assert executor.state == ExecutorState.EXECUTING

    def test_load_segment_from_aborted(self):
        bridge = _make_bridge()
        settings = _make_settings()
        executor = MissionExecutor(bridge=bridge, settings=settings)
        executor._state = ExecutorState.ABORTED

        segment = _make_segment()
        executor.load_segment(segment)

        assert executor.state == ExecutorState.EXECUTING

    def test_load_segment_from_executing_raises(self):
        bridge = _make_bridge()
        settings = _make_settings()
        executor = MissionExecutor(bridge=bridge, settings=settings)
        executor._state = ExecutorState.EXECUTING

        segment = _make_segment()
        with pytest.raises(RuntimeError, match="Cannot load segment"):
            executor.load_segment(segment)

    def test_load_segment_from_paused_raises(self):
        bridge = _make_bridge()
        settings = _make_settings()
        executor = MissionExecutor(bridge=bridge, settings=settings)
        executor._state = ExecutorState.PAUSED

        segment = _make_segment()
        with pytest.raises(RuntimeError, match="Cannot load segment"):
            executor.load_segment(segment)

    def test_load_segment_with_empty_waypoints_raises(self):
        bridge = _make_bridge()
        settings = _make_settings()
        executor = MissionExecutor(bridge=bridge, settings=settings)

        segment = MissionSegment(
            segment_id="seg-empty",
            mission_id="mission-001",
            waypoints=[],
        )
        with pytest.raises(ValueError, match="no waypoints"):
            executor.load_segment(segment)

    def test_load_segment_resets_waypoint_index(self):
        bridge = _make_bridge()
        settings = _make_settings()
        executor = MissionExecutor(bridge=bridge, settings=settings)

        executor._current_waypoint_index = 5
        executor._state = ExecutorState.COMPLETED

        segment = _make_segment()
        executor.load_segment(segment)

        assert executor._current_waypoint_index == 0


class TestMissionExecutorExecute:
    @patch("edge.mission_executor.executor.time")
    def test_execute_all_waypoints(self, mock_time):
        bridge = _make_bridge()
        settings = _make_settings()
        executor = MissionExecutor(bridge=bridge, settings=settings)

        # Create a telemetry that indicates arrival at each waypoint
        mock_telemetry = MagicMock()

        segment = _make_segment(waypoint_count=2)

        # Make get_telemetry return positions close to the waypoints
        call_count = 0

        def telemetry_side_effect():
            nonlocal call_count
            idx = min(call_count, len(segment.waypoints) - 1)
            mock_telemetry.latitude = segment.waypoints[idx].latitude
            mock_telemetry.longitude = segment.waypoints[idx].longitude
            call_count += 1
            return mock_telemetry

        bridge.get_telemetry.side_effect = telemetry_side_effect

        executor.load_segment(segment)
        executor.execute()

        assert executor.state == ExecutorState.COMPLETED
        assert bridge.goto.call_count == 2

    def test_execute_not_executing_raises(self):
        bridge = _make_bridge()
        settings = _make_settings()
        executor = MissionExecutor(bridge=bridge, settings=settings)

        with pytest.raises(RuntimeError, match="Cannot execute"):
            executor.execute()

    @patch("edge.mission_executor.executor.time")
    def test_execute_pauses_mid_mission(self, mock_time):
        bridge = _make_bridge()
        settings = _make_settings()
        executor = MissionExecutor(bridge=bridge, settings=settings)

        segment = _make_segment(waypoint_count=3)

        call_count = 0

        def telemetry_side_effect():
            nonlocal call_count
            mock_telemetry = MagicMock()
            idx = min(call_count, len(segment.waypoints) - 1)
            mock_telemetry.latitude = segment.waypoints[idx].latitude
            mock_telemetry.longitude = segment.waypoints[idx].longitude
            call_count += 1
            # Pause after arriving at first waypoint
            if call_count == 1:
                executor._state = ExecutorState.PAUSED
            return mock_telemetry

        bridge.get_telemetry.side_effect = telemetry_side_effect

        executor.load_segment(segment)
        executor.execute()

        assert executor.state == ExecutorState.PAUSED

    @patch("edge.mission_executor.executor.time")
    def test_execute_aborts_mid_mission(self, mock_time):
        bridge = _make_bridge()
        settings = _make_settings()
        executor = MissionExecutor(bridge=bridge, settings=settings)

        segment = _make_segment(waypoint_count=3)

        call_count = 0

        def telemetry_side_effect():
            nonlocal call_count
            mock_telemetry = MagicMock()
            idx = min(call_count, len(segment.waypoints) - 1)
            mock_telemetry.latitude = segment.waypoints[idx].latitude
            mock_telemetry.longitude = segment.waypoints[idx].longitude
            call_count += 1
            if call_count == 1:
                executor._state = ExecutorState.ABORTED
            return mock_telemetry

        bridge.get_telemetry.side_effect = telemetry_side_effect

        executor.load_segment(segment)
        executor.execute()

        assert executor.state == ExecutorState.ABORTED


class TestMissionExecutorPause:
    def test_pause_from_executing(self):
        bridge = _make_bridge()
        settings = _make_settings()
        executor = MissionExecutor(bridge=bridge, settings=settings)
        executor._state = ExecutorState.EXECUTING
        executor._current_segment = _make_segment()

        executor.pause()

        assert executor.state == ExecutorState.PAUSED
        bridge.set_mode.assert_called_once_with("LOITER")

    def test_pause_from_idle_raises(self):
        bridge = _make_bridge()
        settings = _make_settings()
        executor = MissionExecutor(bridge=bridge, settings=settings)

        with pytest.raises(RuntimeError, match="Cannot pause"):
            executor.pause()

    def test_pause_from_paused_raises(self):
        bridge = _make_bridge()
        settings = _make_settings()
        executor = MissionExecutor(bridge=bridge, settings=settings)
        executor._state = ExecutorState.PAUSED

        with pytest.raises(RuntimeError, match="Cannot pause"):
            executor.pause()


class TestMissionExecutorResume:
    def test_resume_from_paused(self):
        bridge = _make_bridge()
        settings = _make_settings()
        executor = MissionExecutor(bridge=bridge, settings=settings)
        executor._state = ExecutorState.PAUSED

        executor.resume()

        assert executor.state == ExecutorState.EXECUTING

    def test_resume_from_executing_raises(self):
        bridge = _make_bridge()
        settings = _make_settings()
        executor = MissionExecutor(bridge=bridge, settings=settings)
        executor._state = ExecutorState.EXECUTING

        with pytest.raises(RuntimeError, match="Cannot resume"):
            executor.resume()

    def test_resume_from_idle_raises(self):
        bridge = _make_bridge()
        settings = _make_settings()
        executor = MissionExecutor(bridge=bridge, settings=settings)

        with pytest.raises(RuntimeError, match="Cannot resume"):
            executor.resume()


class TestMissionExecutorAbort:
    def test_abort_from_executing(self):
        bridge = _make_bridge()
        settings = _make_settings()
        executor = MissionExecutor(bridge=bridge, settings=settings)
        executor._state = ExecutorState.EXECUTING
        executor._current_segment = _make_segment()

        executor.abort()

        assert executor.state == ExecutorState.ABORTED
        bridge.set_mode.assert_called_once_with("LOITER")

    def test_abort_from_paused(self):
        bridge = _make_bridge()
        settings = _make_settings()
        executor = MissionExecutor(bridge=bridge, settings=settings)
        executor._state = ExecutorState.PAUSED

        executor.abort()

        assert executor.state == ExecutorState.ABORTED

    def test_abort_from_idle_raises(self):
        bridge = _make_bridge()
        settings = _make_settings()
        executor = MissionExecutor(bridge=bridge, settings=settings)

        with pytest.raises(RuntimeError, match="Cannot abort"):
            executor.abort()


class TestMissionExecutorGetProgress:
    def test_get_progress_with_loaded_segment(self):
        bridge = _make_bridge()
        bridge.get_telemetry.side_effect = ConnectionError("Not connected")
        settings = _make_settings()
        executor = MissionExecutor(bridge=bridge, settings=settings)

        segment = _make_segment(waypoint_count=5)
        executor.load_segment(segment)
        executor._current_waypoint_index = 2

        progress = executor.get_progress()

        assert isinstance(progress, WaypointProgress)
        assert progress.segment_id == "seg-001"
        assert progress.current_waypoint_index == 2
        assert progress.total_waypoints == 5

    def test_get_progress_no_segment_raises(self):
        bridge = _make_bridge()
        settings = _make_settings()
        executor = MissionExecutor(bridge=bridge, settings=settings)

        with pytest.raises(RuntimeError, match="No mission segment"):
            executor.get_progress()

    def test_get_progress_estimated_time(self):
        bridge = _make_bridge()
        bridge.get_telemetry.side_effect = ConnectionError("Not connected")
        settings = _make_settings()
        executor = MissionExecutor(bridge=bridge, settings=settings)

        segment = _make_segment(waypoint_count=4)
        executor.load_segment(segment)
        executor._current_waypoint_index = 1

        progress = executor.get_progress()

        # 3 remaining waypoints * 30 seconds each = 90 seconds
        assert progress.estimated_time_remaining_seconds == 90.0

    def test_get_progress_with_telemetry(self):
        bridge = _make_bridge()
        mock_telemetry = MagicMock()
        mock_telemetry.latitude = 40.0
        mock_telemetry.longitude = -74.0
        bridge.get_telemetry.return_value = mock_telemetry

        settings = _make_settings()
        executor = MissionExecutor(bridge=bridge, settings=settings)

        segment = _make_segment(waypoint_count=3)
        executor.load_segment(segment)

        progress = executor.get_progress()

        assert progress.distance_to_next_meters >= 0.0

    def test_get_progress_at_end_of_segment(self):
        bridge = _make_bridge()
        bridge.get_telemetry.side_effect = ConnectionError("Not connected")
        settings = _make_settings()
        executor = MissionExecutor(bridge=bridge, settings=settings)

        segment = _make_segment(waypoint_count=3)
        executor.load_segment(segment)
        executor._current_waypoint_index = 3  # past all waypoints

        progress = executor.get_progress()

        assert progress.estimated_time_remaining_seconds == 0.0
        assert progress.distance_to_next_meters == 0.0


class TestHaversineDistance:
    def test_same_point_returns_zero(self):
        distance = _haversine_distance(
            latitude_1=40.7128,
            longitude_1=-74.0060,
            latitude_2=40.7128,
            longitude_2=-74.0060,
        )
        assert distance == pytest.approx(0.0, abs=0.01)

    def test_known_distance(self):
        # New York to Los Angeles (approximate)
        distance = _haversine_distance(
            latitude_1=40.7128,
            longitude_1=-74.0060,
            latitude_2=34.0522,
            longitude_2=-118.2437,
        )
        # ~3,944 km
        assert 3_900_000 < distance < 4_000_000

    def test_short_distance(self):
        # Two close points (~111 meters apart at equator)
        distance = _haversine_distance(
            latitude_1=0.0,
            longitude_1=0.0,
            latitude_2=0.001,
            longitude_2=0.0,
        )
        assert 100 < distance < 120

    def test_equator_to_pole(self):
        distance = _haversine_distance(
            latitude_1=0.0,
            longitude_1=0.0,
            latitude_2=90.0,
            longitude_2=0.0,
        )
        # ~10,000 km (quarter of Earth's circumference)
        assert 9_900_000 < distance < 10_100_000

    def test_symmetry(self):
        distance_ab = _haversine_distance(
            latitude_1=40.0, longitude_1=-74.0,
            latitude_2=41.0, longitude_2=-73.0,
        )
        distance_ba = _haversine_distance(
            latitude_1=41.0, longitude_1=-73.0,
            latitude_2=40.0, longitude_2=-74.0,
        )
        assert distance_ab == pytest.approx(distance_ba, abs=0.01)
