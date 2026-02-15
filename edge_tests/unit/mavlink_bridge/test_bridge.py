"""Tests for MavlinkBridge with mocked pymavlink."""

from unittest.mock import MagicMock, patch

import pytest

from edge.mavlink_bridge.bridge import MavlinkBridge
from edge.mavlink_bridge.models import AutopilotState, MavlinkCommand


def _make_bridge(
    connection_string="tcp:127.0.0.1:5760",
    baud_rate=57600,
):
    """Create a MavlinkBridge instance."""
    return MavlinkBridge(
        connection_string=connection_string,
        baud_rate=baud_rate,
    )


def _make_connected_bridge():
    """Create a MavlinkBridge that appears connected."""
    bridge = _make_bridge()
    mock_connection = MagicMock()
    mock_connection.target_system = 1
    mock_connection.target_component = 1
    bridge._connection = mock_connection
    bridge._state = AutopilotState.CONNECTED
    return bridge, mock_connection


class TestMavlinkBridgeInit:
    def test_initial_state_is_disconnected(self):
        bridge = _make_bridge()
        assert bridge.state == AutopilotState.DISCONNECTED

    def test_stores_connection_string(self):
        bridge = _make_bridge(connection_string="udp:192.168.1.1:14550")
        assert bridge._connection_string == "udp:192.168.1.1:14550"

    def test_stores_baud_rate(self):
        bridge = _make_bridge(baud_rate=115200)
        assert bridge._baud_rate == 115200

    def test_no_initial_connection(self):
        bridge = _make_bridge()
        assert bridge._connection is None

    def test_command_handlers_registered(self):
        bridge = _make_bridge()
        expected_commands = {"ARM", "DISARM", "SET_MODE", "TAKEOFF", "GOTO", "LAND", "RTL"}
        assert set(bridge._command_handlers.keys()) == expected_commands


class TestMavlinkBridgeConnect:
    @patch("edge.mavlink_bridge.bridge.mavutil")
    def test_connect_success(self, mock_mavutil):
        mock_connection = MagicMock()
        mock_connection.target_system = 1
        mock_connection.target_component = 1
        mock_mavutil.mavlink_connection.return_value = mock_connection

        bridge = _make_bridge()
        bridge.connect()

        mock_mavutil.mavlink_connection.assert_called_once_with(
            "tcp:127.0.0.1:5760",
            baud=57600,
        )
        mock_connection.wait_heartbeat.assert_called_once_with(timeout=30)
        assert bridge.state == AutopilotState.CONNECTED

    @patch("edge.mavlink_bridge.bridge.mavutil")
    def test_connect_transitions_through_connecting(self, mock_mavutil):
        mock_connection = MagicMock()
        mock_connection.target_system = 1
        mock_connection.target_component = 1

        states_during_connect = []

        def capture_state(*args, **kwargs):
            states_during_connect.append(bridge.state)

        mock_connection.wait_heartbeat.side_effect = capture_state
        mock_mavutil.mavlink_connection.return_value = mock_connection

        bridge = _make_bridge()
        bridge.connect()

        assert AutopilotState.CONNECTING in states_during_connect

    @patch("edge.mavlink_bridge.bridge.mavutil")
    def test_connect_failure_raises_connection_error(self, mock_mavutil):
        mock_mavutil.mavlink_connection.side_effect = OSError("Connection refused")

        bridge = _make_bridge()
        with pytest.raises(ConnectionError, match="Failed to connect"):
            bridge.connect()

        assert bridge.state == AutopilotState.DISCONNECTED

    @patch("edge.mavlink_bridge.bridge.mavutil")
    def test_connect_heartbeat_failure_raises_connection_error(self, mock_mavutil):
        mock_connection = MagicMock()
        mock_connection.wait_heartbeat.side_effect = TimeoutError("No heartbeat")
        mock_mavutil.mavlink_connection.return_value = mock_connection

        bridge = _make_bridge()
        with pytest.raises(ConnectionError, match="Failed to connect"):
            bridge.connect()

        assert bridge.state == AutopilotState.DISCONNECTED


