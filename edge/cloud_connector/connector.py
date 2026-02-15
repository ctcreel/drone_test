"""MQTT cloud connector for AWS IoT Core and Mosquitto.

Provides connectivity to the cloud tier over MQTT, supporting both
TLS-secured AWS IoT Core and plain Mosquitto broker connections.
Messages are buffered during connectivity loss and drained on reconnect.
"""

from __future__ import annotations

import logging
import ssl
from typing import TYPE_CHECKING

import paho.mqtt.client as mqtt

from edge.config import ConnectivityMode

if TYPE_CHECKING:
    from collections.abc import Callable

    from edge.cloud_connector.models import TelemetryMessage
    from edge.config import EdgeSettings

logger = logging.getLogger(__name__)

_KEEPALIVE_SECONDS: int = 60
_MAX_BUFFER_SIZE: int = 1000
_QOS_AT_LEAST_ONCE: int = 1


class CloudConnector:
    """MQTT cloud connector for drone-to-cloud communication.

    Supports both AWS IoT Core (TLS mutual authentication) and local
    Mosquitto (plain TCP) connections. Buffers outbound messages during
    connectivity loss and drains the buffer upon reconnection.
    """

    def __init__(self, settings: EdgeSettings) -> None:
        """Initialize the cloud connector.

        Args:
            settings: Edge tier configuration with MQTT broker details.
        """
        self._settings = settings
        self._drone_id = settings.drone_id
        self._is_connected = False
        self._message_buffer: list[tuple[str, str]] = []
        self._command_callback: Callable[[str, bytes], None] | None = None

        self._client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"drone-{self._drone_id}",
            protocol=mqtt.MQTTv311,
        )
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

    @property
    def is_connected(self) -> bool:
        """Return whether the connector is currently connected to the broker."""
        return self._is_connected

    def connect(self) -> None:
        """Connect to the MQTT broker.

        Configures TLS for AWS IoT Core mode or plain TCP for Mosquitto mode,
        then establishes the connection.

        Raises:
            ConnectionError: If the connection to the broker fails.
        """
        logger.info(
            "Connecting to MQTT broker at %s:%d (mode=%s)",
            self._settings.mqtt_endpoint,
            self._settings.mqtt_port,
            self._settings.connectivity_mode,
        )

        if self._settings.connectivity_mode == ConnectivityMode.AWS_IOT:
            self._configure_tls()

        try:
            self._client.connect(
                host=self._settings.mqtt_endpoint,
                port=self._settings.mqtt_port,
                keepalive=_KEEPALIVE_SECONDS,
            )
            self._client.loop_start()
        except Exception as error:
            logger.exception("Failed to connect to MQTT broker")
            raise ConnectionError(
                f"Failed to connect to MQTT broker at "
                f"{self._settings.mqtt_endpoint}:{self._settings.mqtt_port}: {error}"
            ) from error

        logger.info("MQTT connection initiated for drone %s", self._drone_id)

    def disconnect(self) -> None:
        """Disconnect from the MQTT broker gracefully."""
        logger.info("Disconnecting from MQTT broker")
        self._client.loop_stop()
        self._client.disconnect()
        self._is_connected = False
        logger.info("Disconnected from MQTT broker")

    def publish_telemetry(self, telemetry: TelemetryMessage) -> None:
        """Publish telemetry data to the cloud.

        Publishes to the topic: drone/{drone_id}/telemetry/{report_type}.
        If not connected, the message is buffered for later delivery.

        Args:
            telemetry: Telemetry message to publish.
        """
        topic = f"drone/{self._drone_id}/telemetry/{telemetry.report_type}"
        payload = telemetry.model_dump_json()

        if not self._is_connected:
            logger.warning("Not connected, buffering telemetry message (topic=%s)", topic)
            self._buffer_message(topic=topic, payload=payload)
            return

        result = self._client.publish(
            topic=topic,
            payload=payload,
            qos=_QOS_AT_LEAST_ONCE,
        )
        logger.debug(
            "Published telemetry to %s (mid=%d, rc=%d)",
            topic,
            result.mid,
            result.rc,
        )

    def subscribe_commands(self, callback: Callable[[str, bytes], None]) -> None:
        """Subscribe to command topics from the cloud.

        Subscribes to drone/{drone_id}/command/# to receive all command
        types for this drone.

        Args:
            callback: Function called with (topic, payload) for each command.
        """
        self._command_callback = callback
        command_topic = f"drone/{self._drone_id}/command/#"

        self._client.subscribe(
            topic=command_topic,
            qos=_QOS_AT_LEAST_ONCE,
        )
        logger.info("Subscribed to command topic: %s", command_topic)

    def _configure_tls(self) -> None:
        """Configure TLS for AWS IoT Core mutual authentication.

        Raises:
            FileNotFoundError: If certificate files are not found.
        """
        logger.info("Configuring TLS for AWS IoT Core")

        if not self._settings.certificate_path:
            raise FileNotFoundError("Certificate path is required for AWS IoT Core mode")
        if not self._settings.private_key_path:
            raise FileNotFoundError("Private key path is required for AWS IoT Core mode")
        if not self._settings.root_ca_path:
            raise FileNotFoundError("Root CA path is required for AWS IoT Core mode")

        self._client.tls_set(
            ca_certs=self._settings.root_ca_path,
            certfile=self._settings.certificate_path,
            keyfile=self._settings.private_key_path,
            cert_reqs=ssl.CERT_REQUIRED,
            tls_version=ssl.PROTOCOL_TLSv1_2,
        )

    def _on_connect(
        self,
        _client: mqtt.Client,
        _userdata: object,
        _flags: mqtt.ConnectFlags,
        reason_code: mqtt.ReasonCode,
        _properties: mqtt.Properties | None,
    ) -> None:
        """Handle successful MQTT connection.

        Drains any buffered messages that accumulated during disconnection.
        """
        if reason_code == mqtt.ReasonCode(mqtt.ReasonCodes.SUCCESS):
            self._is_connected = True
            logger.info("Connected to MQTT broker (rc=%s)", reason_code)
            self._drain_buffer()
        else:
            self._is_connected = False
            logger.warning("MQTT connection failed with reason code: %s", reason_code)

    def _on_disconnect(
        self,
        _client: mqtt.Client,
        _userdata: object,
        _flags: mqtt.DisconnectFlags,
        reason_code: mqtt.ReasonCode,
        _properties: mqtt.Properties | None,
    ) -> None:
        """Handle MQTT disconnection."""
        self._is_connected = False
        logger.warning("Disconnected from MQTT broker (rc=%s)", reason_code)

    def _on_message(
        self,
        _client: mqtt.Client,
        _userdata: object,
        message: mqtt.MQTTMessage,
    ) -> None:
        """Handle incoming MQTT message.

        Dispatches to the registered command callback if available.
        """
        logger.debug("Received message on topic: %s", message.topic)

        if self._command_callback is not None:
            try:
                self._command_callback(message.topic, message.payload)
            except Exception:
                logger.exception(
                    "Error in command callback for topic %s",
                    message.topic,
                )

    def _buffer_message(self, *, topic: str, payload: str) -> None:
        """Buffer a message for later delivery.

        Drops the oldest message if the buffer is full.

        Args:
            topic: MQTT topic for the message.
            payload: JSON-serialized message payload.
        """
        if len(self._message_buffer) >= _MAX_BUFFER_SIZE:
            dropped_topic, _ = self._message_buffer.pop(0)
            logger.warning(
                "Message buffer full (%d), dropped oldest message (topic=%s)",
                _MAX_BUFFER_SIZE,
                dropped_topic,
            )

        self._message_buffer.append((topic, payload))
        logger.debug(
            "Buffered message (topic=%s, buffer_size=%d)",
            topic,
            len(self._message_buffer),
        )

    def _drain_buffer(self) -> None:
        """Publish all buffered messages after reconnection."""
        if not self._message_buffer:
            return

        buffer_size = len(self._message_buffer)
        logger.info("Draining %d buffered messages", buffer_size)

        messages_to_send = list(self._message_buffer)
        self._message_buffer.clear()

        for topic, payload in messages_to_send:
            result = self._client.publish(
                topic=topic,
                payload=payload,
                qos=_QOS_AT_LEAST_ONCE,
            )
            logger.debug(
                "Drained buffered message to %s (mid=%d, rc=%d)",
                topic,
                result.mid,
                result.rc,
            )

        logger.info("Drained %d buffered messages", buffer_size)
