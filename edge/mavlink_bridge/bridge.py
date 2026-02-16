"""MAVLink bridge for ArduPilot communication via pymavlink.

Provides a deterministic interface to send commands and receive telemetry
from the ArduPilot flight controller over MAVLink protocol.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pymavlink import mavutil

from edge.mavlink_bridge.models import AutopilotState, TelemetryData

if TYPE_CHECKING:
    from pymavlink.mavutil import mavfile

    from edge.mavlink_bridge.models import MavlinkCommand

logger = logging.getLogger(__name__)

# MAVLink command constants
_ARM_PARAM: float = 1.0
_DISARM_PARAM: float = 0.0
_HEARTBEAT_TIMEOUT_SECONDS: int = 30
_MESSAGE_TIMEOUT_SECONDS: float = 5.0
_COORDINATE_SCALE: float = 1e-7
_HEADING_SCALE: float = 100.0
_SPEED_SCALE: float = 100.0
_DATA_STREAM_RATE_HZ: int = 4
_VOLTAGE_SCALE: float = 1000.0

# Command type dispatch keys
_COMMAND_ARM = "ARM"
_COMMAND_DISARM = "DISARM"
_COMMAND_SET_MODE = "SET_MODE"
_COMMAND_TAKEOFF = "TAKEOFF"
_COMMAND_GOTO = "GOTO"
_COMMAND_LAND = "LAND"
_COMMAND_RTL = "RTL"


class MavlinkBridge:
    """Bridge to ArduPilot autopilot via MAVLink protocol.

    Handles connection management, command dispatch, and telemetry
    retrieval using pymavlink. All operations are deterministic
    and suitable for edge deployment.
    """

    def __init__(
        self,
        connection_string: str,
        baud_rate: int,
    ) -> None:
        """Initialize the MAVLink bridge.

        Args:
            connection_string: MAVLink connection URI (e.g., "tcp:127.0.0.1:5760").
            baud_rate: Serial baud rate for the connection.
        """
        self._connection_string = connection_string
        self._baud_rate = baud_rate
        self._connection: mavfile | None = None
        self._state = AutopilotState.DISCONNECTED

        self._command_handlers: dict[str, object] = {
            _COMMAND_ARM: self._handle_arm,
            _COMMAND_DISARM: self._handle_disarm,
            _COMMAND_SET_MODE: self._handle_set_mode,
            _COMMAND_TAKEOFF: self._handle_takeoff,
            _COMMAND_GOTO: self._handle_goto,
            _COMMAND_LAND: self._handle_land,
            _COMMAND_RTL: self._handle_rtl,
        }

    @property
    def state(self) -> AutopilotState:
        """Return the current autopilot connection state."""
        return self._state

    def connect(self) -> None:
        """Connect to the autopilot and wait for heartbeat.

        Raises:
            ConnectionError: If the connection or heartbeat fails.
        """
        logger.info(
            "Connecting to autopilot at %s (baud=%d)",
            self._connection_string,
            self._baud_rate,
        )
        self._state = AutopilotState.CONNECTING

        try:
            self._connection = mavutil.mavlink_connection(
                self._connection_string,
                baud=self._baud_rate,
            )
            logger.info("Waiting for heartbeat (timeout=%ds)", _HEARTBEAT_TIMEOUT_SECONDS)
            self._connection.wait_heartbeat(timeout=_HEARTBEAT_TIMEOUT_SECONDS)
        except Exception as error:
            self._state = AutopilotState.DISCONNECTED
            logger.exception("Failed to connect to autopilot at %s", self._connection_string)
            raise ConnectionError(
                f"Failed to connect to autopilot at {self._connection_string}: {error}"
            ) from error

        self._state = AutopilotState.CONNECTED
        self._request_data_streams()
        logger.info(
            "Connected to autopilot (system=%d, component=%d)",
            self._connection.target_system,
            self._connection.target_component,
        )

    def _request_data_streams(self) -> None:
        """Request telemetry data streams from the autopilot.

        Sends REQUEST_DATA_STREAM messages so the autopilot begins
        sending GLOBAL_POSITION_INT, SYS_STATUS, and GPS_RAW_INT.
        """
        connection = self._get_connection()
        for stream_id in (
            mavutil.mavlink.MAV_DATA_STREAM_POSITION,
            mavutil.mavlink.MAV_DATA_STREAM_EXTENDED_STATUS,
        ):
            connection.mav.request_data_stream_send(
                connection.target_system,
                connection.target_component,
                stream_id,
                _DATA_STREAM_RATE_HZ,
                1,
            )
        logger.info("Requested data streams at %d Hz", _DATA_STREAM_RATE_HZ)

    def disconnect(self) -> None:
        """Disconnect from the autopilot and release resources."""
        if self._connection is not None:
            logger.info("Disconnecting from autopilot")
            self._connection.close()
            self._connection = None

        self._state = AutopilotState.DISCONNECTED
        logger.info("Disconnected from autopilot")

    def send_command(self, command: MavlinkCommand) -> None:
        """Dispatch a command to the appropriate handler.

        Args:
            command: The MAVLink command to execute.

        Raises:
            ConnectionError: If not connected to the autopilot.
            ValueError: If the command type is not recognized.
        """
        self._require_connection()

        handler = self._command_handlers.get(command.command_type)
        if handler is None:
            raise ValueError(f"Unknown command type: {command.command_type}")

        logger.info(
            "Executing command: %s with params=%s", command.command_type, command.parameters
        )
        handler(command)  # type: ignore[operator]

    def get_telemetry(self) -> TelemetryData:
        """Read current telemetry data from the autopilot.

        Reads GLOBAL_POSITION_INT, SYS_STATUS, and GPS_RAW_INT messages
        to build a complete telemetry snapshot.

        Returns:
            Current telemetry data from the autopilot.

        Raises:
            ConnectionError: If not connected to the autopilot.
            TimeoutError: If telemetry messages are not received in time.
        """
        self._require_connection()
        connection = self._get_connection()

        position = connection.recv_match(
            type="GLOBAL_POSITION_INT",
            blocking=True,
            timeout=_MESSAGE_TIMEOUT_SECONDS,
        )
        if position is None:
            raise TimeoutError("Timed out waiting for GLOBAL_POSITION_INT message")

        system_status = connection.recv_match(
            type="SYS_STATUS",
            blocking=True,
            timeout=_MESSAGE_TIMEOUT_SECONDS,
        )
        if system_status is None:
            raise TimeoutError("Timed out waiting for SYS_STATUS message")

        gps_raw = connection.recv_match(
            type="GPS_RAW_INT",
            blocking=True,
            timeout=_MESSAGE_TIMEOUT_SECONDS,
        )
        if gps_raw is None:
            raise TimeoutError("Timed out waiting for GPS_RAW_INT message")

        return TelemetryData(
            latitude=position.lat * _COORDINATE_SCALE,
            longitude=position.lon * _COORDINATE_SCALE,
            altitude=position.relative_alt / _SPEED_SCALE,
            heading=position.hdg / _HEADING_SCALE,
            ground_speed=max(0.0, position.vx / _SPEED_SCALE),
            vertical_speed=position.vz / _SPEED_SCALE,
            battery_voltage=system_status.voltage_battery / _VOLTAGE_SCALE,
            battery_remaining=system_status.battery_remaining,
            gps_fix_type=gps_raw.fix_type,
            satellites_visible=gps_raw.satellites_visible,
        )

    def arm(self) -> None:
        """Arm the autopilot motors.

        Raises:
            ConnectionError: If not connected to the autopilot.
        """
        self._require_connection()
        connection = self._get_connection()

        logger.info("Arming motors")
        connection.arducopter_arm()
        connection.motors_armed_wait()

        self._state = AutopilotState.ARMED
        logger.info("Motors armed")

    def disarm(self) -> None:
        """Disarm the autopilot motors.

        Raises:
            ConnectionError: If not connected to the autopilot.
        """
        self._require_connection()
        connection = self._get_connection()

        logger.info("Disarming motors")
        connection.arducopter_disarm()
        connection.motors_disarmed_wait()

        self._state = AutopilotState.CONNECTED
        logger.info("Motors disarmed")

    def set_mode(self, mode: str) -> None:
        """Set the autopilot flight mode.

        Args:
            mode: Flight mode name (e.g., "GUIDED", "LAND", "RTL", "LOITER").

        Raises:
            ConnectionError: If not connected to the autopilot.
            ValueError: If the mode name is not recognized.
        """
        self._require_connection()
        connection = self._get_connection()

        mode_id = connection.mode_mapping().get(mode)
        if mode_id is None:
            raise ValueError(f"Unknown flight mode: {mode}")

        logger.info("Setting flight mode to %s (id=%s)", mode, mode_id)
        connection.set_mode(mode_id)

    def goto(
        self,
        latitude: float,
        longitude: float,
        altitude: float,
    ) -> None:
        """Navigate to a GPS coordinate.

        Sends a MAV_CMD_NAV_WAYPOINT command to guide the drone to
        the specified position.

        Args:
            latitude: Target latitude in degrees.
            longitude: Target longitude in degrees.
            altitude: Target altitude in meters (relative).

        Raises:
            ConnectionError: If not connected to the autopilot.
        """
        self._require_connection()
        connection = self._get_connection()

        logger.info(
            "Navigating to lat=%.7f, lon=%.7f, alt=%.1f",
            latitude,
            longitude,
            altitude,
        )

        connection.mav.mission_item_int_send(
            connection.target_system,
            connection.target_component,
            0,  # sequence
            mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
            mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
            2,  # current (guided mode waypoint)
            1,  # autocontinue
            0,  # hold time
            0,  # acceptance radius
            0,  # pass radius
            0,  # yaw
            int(latitude / _COORDINATE_SCALE),
            int(longitude / _COORDINATE_SCALE),
            altitude,
        )

        self._state = AutopilotState.FLYING

    def takeoff(self, altitude: float) -> None:
        """Command the drone to take off to the specified altitude.

        Args:
            altitude: Target altitude in meters (relative).

        Raises:
            ConnectionError: If not connected to the autopilot.
        """
        self._require_connection()
        connection = self._get_connection()

        logger.info("Taking off to altitude %.1f meters", altitude)

        connection.mav.command_long_send(
            connection.target_system,
            connection.target_component,
            mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
            0,  # confirmation
            0,  # param1 (min pitch)
            0,  # param2
            0,  # param3
            0,  # param4 (yaw angle)
            0,  # param5 (latitude)
            0,  # param6 (longitude)
            altitude,  # param7 (altitude)
        )

        self._state = AutopilotState.FLYING
        logger.info("Takeoff command sent for altitude %.1f meters", altitude)

    def land(self) -> None:
        """Command the drone to land at the current position.

        Raises:
            ConnectionError: If not connected to the autopilot.
        """
        logger.info("Landing at current position")
        self.set_mode("LAND")
        self._state = AutopilotState.LANDING
        logger.info("Land mode engaged")

    def _require_connection(self) -> None:
        """Verify the bridge is connected to an autopilot.

        Raises:
            ConnectionError: If not connected.
        """
        if self._connection is None or self._state == AutopilotState.DISCONNECTED:
            raise ConnectionError("Not connected to autopilot. Call connect() first.")

    def _get_connection(self) -> mavfile:
        """Return the active mavlink connection.

        Returns:
            The active pymavlink connection.

        Raises:
            ConnectionError: If no active connection exists.
        """
        if self._connection is None:
            raise ConnectionError("No active MAVLink connection")
        return self._connection

    def _handle_arm(self, _command: MavlinkCommand) -> None:
        """Handle ARM command dispatch."""
        self.arm()

    def _handle_disarm(self, _command: MavlinkCommand) -> None:
        """Handle DISARM command dispatch."""
        self.disarm()

    def _handle_set_mode(self, command: MavlinkCommand) -> None:
        """Handle SET_MODE command dispatch."""
        mode = command.parameters.get("mode")
        if mode is None:
            raise ValueError("SET_MODE command requires 'mode' parameter")
        self.set_mode(str(int(mode)) if isinstance(mode, float) else str(mode))

    def _handle_takeoff(self, command: MavlinkCommand) -> None:
        """Handle TAKEOFF command dispatch."""
        altitude = command.parameters.get("altitude")
        if altitude is None:
            raise ValueError("TAKEOFF command requires 'altitude' parameter")
        self.takeoff(altitude)

    def _handle_goto(self, command: MavlinkCommand) -> None:
        """Handle GOTO command dispatch."""
        latitude = command.parameters.get("latitude")
        longitude = command.parameters.get("longitude")
        altitude = command.parameters.get("altitude")
        if latitude is None or longitude is None or altitude is None:
            raise ValueError(
                "GOTO command requires 'latitude', 'longitude', and 'altitude' parameters"
            )
        self.goto(
            latitude=latitude,
            longitude=longitude,
            altitude=altitude,
        )

    def _handle_land(self, _command: MavlinkCommand) -> None:
        """Handle LAND command dispatch."""
        self.land()

    def _handle_rtl(self, _command: MavlinkCommand) -> None:
        """Handle RTL (Return To Launch) command dispatch."""
        logger.info("Returning to launch")
        self.set_mode("RTL")
        self._state = AutopilotState.FLYING