class TestMavlinkBridgeDisconnect:
    def test_disconnect_when_connected(self):
        bridge, mock_connection = _make_connected_bridge()

        bridge.disconnect()

        mock_connection.close.assert_called_once()
        assert bridge._connection is None
        assert bridge.state == AutopilotState.DISCONNECTED

    def test_disconnect_when_already_disconnected(self):
        bridge = _make_bridge()
        bridge.disconnect()
        assert bridge.state == AutopilotState.DISCONNECTED

    def test_disconnect_clears_connection(self):
        bridge, _ = _make_connected_bridge()
        bridge.disconnect()
        assert bridge._connection is None


class TestMavlinkBridgeSendCommand:
    def test_send_arm_command(self):
        bridge, mock_connection = _make_connected_bridge()

        command = MavlinkCommand(command_type="ARM")
        bridge.send_command(command)

        mock_connection.arducopter_arm.assert_called_once()
        assert bridge.state == AutopilotState.ARMED

    def test_send_disarm_command(self):
        bridge, mock_connection = _make_connected_bridge()
        bridge._state = AutopilotState.ARMED

        command = MavlinkCommand(command_type="DISARM")
        bridge.send_command(command)

        mock_connection.arducopter_disarm.assert_called_once()
        assert bridge.state == AutopilotState.CONNECTED

    def test_send_unknown_command_raises(self):
        bridge, _ = _make_connected_bridge()

        command = MavlinkCommand(command_type="UNKNOWN")
        with pytest.raises(ValueError, match="Unknown command type: UNKNOWN"):
            bridge.send_command(command)

    def test_send_command_when_disconnected_raises(self):
        bridge = _make_bridge()

        command = MavlinkCommand(command_type="ARM")
        with pytest.raises(ConnectionError, match="Not connected"):
            bridge.send_command(command)

    def test_send_takeoff_command(self):
        bridge, mock_connection = _make_connected_bridge()

        command = MavlinkCommand(
            command_type="TAKEOFF",
            parameters={"altitude": 10.0},
        )
        bridge.send_command(command)

        mock_connection.mav.command_long_send.assert_called_once()
        assert bridge.state == AutopilotState.FLYING

    def test_send_takeoff_without_altitude_raises(self):
        bridge, _ = _make_connected_bridge()

        command = MavlinkCommand(command_type="TAKEOFF")
        with pytest.raises(ValueError, match="altitude"):
            bridge.send_command(command)

    def test_send_goto_command(self):
        bridge, mock_connection = _make_connected_bridge()

        command = MavlinkCommand(
            command_type="GOTO",
            parameters={
                "latitude": 40.7128,
                "longitude": -74.0060,
                "altitude": 50.0,
            },
        )
        bridge.send_command(command)

        mock_connection.mav.mission_item_int_send.assert_called_once()
        assert bridge.state == AutopilotState.FLYING

    def test_send_goto_without_coordinates_raises(self):
        bridge, _ = _make_connected_bridge()

        command = MavlinkCommand(
            command_type="GOTO",
            parameters={"latitude": 40.0},
        )
        with pytest.raises(ValueError, match=r"latitude.*longitude.*altitude"):
            bridge.send_command(command)

    def test_send_land_command(self):
        bridge, mock_connection = _make_connected_bridge()

        command = MavlinkCommand(command_type="LAND")
        bridge.send_command(command)

        mock_connection.mode_mapping.assert_called()
        assert bridge.state == AutopilotState.LANDING

    def test_send_rtl_command(self):
        bridge, mock_connection = _make_connected_bridge()
        mock_connection.mode_mapping.return_value = {"RTL": 6}

        command = MavlinkCommand(command_type="RTL")
        bridge.send_command(command)

        mock_connection.set_mode.assert_called_once_with(6)
        assert bridge.state == AutopilotState.FLYING

    def test_send_set_mode_command(self):
        bridge, mock_connection = _make_connected_bridge()
        # SET_MODE handler converts float to int then str for mode_mapping lookup
        mock_connection.mode_mapping.return_value = {"4": 4}

        command = MavlinkCommand(
            command_type="SET_MODE",
            parameters={"mode": 4.0},
        )
        bridge.send_command(command)

        mock_connection.set_mode.assert_called_once_with(4)

    def test_send_set_mode_without_mode_raises(self):
        bridge, _ = _make_connected_bridge()

        command = MavlinkCommand(command_type="SET_MODE")
        with pytest.raises(ValueError, match="mode"):
            bridge.send_command(command)


