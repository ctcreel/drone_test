"""Edge application entry point.

Wires up all edge tier components and runs the main event loop:
MAVLink bridge, cloud connector, mission executor, fail-safe manager,
obstacle avoidance, and image pipeline.
"""

from __future__ import annotations

import asyncio
import json
import logging
import signal
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from edge.cloud_connector.connector import CloudConnector
from edge.cloud_connector.models import CommandType, MessageDirection, TelemetryMessage
from edge.config import get_edge_settings
from edge.image_pipeline.pipeline import ImagePipeline
from edge.mavlink_bridge.bridge import MavlinkBridge
from edge.mission_executor.executor import MissionExecutor
from edge.mission_executor.fail_safe import FailSafeManager
from edge.mission_executor.models import MissionSegment
from edge.obstacle_avoidance.avoidance import ObstacleAvoidance

if TYPE_CHECKING:
    from edge.config import EdgeSettings

logger = logging.getLogger(__name__)

_MAIN_LOOP_INTERVAL_SECONDS: float = 0.1
_SHUTDOWN_TIMEOUT_SECONDS: float = 10.0


class EdgeApplication:
    """Edge application that orchestrates all edge tier components.

    Wires together the MAVLink bridge, cloud connector, mission executor,
    fail-safe manager, obstacle avoidance, and image pipeline into a
    single coordinated runtime.
    """

    def __init__(self, settings: EdgeSettings) -> None:
        """Initialize the edge application with all components.

        Args:
            settings: Edge tier configuration.
        """
        self._settings = settings
        self._running = False

        # Core components
        self._bridge = MavlinkBridge(
            connection_string=settings.mavlink_connection,
            baud_rate=settings.mavlink_baud_rate,
        )
        self._connector = CloudConnector(settings=settings)
        self._executor = MissionExecutor(
            bridge=self._bridge,
            settings=settings,
        )
        self._fail_safe = FailSafeManager(settings=settings)
        self._obstacle_avoidance = ObstacleAvoidance(settings=settings)
        self._image_pipeline = ImagePipeline(settings=settings)

        # Timing trackers
        self._last_telemetry_time: float = 0.0
        self._last_image_capture_time: float = 0.0

    async def run(self) -> None:
        """Run the edge application main loop.

        Connects all components, subscribes to cloud commands, and enters
        the main event loop that:
        1. Reports telemetry at the configured interval.
        2. Updates fail-safe state based on connectivity.
        3. Processes the image upload queue.
        4. Yields control to the async event loop.

        Raises:
            ConnectionError: If initial connections fail.
        """
        self._running = True
        logger.info("Starting edge application for drone %s", self._settings.drone_id)

        self._connect_components()
        self._connector.subscribe_commands(callback=self._handle_command)

        logger.info("Edge application started, entering main loop")

        try:
            while self._running:
                await self._main_loop_iteration()
                await asyncio.sleep(_MAIN_LOOP_INTERVAL_SECONDS)
        except asyncio.CancelledError:
            logger.info("Edge application cancelled")
        finally:
            self._shutdown()

    def stop(self) -> None:
        """Signal the edge application to stop."""
        logger.info("Stop signal received")
        self._running = False

    def _connect_components(self) -> None:
        """Connect MAVLink bridge and cloud connector.

        Raises:
            ConnectionError: If either connection fails.
        """
        logger.info("Connecting MAVLink bridge")
        self._bridge.connect()

        logger.info("Connecting cloud connector")
        self._connector.connect()

    def _shutdown(self) -> None:
        """Gracefully shut down all components."""
        logger.info("Shutting down edge application")

        self._connector.disconnect()
        self._bridge.disconnect()

        logger.info("Edge application shut down complete")

    async def _main_loop_iteration(self) -> None:
        """Execute one iteration of the main event loop."""
        loop = asyncio.get_event_loop()
        current_time = loop.time()

        # Update fail-safe state
        self._fail_safe.update_connectivity(is_connected=self._connector.is_connected)
        self._handle_fail_safe_state()

        # Report telemetry at configured interval
        telemetry_interval = self._settings.telemetry_report_interval_seconds
        if current_time - self._last_telemetry_time >= telemetry_interval:
            self._report_telemetry()
            self._last_telemetry_time = current_time

        # Process image upload queue
        self._image_pipeline.process_upload_queue()

    def _report_telemetry(self) -> None:
        """Read telemetry from MAVLink and publish to cloud."""
        try:
            telemetry = self._bridge.get_telemetry()
        except (ConnectionError, TimeoutError):
            logger.warning("Failed to read telemetry from autopilot")
            return

        message = TelemetryMessage(
            message_id=f"telem-{self._settings.drone_id}-{int(datetime.now(tz=UTC).timestamp())}",
            timestamp=datetime.now(tz=UTC),
            drone_id=self._settings.drone_id,
            direction=MessageDirection.OUTBOUND,
            report_type="position",
            latitude=telemetry.latitude,
            longitude=telemetry.longitude,
            altitude=telemetry.altitude,
            heading=telemetry.heading,
            battery_remaining=telemetry.battery_remaining,
            ground_speed=telemetry.ground_speed,
        )

        self._connector.publish_telemetry(telemetry=message)

    def _handle_fail_safe_state(self) -> None:
        """React to fail-safe state changes."""
        if self._fail_safe.should_return():
            logger.warning("Fail-safe: returning to launch")
            self._executor.abort()
            self._bridge.set_mode("RTL")
        elif self._fail_safe.should_hold():
            logger.warning("Fail-safe: holding position")
            self._bridge.set_mode("LOITER")

    def _handle_command(self, topic: str, payload: bytes) -> None:
        """Handle an incoming command from the cloud.

        Dispatches commands based on their type:
        - MISSION_SEGMENT: Load and execute a new mission segment.
        - RECALL: Return to launch.
        - ABORT: Abort current mission.

        Args:
            topic: MQTT topic the command was received on.
            payload: JSON-encoded command payload.
        """
        logger.info("Received command on topic: %s", topic)

        try:
            command_data = json.loads(payload)
        except json.JSONDecodeError:
            logger.exception("Failed to parse command payload from topic %s", topic)
            return

        command_type = command_data.get("command_type", "")

        if command_type == CommandType.MISSION_SEGMENT:
            self._handle_mission_segment(command_data=command_data)
        elif command_type == CommandType.RECALL:
            logger.info("Recall command received, returning to launch")
            self._bridge.set_mode("RTL")
        elif command_type == CommandType.ABORT:
            logger.warning("Abort command received")
            self._executor.abort()
        elif command_type == CommandType.UPDATE_CONFIG:
            logger.info("Config update command received (not yet implemented)")
        else:
            logger.warning("Unknown command type: %s", command_type)

    def _handle_mission_segment(self, command_data: dict[str, object]) -> None:
        """Handle a mission segment command from the cloud.

        Args:
            command_data: Parsed command data containing segment details.
        """
        try:
            payload = command_data.get("payload", {})
            if not isinstance(payload, dict):
                logger.warning("Mission segment payload is not a dictionary")
                return

            segment = MissionSegment.model_validate(payload)
            self._executor.load_segment(segment=segment)
            self._executor.execute()
        except Exception:
            logger.exception("Failed to load and execute mission segment")


async def run_edge(settings: EdgeSettings) -> None:
    """Main entry point for the edge application.

    Creates and runs the edge application with signal handling for
    graceful shutdown.

    Args:
        settings: Edge tier configuration.
    """
    application = EdgeApplication(settings=settings)

    loop = asyncio.get_event_loop()

    def signal_handler() -> None:
        logger.info("Received shutdown signal")
        application.stop()

    for signal_name in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(signal_name, signal_handler)

    await application.run()


def main() -> None:
    """CLI entry point: load settings and run the async event loop."""
    settings = get_edge_settings()

    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    logger.info(
        "Starting edge application (drone_id=%s, mavlink=%s, mqtt=%s:%d)",
        settings.drone_id,
        settings.mavlink_connection,
        settings.mqtt_endpoint,
        settings.mqtt_port,
    )

    asyncio.run(run_edge(settings=settings))


if __name__ == "__main__":
    main()
