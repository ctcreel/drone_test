"""Tests for obstacle avoidance data models."""

import pytest
from pydantic import ValidationError

from edge.obstacle_avoidance.models import (
    AvoidanceManeuver,
    DepthFrame,
    ObstacleDetection,
    ObstacleSeverity,
)


class TestObstacleSeverity:
    def test_none_value(self):
        assert ObstacleSeverity.NONE.value == "none"

    def test_low_value(self):
        assert ObstacleSeverity.LOW.value == "low"

    def test_medium_value(self):
        assert ObstacleSeverity.MEDIUM.value == "medium"

    def test_high_value(self):
        assert ObstacleSeverity.HIGH.value == "high"

    def test_critical_value(self):
        assert ObstacleSeverity.CRITICAL.value == "critical"

    def test_all_severities_count(self):
        assert len(ObstacleSeverity) == 5

    def test_values_are_lowercase(self):
        for severity in ObstacleSeverity:
            assert severity.value == severity.value.lower()

    def test_is_string_enum(self):
        assert isinstance(ObstacleSeverity.NONE, str)
        assert ObstacleSeverity.NONE == "none"


class TestDepthFrame:
    def test_valid_frame(self):
        frame = DepthFrame(
            width=640,
            height=480,
            min_distance_meters=1.5,
            max_distance_meters=10.0,
            timestamp_ms=1000,
        )
        assert frame.width == 640
        assert frame.height == 480
        assert frame.min_distance_meters == 1.5
        assert frame.max_distance_meters == 10.0
        assert frame.timestamp_ms == 1000

    def test_width_minimum(self):
        frame = DepthFrame(
            width=1, height=1,
            min_distance_meters=0.0, max_distance_meters=0.0,
            timestamp_ms=0,
        )
        assert frame.width == 1

    def test_width_zero_rejected(self):
        with pytest.raises(ValidationError):
            DepthFrame(
                width=0, height=1,
                min_distance_meters=0.0, max_distance_meters=0.0,
                timestamp_ms=0,
            )

    def test_height_zero_rejected(self):
        with pytest.raises(ValidationError):
            DepthFrame(
                width=1, height=0,
                min_distance_meters=0.0, max_distance_meters=0.0,
                timestamp_ms=0,
            )

    def test_min_distance_negative_rejected(self):
        with pytest.raises(ValidationError):
            DepthFrame(
                width=1, height=1,
                min_distance_meters=-1.0, max_distance_meters=0.0,
                timestamp_ms=0,
            )

    def test_max_distance_negative_rejected(self):
        with pytest.raises(ValidationError):
            DepthFrame(
                width=1, height=1,
                min_distance_meters=0.0, max_distance_meters=-1.0,
                timestamp_ms=0,
            )

    def test_timestamp_negative_rejected(self):
        with pytest.raises(ValidationError):
            DepthFrame(
                width=1, height=1,
                min_distance_meters=0.0, max_distance_meters=0.0,
                timestamp_ms=-1,
            )

    def test_serialization_roundtrip(self):
        frame = DepthFrame(
            width=640, height=480,
            min_distance_meters=1.5, max_distance_meters=10.0,
            timestamp_ms=1000,
        )
        data = frame.model_dump()
        restored = DepthFrame(**data)
        assert restored == frame


