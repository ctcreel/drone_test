"""Tests for ObstacleAvoidance detection and maneuver computation."""

import pytest

from edge.config import EdgeSettings
from edge.obstacle_avoidance.avoidance import ObstacleAvoidance
from edge.obstacle_avoidance.models import (
    DepthFrame,
    ObstacleDetection,
    ObstacleSeverity,
)


def _make_settings(**overrides):
    """Create EdgeSettings for testing."""
    defaults = {
        "drone_id": "drone-test",
        "obstacle_detection_range_meters": 10.0,
        "minimum_clearance_meters": 2.0,
    }
    defaults.update(overrides)
    return EdgeSettings(**defaults)


def _make_avoidance(**overrides):
    """Create an ObstacleAvoidance instance."""
    settings = _make_settings(**overrides)
    return ObstacleAvoidance(settings)


def _make_frame(
    min_distance=3.0,
    max_distance=10.0,
    width=640,
    height=480,
    timestamp_ms=1000,
):
    """Create a DepthFrame for testing."""
    return DepthFrame(
        width=width,
        height=height,
        min_distance_meters=min_distance,
        max_distance_meters=max_distance,
        timestamp_ms=timestamp_ms,
    )


class TestObstacleAvoidanceInit:
    def test_detection_range_from_settings(self):
        avoidance = _make_avoidance(obstacle_detection_range_meters=15.0)
        assert avoidance._detection_range_meters == 15.0

    def test_minimum_clearance_from_settings(self):
        avoidance = _make_avoidance(minimum_clearance_meters=3.0)
        assert avoidance._minimum_clearance_meters == 3.0


class TestProcessDepthFrame:
    def test_no_obstacle_beyond_range(self):
        avoidance = _make_avoidance(obstacle_detection_range_meters=10.0)
        frame = _make_frame(min_distance=15.0, max_distance=20.0)

        detections = avoidance.process_depth_frame(frame)

        assert len(detections) == 0

    def test_no_obstacle_zero_distance(self):
        avoidance = _make_avoidance()
        frame = _make_frame(min_distance=0.0, max_distance=10.0)

        detections = avoidance.process_depth_frame(frame)

        assert len(detections) == 0

    def test_obstacle_within_range(self):
        avoidance = _make_avoidance(obstacle_detection_range_meters=10.0)
        frame = _make_frame(min_distance=5.0, max_distance=10.0)

        detections = avoidance.process_depth_frame(frame)

        assert len(detections) == 1
        assert detections[0].distance_meters == 5.0

    def test_critical_obstacle_detected(self):
        avoidance = _make_avoidance(obstacle_detection_range_meters=10.0)
        # Distance is 1.5m, which is 15% of 10m range -> CRITICAL (<=20%)
        frame = _make_frame(min_distance=1.5, max_distance=10.0)

        detections = avoidance.process_depth_frame(frame)

        assert len(detections) == 1
        assert detections[0].severity == ObstacleSeverity.CRITICAL

    def test_high_severity_obstacle(self):
        avoidance = _make_avoidance(obstacle_detection_range_meters=10.0)
        # Distance is 3.0m, which is 30% of 10m range -> HIGH (20%-40%)
        frame = _make_frame(min_distance=3.0, max_distance=10.0)

        detections = avoidance.process_depth_frame(frame)

        assert len(detections) == 1
        assert detections[0].severity == ObstacleSeverity.HIGH

    def test_medium_severity_obstacle(self):
        avoidance = _make_avoidance(obstacle_detection_range_meters=10.0)
        # Distance is 5.0m, which is 50% of 10m range -> MEDIUM (40%-60%)
        frame = _make_frame(min_distance=5.0, max_distance=10.0)

        detections = avoidance.process_depth_frame(frame)

        assert len(detections) == 1
        assert detections[0].severity == ObstacleSeverity.MEDIUM

    def test_low_severity_obstacle(self):
        avoidance = _make_avoidance(obstacle_detection_range_meters=10.0)
        # Distance is 7.0m, which is 70% of 10m range -> LOW (60%-80%)
        frame = _make_frame(min_distance=7.0, max_distance=10.0)

        detections = avoidance.process_depth_frame(frame)

        assert len(detections) == 1
        assert detections[0].severity == ObstacleSeverity.LOW

    def test_no_severity_at_boundary(self):
        avoidance = _make_avoidance(obstacle_detection_range_meters=10.0)
        # Distance is 9.0m, which is 90% of 10m range -> NONE (>80%)
        frame = _make_frame(min_distance=9.0, max_distance=10.0)

        detections = avoidance.process_depth_frame(frame)

        assert len(detections) == 0

    def test_detection_has_estimated_width(self):
        avoidance = _make_avoidance(obstacle_detection_range_meters=10.0)
        frame = _make_frame(min_distance=5.0, max_distance=10.0)

        detections = avoidance.process_depth_frame(frame)

        assert len(detections) == 1
        assert detections[0].width_meters > 0.0

    def test_detection_has_estimated_height(self):
        avoidance = _make_avoidance(obstacle_detection_range_meters=10.0)
        frame = _make_frame(min_distance=5.0, max_distance=10.0)

        detections = avoidance.process_depth_frame(frame)

        assert len(detections) == 1
        assert detections[0].height_meters > 0.0

    def test_height_is_three_quarters_of_width(self):
        avoidance = _make_avoidance(obstacle_detection_range_meters=10.0)
        frame = _make_frame(min_distance=5.0, max_distance=10.0)

        detections = avoidance.process_depth_frame(frame)

        assert len(detections) == 1
        assert detections[0].height_meters == pytest.approx(
            detections[0].width_meters * 0.75,
        )

    def test_bearing_is_zero_for_aggregate_frame(self):
        avoidance = _make_avoidance()
        frame = _make_frame(min_distance=5.0, max_distance=10.0)

        detections = avoidance.process_depth_frame(frame)

        assert len(detections) == 1
        assert detections[0].bearing_degrees == 0.0