class TestMavlinkBridgeGetTelemetry:
    def test_get_telemetry_success(self):
        bridge, mock_connection = _make_connected_bridge()

        mock_position = MagicMock()
        mock_position.lat = 407128000
        mock_position.lon = -740060000
        mock_position.relative_alt = 5000
        mock_position.hdg = 18000
        mock_position.vx = 500
        mock_position.vz = -100

        mock_sys_status = MagicMock()
        mock_sys_status.voltage_battery = 12600
        mock_sys_status.battery_remaining = 80

        mock_gps_raw = MagicMock()
        mock_gps_raw.fix_type = 3
        mock_gps_raw.satellites_visible = 12

        def recv_match_side_effect(type, **kwargs):
            messages = {
                "GLOBAL_POSITION_INT": mock_position,
                "SYS_STATUS": mock_sys_status,
                "GPS_RAW_INT": mock_gps_raw,
            }
            return messages.get(type)

        mock_connection.recv_match.side_effect = recv_match_side_effect

        telemetry = bridge.get_telemetry()

        assert telemetry.latitude == pytest.approx(40.7128, abs=0.001)
        assert telemetry.longitude == pytest.approx(-74.006, abs=0.001)
        assert telemetry.altitude == pytest.approx(50.0, abs=0.1)
        assert telemetry.heading == pytest.approx(180.0, abs=0.1)
        assert telemetry.battery_voltage == pytest.approx(12.6, abs=0.01)
        assert telemetry.battery_remaining == 80
        assert telemetry.gps_fix_type == 3
        assert telemetry.satellites_visible == 12

    def test_get_telemetry_when_disconnected_raises(self):
        bridge = _make_bridge()

        with pytest.raises(ConnectionError):
            bridge.get_telemetry()

    def test_get_telemetry_position_timeout_raises(self):
        bridge, mock_connection = _make_connected_bridge()
        mock_connection.recv_match.return_value = None

        with pytest.raises(TimeoutError, match="GLOBAL_POSITION_INT"):
            bridge.get_telemetry()

    def test_get_telemetry_sys_status_timeout_raises(self):
        bridge, mock_connection = _make_connected_bridge()

        mock_position = MagicMock()
        mock_position.lat = 0
        mock_position.lon = 0
        mock_position.relative_alt = 0
        mock_position.hdg = 0
        mock_position.vx = 0
        mock_position.vz = 0

        call_count = 0

        def recv_match_side_effect(type, **kwargs):
            nonlocal call_count
            call_count += 1
            if type == "GLOBAL_POSITION_INT":
                return mock_position
            return None

        mock_connection.recv_match.side_effect = recv_match_side_effect

        with pytest.raises(TimeoutError, match="SYS_STATUS"):
            bridge.get_telemetry()

    def test_get_telemetry_gps_raw_timeout_raises(self):
        bridge, mock_connection = _make_connected_bridge()

        mock_position = MagicMock()
        mock_position.lat = 0
        mock_position.lon = 0
        mock_position.relative_alt = 0
        mock_position.hdg = 0
        mock_position.vx = 0
        mock_position.vz = 0

        mock_sys_status = MagicMock()
        mock_sys_status.voltage_battery = 12000
        mock_sys_status.battery_remaining = 50

        def recv_match_side_effect(type, **kwargs):
            if type == "GLOBAL_POSITION_INT":
                return mock_position
            if type == "SYS_STATUS":
                return mock_sys_status
            return None

        mock_connection.recv_match.side_effect = recv_match_side_effect

        with pytest.raises(TimeoutError, match="GPS_RAW_INT"):
            bridge.get_telemetry()


class TestMavlinkBridgeArm:
    def test_arm_success(self):
        bridge, mock_connection = _make_connected_bridge()

        bridge.arm()

        mock_connection.arducopter_arm.assert_called_once()
        mock_connection.motors_armed_wait.assert_called_once()
        assert bridge.state == AutopilotState.ARMED

    def test_arm_when_disconnected_raises(self):
        bridge = _make_bridge()
        with pytest.raises(ConnectionError):
            bridge.arm()


class TestMavlinkBridgeDisarm:
    def test_disarm_success(self):
        bridge, mock_connection = _make_connected_bridge()
        bridge._state = AutopilotState.ARMED

        bridge.disarm()

        mock_connection.arducopter_disarm.assert_called_once()
        mock_connection.motors_disarmed_wait.assert_called_once()
        assert bridge.state == AutopilotState.CONNECTED

    def test_disarm_when_disconnected_raises(self):
        bridge = _make_bridge()
        with pytest.raises(ConnectionError):
            bridge.disarm()


