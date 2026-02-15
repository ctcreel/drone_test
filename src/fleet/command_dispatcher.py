"""IoT Core command dispatcher for drone fleet."""

import json
import os
from datetime import UTC, datetime
from typing import Any

import boto3

from src.constants import MQTT_TOPIC_PREFIX
from src.exceptions.server_errors import ExternalServiceError


class CommandDispatcher:
    """Dispatches commands to drones via IoT Core MQTT."""

    def __init__(self) -> None:
        """Initialize the command dispatcher."""
        endpoint = os.environ.get("IOT_ENDPOINT", "")
        self._client = boto3.client(  # type: ignore[call-overload]
            "iot-data",
            endpoint_url=f"https://{endpoint}" if endpoint else None,
        )

    def _publish(self, topic: str, payload: dict[str, Any]) -> None:
        """Publish a message to an MQTT topic.

        Args:
            topic: MQTT topic path.
            payload: Message payload.

        Raises:
            ExternalServiceError: If publish fails.
        """
        envelope: dict[str, Any] = {
            "version": "1.0",
            "timestamp": datetime.now(UTC).isoformat(),
            "source": "cloud",
            **payload,
        }
        try:
            self._client.publish(
                topic=topic,
                qos=1,
                payload=json.dumps(envelope),
            )
        except Exception as error:
            raise ExternalServiceError(
                f"Failed to publish to {topic}: {error}",
                service_name="iot-core",
            ) from error

    def dispatch_mission_segment(
        self,
        drone_id: str,
        mission_id: str,
        segment_data: dict[str, Any],
    ) -> None:
        """Send a mission segment to a drone.

        Args:
            drone_id: Target drone identifier.
            mission_id: Mission identifier.
            segment_data: Flight segment data with waypoints.
        """
        topic = f"{MQTT_TOPIC_PREFIX}/{drone_id}/command/mission"
        self._publish(topic, {
            "command_type": "mission_segment",
            "mission_id": mission_id,
            "segment": segment_data,
        })

    def recall_drone(self, drone_id: str) -> None:
        """Send emergency recall command to a drone.

        Args:
            drone_id: Target drone identifier.
        """
        topic = f"{MQTT_TOPIC_PREFIX}/{drone_id}/command/recall"
        self._publish(topic, {
            "command_type": "recall",
            "drone_id": drone_id,
        })

    def broadcast_fleet_recall(self) -> None:
        """Broadcast emergency recall to all drones."""
        topic = f"{MQTT_TOPIC_PREFIX}/fleet/broadcast/recall"
        self._publish(topic, {
            "command_type": "fleet_recall",
        })
