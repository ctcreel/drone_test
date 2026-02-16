"""Mission executor for sequencing waypoints from cloud mission segments.

Receives mission segments from the cloud tier, sequences waypoints to the
MAVLink bridge, and reports progress. All operations are deterministic
and suitable for edge deployment.
"""

from __future__ import annotations

import logging
import math
import time
from typing import TYPE_CHECKING

from edge.mission_executor.models import ExecutorState, WaypointProgress

if TYPE_CHECKING:
    from edge.config import EdgeSettings
    from edge.mavlink_bridge.bridge import MavlinkBridge
    from edge.mavlink_bridge.models import TelemetryData
    from edge.mission_executor.models import MissionSegment, Waypoint

logger = logging.getLogger(__name__)

# Navigation constants
_EARTH_RADIUS_METERS: float = 6_371_000.0
_DEFAULT_ARRIVAL_THRESHOLD_METERS: float = 2.0
_NAVIGATION_POLL_INTERVAL_SECONDS: float = 0.5
_DEGREES_TO_RADIANS: float = math.pi / 180.0


class MissionExecutor:
    """Executes mission segments by sequencing waypoints to MAVLink.

    Receives mission segments from the cloud, iterates through waypoints,
    commands the autopilot via the MAVLink bridge, and tracks progress.
    Supports pause, resume, and abort operations.

    The current segment is cached locally for connectivity loss resilience.
    """

    def __init__(
        self,
        bridge: MavlinkBridge,
        settings: EdgeSettings,
    ) -> None:
        """Initialize the mission executor.

        Args:
            bridge: MAVLink bridge for autopilot communication.
            settings: Edge tier configuration.
        """
        self._bridge = bridge
        self._settings = settings
        self._state = ExecutorState.IDLE
        self._current_segment: MissionSegment | None = None
        self._current_waypoint_index: int = 0
        self._arrival_threshold_meters = _DEFAULT_ARRIVAL_THRESHOLD_METERS

    @property
    def state(self) -> ExecutorState:
        """Return the current executor state."""
        return self._state

    def load_segment(self, segment: MissionSegment) -> None:
        """Load a mission segment for execution.

        Transitions the executor from IDLE to LOADING, validates the segment,
        then transitions to EXECUTING.

        Args:
            segment: Mission segment containing waypoints to execute.

        Raises:
            RuntimeError: If the executor is not in IDLE state.
            ValueError: If the segment contains no waypoints.
        """
        if self._state not in (ExecutorState.IDLE, ExecutorState.COMPLETED, ExecutorState.ABORTED):
            raise RuntimeError(
                f"Cannot load segment in state {self._state}. "
                f"Executor must be in IDLE, COMPLETED, or ABORTED state."
            )

        if not segment.waypoints:
            raise ValueError(f"Mission segment {segment.segment_id} contains no waypoints")

        logger.info(
            "Loading mission segment %s (%d waypoints) for mission %s",
            segment.segment_id,
            len(segment.waypoints),
            segment.mission_id,
        )

        self._state = ExecutorState.LOADING
        self._current_segment = segment
        self._current_waypoint_index = 0
        self._state = ExecutorState.EXECUTING

        logger.info("Mission segment %s loaded and ready for execution", segment.segment_id)

    def execute(self) -> None:
        """Execute the loaded mission segment.

        Iterates through all waypoints in the segment, navigating to each
        in sequence. Reports progress after each waypoint.

        Raises:
            RuntimeError: If the executor is not in EXECUTING state.
        """
        if self._state != ExecutorState.EXECUTING:
            raise RuntimeError(f"Cannot execute in state {self._state}")

        segment = self._require_segment()

        logger.info(
            "Beginning execution of segment %s (%d waypoints)",
            segment.segment_id,
            len(segment.waypoints),
        )

        while self._current_waypoint_index < len(segment.waypoints):
            if self._state == ExecutorState.PAUSED:
                logger.info("Execution paused at waypoint %d", self._current_waypoint_index)
                return

            if self._state == ExecutorState.ABORTED:
                logger.info("Execution aborted at waypoint %d", self._current_waypoint_index)
                return

            waypoint = segment.waypoints[self._current_waypoint_index]

            logger.info(
                "Navigating to waypoint %d/%d (lat=%.7f, lon=%.7f, alt=%.1f)",
                self._current_waypoint_index + 1,
                len(segment.waypoints),
                waypoint.latitude,
                waypoint.longitude,
                waypoint.altitude,
            )

            self._navigate_to_waypoint(waypoint)

            if waypoint.loiter_time_seconds > 0:
                logger.info(
                    "Loitering at waypoint %d for %d seconds",
                    self._current_waypoint_index + 1,
                    waypoint.loiter_time_seconds,
                )
                time.sleep(waypoint.loiter_time_seconds)

            self._current_waypoint_index += 1

        self._state = ExecutorState.COMPLETED
        logger.info("Mission segment %s completed", segment.segment_id)

    def pause(self) -> None:
        """Pause mission execution.

        The drone will hold its current position. Execution can be
        resumed with resume().

        Raises:
            RuntimeError: If the executor is not in EXECUTING state.
        """
        if self._state != ExecutorState.EXECUTING:
            raise RuntimeError(f"Cannot pause in state {self._state}")

        self._state = ExecutorState.PAUSED
        self._bridge.set_mode("LOITER")
        logger.info(
            "Mission execution paused at waypoint %d",
            self._current_waypoint_index,
        )

    def resume(self) -> None:
        """Resume paused mission execution.

        Raises:
            RuntimeError: If the executor is not in PAUSED state.
        """
        if self._state != ExecutorState.PAUSED:
            raise RuntimeError(f"Cannot resume in state {self._state}")

        self._state = ExecutorState.EXECUTING
        logger.info(
            "Mission execution resumed at waypoint %d",
            self._current_waypoint_index,
        )

    def abort(self) -> None:
        """Abort mission execution.

        Commands the drone to hold position. The mission cannot be
        resumed after abort.

        Raises:
            RuntimeError: If the executor is in IDLE state.
        """
        if self._state == ExecutorState.IDLE:
            raise RuntimeError("Cannot abort: no mission is loaded")

        previous_state = self._state
        self._state = ExecutorState.ABORTED
        self._bridge.set_mode("LOITER")

        logger.warning(
            "Mission execution aborted (was in state %s at waypoint %d)",
            previous_state,
            self._current_waypoint_index,
        )

    def get_progress(self) -> WaypointProgress:
        """Return current progress through the mission segment.

        Returns:
            Progress information including current waypoint and distance.

        Raises:
            RuntimeError: If no mission segment is loaded.
        """
        segment = self._require_segment()

        distance_to_next = 0.0
        if self._current_waypoint_index < len(segment.waypoints):
            try:
                telemetry = self._bridge.get_telemetry()
                target = segment.waypoints[self._current_waypoint_index]
                distance_to_next = _haversine_distance(
                    latitude_1=telemetry.latitude,
                    longitude_1=telemetry.longitude,
                    latitude_2=target.latitude,
                    longitude_2=target.longitude,
                )
            except (ConnectionError, TimeoutError):
                logger.warning("Could not get telemetry for progress calculation")

        remaining_waypoints = len(segment.waypoints) - self._current_waypoint_index
        estimated_time = remaining_waypoints * 30.0  # rough estimate: 30s per waypoint

        return WaypointProgress(
            segment_id=segment.segment_id,
            current_waypoint_index=self._current_waypoint_index,
            total_waypoints=len(segment.waypoints),
            distance_to_next_meters=distance_to_next,
            estimated_time_remaining_seconds=estimated_time,
        )

    def _navigate_to_waypoint(self, waypoint: Waypoint) -> None:
        """Navigate to a waypoint and wait for arrival.

        Sends a goto command and polls telemetry until the drone is
        within the arrival threshold of the target.

        Args:
            waypoint: Target waypoint to navigate to.
        """
        self._bridge.goto(
            latitude=waypoint.latitude,
            longitude=waypoint.longitude,
            altitude=waypoint.altitude,
        )

        while True:
            if self._state in (ExecutorState.PAUSED, ExecutorState.ABORTED):
                return

            try:
                telemetry = self._bridge.get_telemetry()
            except (ConnectionError, TimeoutError):
                logger.warning("Telemetry read failed during navigation, retrying")
                time.sleep(_NAVIGATION_POLL_INTERVAL_SECONDS)
                continue

            if self._has_arrived(
                target=waypoint,
                current=telemetry,
                threshold=self._arrival_threshold_meters,
            ):
                logger.info(
                    "Arrived at waypoint (lat=%.7f, lon=%.7f)",
                    waypoint.latitude,
                    waypoint.longitude,
                )
                return

            time.sleep(_NAVIGATION_POLL_INTERVAL_SECONDS)

    def _has_arrived(
        self,
        target: Waypoint,
        current: TelemetryData,
        threshold: float,
    ) -> bool:
        """Check if the drone has arrived at the target waypoint.

        Uses the Haversine formula to compute the horizontal distance
        between the current position and the target.

        Args:
            target: Target waypoint coordinates.
            current: Current telemetry position.
            threshold: Arrival distance threshold in meters.

        Returns:
            True if the drone is within the threshold of the target.
        """
        distance = _haversine_distance(
            latitude_1=current.latitude,
            longitude_1=current.longitude,
            latitude_2=target.latitude,
            longitude_2=target.longitude,
        )
        return distance <= threshold

    def _require_segment(self) -> MissionSegment:
        """Return the current segment or raise if none is loaded.

        Returns:
            The currently loaded mission segment.

        Raises:
            RuntimeError: If no segment is loaded.
        """
        if self._current_segment is None:
            raise RuntimeError("No mission segment is loaded")
        return self._current_segment


def _haversine_distance(
    *,
    latitude_1: float,
    longitude_1: float,
    latitude_2: float,
    longitude_2: float,
) -> float:
    """Compute the Haversine distance between two GPS coordinates.

    Args:
        latitude_1: First point latitude in degrees.
        longitude_1: First point longitude in degrees.
        latitude_2: Second point latitude in degrees.
        longitude_2: Second point longitude in degrees.

    Returns:
        Distance between the two points in meters.
    """
    delta_latitude = (latitude_2 - latitude_1) * _DEGREES_TO_RADIANS
    delta_longitude = (longitude_2 - longitude_1) * _DEGREES_TO_RADIANS

    latitude_1_radians = latitude_1 * _DEGREES_TO_RADIANS
    latitude_2_radians = latitude_2 * _DEGREES_TO_RADIANS

    haversine = (
        math.sin(delta_latitude / 2.0) ** 2
        + math.cos(latitude_1_radians)
        * math.cos(latitude_2_radians)
        * math.sin(delta_longitude / 2.0) ** 2
    )
    angular_distance = 2.0 * math.atan2(math.sqrt(haversine), math.sqrt(1.0 - haversine))

    return _EARTH_RADIUS_METERS * angular_distance