class TestMavlinkBridgeSetMode:
    def test_set_mode_success(self):
        bridge, mock_connection = _make_connected_bridge()
        mock_connection.mode_mapping.return_value = {"GUIDED": 4}

        bridge.set_mode("GUIDED")

        mock_connection.set_mode.assert_called_once_with(4)

    def test_set_mode_unknown_raises(self):
        bridge, mock_connection = _make_connected_bridge()
        mock_connection.mode_mapping.return_value = {}

        with pytest.raises(ValueError, match="Unknown flight mode"):
            bridge.set_mode("INVALID_MODE")

    def test_set_mode_when_disconnected_raises(self):
        bridge = _make_bridge()
        with pytest.raises(ConnectionError):
            bridge.set_mode("GUIDED")


class TestMavlinkBridgeGoto:
    @patch("edge.mavlink_bridge.bridge.mavutil")
    def test_goto_sends_mission_item(self, mock_mavutil):
        bridge, mock_connection = _make_connected_bridge()

        bridge.goto(latitude=40.7128, longitude=-74.0060, altitude=50.0)

        mock_connection.mav.mission_item_int_send.assert_called_once()
        assert bridge.state == AutopilotState.FLYING

    def test_goto_when_disconnected_raises(self):
        bridge = _make_bridge()
        with pytest.raises(ConnectionError):
            bridge.goto(latitude=40.0, longitude=-74.0, altitude=50.0)


class TestMavlinkBridgeTakeoff:
    @patch("edge.mavlink_bridge.bridge.mavutil")
    def test_takeoff_sends_command_long(self, mock_mavutil):
        bridge, mock_connection = _make_connected_bridge()

        bridge.takeoff(altitude=10.0)

        mock_connection.mav.command_long_send.assert_called_once()
        call_args = mock_connection.mav.command_long_send.call_args[0]
        assert call_args[-1] == 10.0  # altitude is the last parameter
        assert bridge.state == AutopilotState.FLYING

    def test_takeoff_when_disconnected_raises(self):
        bridge = _make_bridge()
        with pytest.raises(ConnectionError):
            bridge.takeoff(altitude=10.0)


class TestMavlinkBridgeLand:
    def test_land_sets_mode_and_state(self):
        bridge, mock_connection = _make_connected_bridge()
        mock_connection.mode_mapping.return_value = {"LAND": 9}

        bridge.land()

        mock_connection.set_mode.assert_called_once_with(9)
        assert bridge.state == AutopilotState.LANDING

    def test_land_when_disconnected_raises(self):
        bridge = _make_bridge()
        with pytest.raises(ConnectionError):
            bridge.land()


class TestMavlinkBridgeStateTransitions:
    @patch("edge.mavlink_bridge.bridge.mavutil")
    def test_connect_disconnect_cycle(self, mock_mavutil):
        mock_connection = MagicMock()
        mock_connection.target_system = 1
        mock_connection.target_component = 1
        mock_mavutil.mavlink_connection.return_value = mock_connection

        bridge = _make_bridge()
        assert bridge.state == AutopilotState.DISCONNECTED

        bridge.connect()
        assert bridge.state == AutopilotState.CONNECTED

        bridge.disconnect()
        assert bridge.state == AutopilotState.DISCONNECTED

    def test_connected_arm_disarm_cycle(self):
        bridge, _ = _make_connected_bridge()
        assert bridge.state == AutopilotState.CONNECTED

        bridge.arm()
        assert bridge.state == AutopilotState.ARMED

        bridge.disarm()
        assert bridge.state == AutopilotState.CONNECTED

    @patch("edge.mavlink_bridge.bridge.mavutil")
    def test_arm_takeoff_land_cycle(self, mock_mavutil):
        bridge, mock_connection = _make_connected_bridge()
        mock_connection.mode_mapping.return_value = {"LAND": 9}

        bridge.arm()
        assert bridge.state == AutopilotState.ARMED

        bridge.takeoff(altitude=10.0)
        assert bridge.state == AutopilotState.FLYING

        bridge.land()
        assert bridge.state == AutopilotState.LANDING