class TestSeverityClassification:
    def test_critical_at_boundary(self):
        avoidance = _make_avoidance()
        result = avoidance._classify_severity(distance=2.0, detection_range=10.0)
        assert result == ObstacleSeverity.CRITICAL

    def test_high_at_boundary(self):
        avoidance = _make_avoidance()
        result = avoidance._classify_severity(distance=4.0, detection_range=10.0)
        assert result == ObstacleSeverity.HIGH

    def test_medium_at_boundary(self):
        avoidance = _make_avoidance()
        result = avoidance._classify_severity(distance=6.0, detection_range=10.0)
        assert result == ObstacleSeverity.MEDIUM

    def test_low_at_boundary(self):
        avoidance = _make_avoidance()
        result = avoidance._classify_severity(distance=8.0, detection_range=10.0)
        assert result == ObstacleSeverity.LOW

    def test_none_beyond_low(self):
        avoidance = _make_avoidance()
        result = avoidance._classify_severity(distance=9.0, detection_range=10.0)
        assert result == ObstacleSeverity.NONE

    def test_zero_detection_range_returns_none(self):
        avoidance = _make_avoidance()
        result = avoidance._classify_severity(distance=5.0, detection_range=0.0)
        assert result == ObstacleSeverity.NONE

    def test_negative_detection_range_returns_none(self):
        avoidance = _make_avoidance()
        result = avoidance._classify_severity(distance=5.0, detection_range=-1.0)
        assert result == ObstacleSeverity.NONE


