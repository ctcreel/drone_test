"""Tests for telemetry domain models."""

from src.telemetry.models import BatteryReport, ObstacleEvent, PositionReport


class TestPositionReport:
    """Tests for PositionReport model."""

    def test_valid_position(self) -> None:
        report = PositionReport(
            drone_id="d-001",
            timestamp="2024-01-01T00:00:00Z",
            latitude=40.7128,
            longitude=-74.0060,
            altitude=50.0,
            heading=180.0,
            speed=5.0,
        )
        assert report.latitude == 40.7128

    def test_to_dynamodb_item(self) -> None:
        report = PositionReport(
            drone_id="d-002",
            timestamp="2024-01-01T12:00:00Z",
            latitude=40.0,
            longitude=-74.0,
            altitude=30.0,
            heading=90.0,
            speed=3.0,
        )
        item = report.to_dynamodb_item()
        assert item["pk"] == "DRONE#d-002"
        assert item["sk"] == "TELEMETRY#2024-01-01T12:00:00Z"
        assert item["message_type"] == "position_report"
        assert item["gsi2pk"] == "DRONE#d-002"


class TestBatteryReport:
    """Tests for BatteryReport model."""

    def test_valid_battery(self) -> None:
        report = BatteryReport(
            drone_id="d-001",
            timestamp="2024-01-01T00:00:00Z",
            voltage=11.8,
            remaining_percent=72.0,
            estimated_flight_time_seconds=1800,
        )
        assert report.voltage == 11.8

    def test_to_dynamodb_item(self) -> None:
        report = BatteryReport(
            drone_id="d-003",
            timestamp="2024-01-01T12:00:00Z",
            voltage=12.0,
            remaining_percent=90.0,
            estimated_flight_time_seconds=3000,
        )
        item = report.to_dynamodb_item()
        assert item["message_type"] == "battery_report"
        assert item["voltage"] == 12.0


class TestObstacleEvent:
    """Tests for ObstacleEvent model."""

    def test_valid_obstacle(self) -> None:
        event = ObstacleEvent(
            drone_id="d-001",
            timestamp="2024-01-01T00:00:00Z",
            obstacle_type="building",
            distance_meters=5.0,
            avoidance_action="altitude_increase",
        )
        assert event.obstacle_type == "building"

    def test_to_dynamodb_item(self) -> None:
        event = ObstacleEvent(
            drone_id="d-004",
            timestamp="2024-01-01T12:00:00Z",
            obstacle_type="tree",
            distance_meters=3.0,
            avoidance_action="lateral_shift",
        )
        item = event.to_dynamodb_item()
        assert item["message_type"] == "obstacle_event"
        assert item["avoidance_action"] == "lateral_shift"
