"""Tests for MAVLink bridge data models."""

import pytest
from pydantic import ValidationError

from edge.mavlink_bridge.models import (
    AutopilotState,
    GpsPosition,
    MavlinkCommand,
    TelemetryData,
)


class TestAutopilotState:
    def test_disconnected_value(self):
        assert AutopilotState.DISCONNECTED.value == "disconnected"

    def test_connecting_value(self):
        assert AutopilotState.CONNECTING.value == "connecting"

    def test_connected_value(self):
        assert AutopilotState.CONNECTED.value == "connected"

    def test_armed_value(self):
        assert AutopilotState.ARMED.value == "armed"

    def test_flying_value(self):
        assert AutopilotState.FLYING.value == "flying"

    def test_landing_value(self):
        assert AutopilotState.LANDING.value == "landing"

    def test_landed_value(self):
        assert AutopilotState.LANDED.value == "landed"

    def test_all_states_count(self):
        assert len(AutopilotState) == 7

    def test_values_are_lowercase(self):
        for state in AutopilotState:
            assert state.value == state.value.lower()

    def test_is_string_enum(self):
        assert isinstance(AutopilotState.DISCONNECTED, str)
        assert AutopilotState.DISCONNECTED == "disconnected"


class TestMavlinkCommand:
    def test_minimal_command(self):
        command = MavlinkCommand(command_type="ARM")
        assert command.command_type == "ARM"
        assert command.parameters == {}
        assert command.target_system == 1
        assert command.target_component == 1

    def test_command_with_parameters(self):
        command = MavlinkCommand(
            command_type="TAKEOFF",
            parameters={"altitude": 10.0},
        )
        assert command.parameters["altitude"] == 10.0

    def test_command_with_custom_targets(self):
        command = MavlinkCommand(
            command_type="SET_MODE",
            target_system=2,
            target_component=3,
        )
        assert command.target_system == 2
        assert command.target_component == 3

    def test_goto_command_parameters(self):
        command = MavlinkCommand(
            command_type="GOTO",
            parameters={
                "latitude": 40.7128,
                "longitude": -74.0060,
                "altitude": 50.0,
            },
        )
        assert command.parameters["latitude"] == 40.7128
        assert command.parameters["longitude"] == -74.0060
        assert command.parameters["altitude"] == 50.0

    def test_command_type_is_string(self):
        command = MavlinkCommand(command_type="RTL")
        assert isinstance(command.command_type, str)

    def test_parameters_default_is_empty_dict(self):
        command1 = MavlinkCommand(command_type="ARM")
        command2 = MavlinkCommand(command_type="ARM")
        assert command1.parameters is not command2.parameters

    def test_serialization_roundtrip(self):
        command = MavlinkCommand(
            command_type="GOTO",
            parameters={"latitude": 40.7128},
            target_system=2,
        )
        data = command.model_dump()
        restored = MavlinkCommand(**data)
        assert restored == command