class TestComputeAvoidance:
    def test_no_detections_returns_none(self):
        avoidance = _make_avoidance()

        result = avoidance.compute_avoidance([])

        assert result is None

    def test_none_severity_returns_none(self):
        avoidance = _make_avoidance()
        detection = ObstacleDetection(
            distance_meters=10.0,
            bearing_degrees=0.0,
            severity=ObstacleSeverity.NONE,
            width_meters=1.0,
            height_meters=1.0,
        )

        result = avoidance.compute_avoidance([detection])

        assert result is None

    def test_obstacle_beyond_clearance_returns_none(self):
        avoidance = _make_avoidance(minimum_clearance_meters=2.0)
        detection = ObstacleDetection(
            distance_meters=5.0,
            bearing_degrees=0.0,
            severity=ObstacleSeverity.MEDIUM,
            width_meters=1.0,
            height_meters=1.0,
        )

        result = avoidance.compute_avoidance([detection])

        assert result is None

    def test_critical_returns_hold(self):
        avoidance = _make_avoidance(minimum_clearance_meters=5.0)
        detection = ObstacleDetection(
            distance_meters=1.0,
            bearing_degrees=0.0,
            severity=ObstacleSeverity.CRITICAL,
            width_meters=1.0,
            height_meters=1.0,
        )

        result = avoidance.compute_avoidance([detection])

        assert result is not None
        assert result.maneuver_type == "hold"
        assert result.priority == 10

    def test_high_returns_climb(self):
        avoidance = _make_avoidance(minimum_clearance_meters=5.0)
        detection = ObstacleDetection(
            distance_meters=1.5,
            bearing_degrees=0.0,
            severity=ObstacleSeverity.HIGH,
            width_meters=1.0,
            height_meters=1.0,
        )

        result = avoidance.compute_avoidance([detection])

        assert result is not None
        assert result.maneuver_type == "climb"
        assert result.magnitude_meters == 5.0
        assert result.priority == 8

    def test_medium_with_right_bearing_returns_lateral_left(self):
        avoidance = _make_avoidance(minimum_clearance_meters=5.0)
        detection = ObstacleDetection(
            distance_meters=1.5,
            bearing_degrees=30.0,  # obstacle to the right
            severity=ObstacleSeverity.MEDIUM,
            width_meters=1.0,
            height_meters=1.0,
        )

        result = avoidance.compute_avoidance([detection])

        assert result is not None
        assert result.maneuver_type == "lateral_left"
        assert result.priority == 5

    def test_medium_with_left_bearing_returns_lateral_right(self):
        avoidance = _make_avoidance(minimum_clearance_meters=5.0)
        detection = ObstacleDetection(
            distance_meters=1.5,
            bearing_degrees=-30.0,  # obstacle to the left
            severity=ObstacleSeverity.MEDIUM,
            width_meters=1.0,
            height_meters=1.0,
        )

        result = avoidance.compute_avoidance([detection])

        assert result is not None
        assert result.maneuver_type == "lateral_right"

    def test_center_bearing_returns_climb(self):
        avoidance = _make_avoidance(minimum_clearance_meters=5.0)
        detection = ObstacleDetection(
            distance_meters=1.5,
            bearing_degrees=0.0,  # dead center
            severity=ObstacleSeverity.MEDIUM,
            width_meters=1.0,
            height_meters=1.0,
        )

        result = avoidance.compute_avoidance([detection])

        assert result is not None
        # Dead center obstacle defaults to climb instead of lateral
        assert result.maneuver_type == "climb"

    def test_low_severity_lateral_avoidance(self):
        avoidance = _make_avoidance(minimum_clearance_meters=5.0)
        detection = ObstacleDetection(
            distance_meters=1.5,
            bearing_degrees=45.0,
            severity=ObstacleSeverity.LOW,
            width_meters=1.0,
            height_meters=1.0,
        )

        result = avoidance.compute_avoidance([detection])

        assert result is not None
        assert result.priority == 2

    def test_prioritizes_nearest_obstacle(self):
        avoidance = _make_avoidance(minimum_clearance_meters=5.0)
        far_detection = ObstacleDetection(
            distance_meters=4.0,
            bearing_degrees=0.0,
            severity=ObstacleSeverity.LOW,
            width_meters=1.0,
            height_meters=1.0,
        )
        close_detection = ObstacleDetection(
            distance_meters=1.0,
            bearing_degrees=0.0,
            severity=ObstacleSeverity.CRITICAL,
            width_meters=1.0,
            height_meters=1.0,
        )

        result = avoidance.compute_avoidance([far_detection, close_detection])

        assert result is not None
        assert result.maneuver_type == "hold"
        assert result.priority == 10


class TestChooseLateralDirection:
    def test_obstacle_right_goes_left(self):
        avoidance = _make_avoidance()
        direction = avoidance._choose_lateral_direction(bearing_degrees=30.0)
        assert direction == "lateral_left"

    def test_obstacle_left_goes_right(self):
        avoidance = _make_avoidance()
        direction = avoidance._choose_lateral_direction(bearing_degrees=-30.0)
        assert direction == "lateral_right"

    def test_obstacle_center_climbs(self):
        avoidance = _make_avoidance()
        direction = avoidance._choose_lateral_direction(bearing_degrees=0.0)
        assert direction == "climb"

    def test_at_positive_threshold_boundary(self):
        avoidance = _make_avoidance()
        # At exactly 15 degrees -- should NOT trigger lateral_left (uses >)
        direction = avoidance._choose_lateral_direction(bearing_degrees=15.0)
        assert direction == "climb"

    def test_just_above_positive_threshold(self):
        avoidance = _make_avoidance()
        direction = avoidance._choose_lateral_direction(bearing_degrees=15.1)
        assert direction == "lateral_left"

    def test_at_negative_threshold_boundary(self):
        avoidance = _make_avoidance()
        # At exactly -15 degrees -- should NOT trigger lateral_right (uses <)
        direction = avoidance._choose_lateral_direction(bearing_degrees=-15.0)
        assert direction == "climb"

    def test_just_below_negative_threshold(self):
        avoidance = _make_avoidance()
        direction = avoidance._choose_lateral_direction(bearing_degrees=-15.1)
        assert direction == "lateral_right"


class TestEstimateObstacleWidth:
    def test_max_distance_zero_returns_default(self):
        avoidance = _make_avoidance()
        frame = _make_frame(min_distance=5.0, max_distance=0.0)

        width = avoidance._estimate_obstacle_width(frame)

        assert width == 1.0

    def test_positive_width_with_valid_frame(self):
        avoidance = _make_avoidance()
        frame = _make_frame(min_distance=5.0, max_distance=10.0)

        width = avoidance._estimate_obstacle_width(frame)

        assert width >= 0.5

    def test_width_minimum_is_half_meter(self):
        avoidance = _make_avoidance()
        # Large depth range implies small coverage ratio
        frame = _make_frame(min_distance=0.1, max_distance=100.0)

        width = avoidance._estimate_obstacle_width(frame)

        assert width >= 0.5