class TestObstacleDetection:
    def test_valid_detection(self):
        detection = ObstacleDetection(
            distance_meters=5.0,
            bearing_degrees=30.0,
            severity=ObstacleSeverity.MEDIUM,
            width_meters=2.0,
            height_meters=1.5,
        )
        assert detection.distance_meters == 5.0
        assert detection.bearing_degrees == 30.0
        assert detection.severity == ObstacleSeverity.MEDIUM
        assert detection.width_meters == 2.0
        assert detection.height_meters == 1.5

    def test_bearing_minimum(self):
        detection = ObstacleDetection(
            distance_meters=1.0, bearing_degrees=-180.0,
            severity=ObstacleSeverity.LOW, width_meters=1.0, height_meters=1.0,
        )
        assert detection.bearing_degrees == -180.0

    def test_bearing_maximum(self):
        detection = ObstacleDetection(
            distance_meters=1.0, bearing_degrees=180.0,
            severity=ObstacleSeverity.LOW, width_meters=1.0, height_meters=1.0,
        )
        assert detection.bearing_degrees == 180.0

    def test_bearing_below_minimum_rejected(self):
        with pytest.raises(ValidationError):
            ObstacleDetection(
                distance_meters=1.0, bearing_degrees=-181.0,
                severity=ObstacleSeverity.LOW, width_meters=1.0, height_meters=1.0,
            )

    def test_bearing_above_maximum_rejected(self):
        with pytest.raises(ValidationError):
            ObstacleDetection(
                distance_meters=1.0, bearing_degrees=181.0,
                severity=ObstacleSeverity.LOW, width_meters=1.0, height_meters=1.0,
            )

    def test_distance_negative_rejected(self):
        with pytest.raises(ValidationError):
            ObstacleDetection(
                distance_meters=-1.0, bearing_degrees=0.0,
                severity=ObstacleSeverity.LOW, width_meters=1.0, height_meters=1.0,
            )

    def test_width_negative_rejected(self):
        with pytest.raises(ValidationError):
            ObstacleDetection(
                distance_meters=1.0, bearing_degrees=0.0,
                severity=ObstacleSeverity.LOW, width_meters=-1.0, height_meters=1.0,
            )

    def test_height_negative_rejected(self):
        with pytest.raises(ValidationError):
            ObstacleDetection(
                distance_meters=1.0, bearing_degrees=0.0,
                severity=ObstacleSeverity.LOW, width_meters=1.0, height_meters=-1.0,
            )

    def test_all_severity_levels(self):
        for severity in ObstacleSeverity:
            detection = ObstacleDetection(
                distance_meters=1.0, bearing_degrees=0.0,
                severity=severity, width_meters=1.0, height_meters=1.0,
            )
            assert detection.severity == severity

    def test_serialization_roundtrip(self):
        detection = ObstacleDetection(
            distance_meters=5.0, bearing_degrees=30.0,
            severity=ObstacleSeverity.HIGH, width_meters=2.0, height_meters=1.5,
        )
        data = detection.model_dump()
        restored = ObstacleDetection(**data)
        assert restored == detection


class TestAvoidanceManeuver:
    def test_valid_maneuver(self):
        maneuver = AvoidanceManeuver(
            maneuver_type="climb",
            magnitude_meters=5.0,
            duration_seconds=3.0,
            priority=8,
        )
        assert maneuver.maneuver_type == "climb"
        assert maneuver.magnitude_meters == 5.0
        assert maneuver.duration_seconds == 3.0
        assert maneuver.priority == 8

    def test_hold_maneuver(self):
        maneuver = AvoidanceManeuver(
            maneuver_type="hold",
            magnitude_meters=0.0,
            duration_seconds=2.0,
            priority=10,
        )
        assert maneuver.maneuver_type == "hold"
        assert maneuver.magnitude_meters == 0.0

    def test_lateral_left_maneuver(self):
        maneuver = AvoidanceManeuver(
            maneuver_type="lateral_left",
            magnitude_meters=3.0,
            duration_seconds=2.5,
            priority=5,
        )
        assert maneuver.maneuver_type == "lateral_left"

    def test_lateral_right_maneuver(self):
        maneuver = AvoidanceManeuver(
            maneuver_type="lateral_right",
            magnitude_meters=3.0,
            duration_seconds=2.5,
            priority=2,
        )
        assert maneuver.maneuver_type == "lateral_right"

    def test_magnitude_negative_rejected(self):
        with pytest.raises(ValidationError):
            AvoidanceManeuver(
                maneuver_type="climb",
                magnitude_meters=-1.0,
                duration_seconds=1.0,
                priority=5,
            )

    def test_duration_negative_rejected(self):
        with pytest.raises(ValidationError):
            AvoidanceManeuver(
                maneuver_type="climb",
                magnitude_meters=1.0,
                duration_seconds=-1.0,
                priority=5,
            )

    def test_priority_minimum(self):
        maneuver = AvoidanceManeuver(
            maneuver_type="hold",
            magnitude_meters=0.0,
            duration_seconds=0.0,
            priority=0,
        )
        assert maneuver.priority == 0

    def test_priority_maximum(self):
        maneuver = AvoidanceManeuver(
            maneuver_type="hold",
            magnitude_meters=0.0,
            duration_seconds=0.0,
            priority=10,
        )
        assert maneuver.priority == 10

    def test_priority_below_minimum_rejected(self):
        with pytest.raises(ValidationError):
            AvoidanceManeuver(
                maneuver_type="hold",
                magnitude_meters=0.0,
                duration_seconds=0.0,
                priority=-1,
            )

    def test_priority_above_maximum_rejected(self):
        with pytest.raises(ValidationError):
            AvoidanceManeuver(
                maneuver_type="hold",
                magnitude_meters=0.0,
                duration_seconds=0.0,
                priority=11,
            )

    def test_serialization_roundtrip(self):
        maneuver = AvoidanceManeuver(
            maneuver_type="climb",
            magnitude_meters=5.0,
            duration_seconds=3.0,
            priority=8,
        )
        data = maneuver.model_dump()
        restored = AvoidanceManeuver(**data)
        assert restored == maneuver
