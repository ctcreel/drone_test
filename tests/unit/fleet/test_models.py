"""Tests for fleet domain models."""

import pytest
from pydantic import ValidationError

from src.fleet.models import (
    Drone,
    DroneHealth,
    DroneStatus,
    FleetState,
)


class TestDroneStatus:
    """Tests for DroneStatus enum."""

    def test_all_statuses_exist(self) -> None:
        assert len(DroneStatus) == 7

    def test_values_are_lowercase(self) -> None:
        for status in DroneStatus:
            assert status.value == status.value.lower()


class TestDroneHealth:
    """Tests for DroneHealth model."""

    def test_valid_health(self) -> None:
        health = DroneHealth(
            battery_voltage=11.8,
            battery_remaining_percent=72.0,
            estimated_flight_time_seconds=1800,
        )
        assert health.battery_voltage == 11.8
        assert health.connectivity == "connected"

    def test_invalid_battery_percent(self) -> None:
        with pytest.raises(ValidationError):
            DroneHealth(
                battery_voltage=11.8,
                battery_remaining_percent=150.0,
                estimated_flight_time_seconds=0,
            )


class TestDrone:
    """Tests for Drone model."""

    def test_create_drone(self) -> None:
        drone = Drone(
            drone_id="d-001",
            name="Alpha",
            iot_thing_name="drone-fleet-d-001",
        )
        assert drone.drone_id == "d-001"
        assert drone.status == DroneStatus.REGISTERED
        assert drone.health is None

    def test_drone_with_health(self) -> None:
        health = DroneHealth(
            battery_voltage=11.5,
            battery_remaining_percent=65.0,
            estimated_flight_time_seconds=1500,
        )
        drone = Drone(
            drone_id="d-002",
            name="Beta",
            health=health,
        )
        assert drone.health is not None
        assert drone.health.battery_remaining_percent == 65.0

    def test_to_dynamodb_item(self) -> None:
        drone = Drone(
            drone_id="d-ddb",
            name="DDB Test",
            iot_thing_name="drone-fleet-d-ddb",
            status=DroneStatus.AVAILABLE,
        )
        item = drone.to_dynamodb_item()
        assert item["pk"] == "DRONE#d-ddb"
        assert item["sk"] == "METADATA"
        assert item["gsi1pk"] == DroneStatus.AVAILABLE
        assert "health" not in item

    def test_to_dynamodb_item_with_health(self) -> None:
        drone = Drone(
            drone_id="d-h",
            name="Health Test",
            health=DroneHealth(
                battery_voltage=12.0,
                battery_remaining_percent=90.0,
                estimated_flight_time_seconds=3000,
            ),
        )
        item = drone.to_dynamodb_item()
        assert "health" in item

    def test_from_dynamodb_item_roundtrip(self) -> None:
        drone = Drone(
            drone_id="d-round",
            name="Roundtrip",
            iot_thing_name="drone-fleet-d-round",
            status=DroneStatus.ACTIVE,
        )
        item = drone.to_dynamodb_item()
        restored = Drone.from_dynamodb_item(item)
        assert restored.drone_id == "d-round"
        assert restored.status == DroneStatus.ACTIVE


class TestFleetState:
    """Tests for FleetState model."""

    def test_fleet_state(self) -> None:
        state = FleetState(
            total_drones=5,
            available_drones=3,
            active_drones=1,
            maintenance_drones=1,
        )
        assert state.total_drones == 5