class TestTelemetryData:
    def test_valid_telemetry(self):
        telemetry = TelemetryData(
            latitude=40.7128,
            longitude=-74.0060,
            altitude=50.0,
            heading=180.0,
            ground_speed=5.0,
            vertical_speed=-1.0,
            battery_voltage=12.6,
            battery_remaining=80,
            gps_fix_type=3,
            satellites_visible=12,
        )
        assert telemetry.latitude == 40.7128
        assert telemetry.longitude == -74.0060
        assert telemetry.altitude == 50.0
        assert telemetry.heading == 180.0
        assert telemetry.ground_speed == 5.0
        assert telemetry.vertical_speed == -1.0
        assert telemetry.battery_voltage == 12.6
        assert telemetry.battery_remaining == 80
        assert telemetry.gps_fix_type == 3
        assert telemetry.satellites_visible == 12

    def test_heading_minimum(self):
        telemetry = TelemetryData(
            latitude=0, longitude=0, altitude=0, heading=0.0,
            ground_speed=0, vertical_speed=0, battery_voltage=0,
            battery_remaining=0, gps_fix_type=0, satellites_visible=0,
        )
        assert telemetry.heading == 0.0

    def test_heading_maximum(self):
        telemetry = TelemetryData(
            latitude=0, longitude=0, altitude=0, heading=360.0,
            ground_speed=0, vertical_speed=0, battery_voltage=0,
            battery_remaining=0, gps_fix_type=0, satellites_visible=0,
        )
        assert telemetry.heading == 360.0

    def test_heading_below_minimum_rejected(self):
        with pytest.raises(ValidationError):
            TelemetryData(
                latitude=0, longitude=0, altitude=0, heading=-1.0,
                ground_speed=0, vertical_speed=0, battery_voltage=0,
                battery_remaining=0, gps_fix_type=0, satellites_visible=0,
            )

    def test_heading_above_maximum_rejected(self):
        with pytest.raises(ValidationError):
            TelemetryData(
                latitude=0, longitude=0, altitude=0, heading=361.0,
                ground_speed=0, vertical_speed=0, battery_voltage=0,
                battery_remaining=0, gps_fix_type=0, satellites_visible=0,
            )

    def test_ground_speed_negative_rejected(self):
        with pytest.raises(ValidationError):
            TelemetryData(
                latitude=0, longitude=0, altitude=0, heading=0,
                ground_speed=-1.0, vertical_speed=0, battery_voltage=0,
                battery_remaining=0, gps_fix_type=0, satellites_visible=0,
            )

    def test_battery_voltage_negative_rejected(self):
        with pytest.raises(ValidationError):
            TelemetryData(
                latitude=0, longitude=0, altitude=0, heading=0,
                ground_speed=0, vertical_speed=0, battery_voltage=-1.0,
                battery_remaining=0, gps_fix_type=0, satellites_visible=0,
            )

    def test_battery_remaining_below_zero_rejected(self):
        with pytest.raises(ValidationError):
            TelemetryData(
                latitude=0, longitude=0, altitude=0, heading=0,
                ground_speed=0, vertical_speed=0, battery_voltage=0,
                battery_remaining=-1, gps_fix_type=0, satellites_visible=0,
            )

    def test_battery_remaining_above_100_rejected(self):
        with pytest.raises(ValidationError):
            TelemetryData(
                latitude=0, longitude=0, altitude=0, heading=0,
                ground_speed=0, vertical_speed=0, battery_voltage=0,
                battery_remaining=101, gps_fix_type=0, satellites_visible=0,
            )

    def test_gps_fix_type_negative_rejected(self):
        with pytest.raises(ValidationError):
            TelemetryData(
                latitude=0, longitude=0, altitude=0, heading=0,
                ground_speed=0, vertical_speed=0, battery_voltage=0,
                battery_remaining=0, gps_fix_type=-1, satellites_visible=0,
            )

    def test_satellites_visible_negative_rejected(self):
        with pytest.raises(ValidationError):
            TelemetryData(
                latitude=0, longitude=0, altitude=0, heading=0,
                ground_speed=0, vertical_speed=0, battery_voltage=0,
                battery_remaining=0, gps_fix_type=0, satellites_visible=-1,
            )

    def test_vertical_speed_can_be_negative(self):
        telemetry = TelemetryData(
            latitude=0, longitude=0, altitude=0, heading=0,
            ground_speed=0, vertical_speed=-5.0, battery_voltage=0,
            battery_remaining=0, gps_fix_type=0, satellites_visible=0,
        )
        assert telemetry.vertical_speed == -5.0

    def test_serialization_roundtrip(self):
        telemetry = TelemetryData(
            latitude=40.7128, longitude=-74.0060, altitude=50.0,
            heading=180.0, ground_speed=5.0, vertical_speed=-1.0,
            battery_voltage=12.6, battery_remaining=80,
            gps_fix_type=3, satellites_visible=12,
        )
        data = telemetry.model_dump()
        restored = TelemetryData(**data)
        assert restored == telemetry


class TestGpsPosition:
    def test_valid_position(self):
        position = GpsPosition(
            latitude=40.7128,
            longitude=-74.0060,
            altitude=50.0,
        )
        assert position.latitude == 40.7128
        assert position.longitude == -74.0060
        assert position.altitude == 50.0

    def test_negative_coordinates(self):
        position = GpsPosition(
            latitude=-33.8688,
            longitude=151.2093,
            altitude=0.0,
        )
        assert position.latitude == -33.8688
        assert position.longitude == 151.2093

    def test_zero_values(self):
        position = GpsPosition(latitude=0, longitude=0, altitude=0)
        assert position.latitude == 0.0
        assert position.longitude == 0.0
        assert position.altitude == 0.0

    def test_serialization_roundtrip(self):
        position = GpsPosition(latitude=40.7128, longitude=-74.0060, altitude=50.0)
        data = position.model_dump()
        restored = GpsPosition(**data)
        assert restored == position
