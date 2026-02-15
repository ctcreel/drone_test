"""Tests for CloudConnector with mocked paho-mqtt."""

from unittest.mock import MagicMock, call, patch

import pytest

from edge.cloud_connector.connector import _MAX_BUFFER_SIZE, _QOS_AT_LEAST_ONCE, CloudConnector
from edge.cloud_connector.models import MessageDirection, TelemetryMessage
from edge.config import ConnectivityMode, EdgeSettings


def _make_settings(**overrides):
    """Create EdgeSettings for testing."""
    defaults = {
        "drone_id": "drone-test",
        "mqtt_endpoint": "localhost",
        "mqtt_port": 1883,
        "connectivity_mode": ConnectivityMode.MOSQUITTO,
    }
    defaults.update(overrides)
    return EdgeSettings(**defaults)


def _make_telemetry_message(
    drone_id="drone-test",
    report_type="position",
):
    """Create a TelemetryMessage for testing."""
    return TelemetryMessage(
        message_id="tel-001",
        drone_id=drone_id,
        direction=MessageDirection.OUTBOUND,
        report_type=report_type,
        latitude=40.7128,
        longitude=-74.0060,
        altitude=50.0,
        heading=180.0,
        battery_remaining=80,
        ground_speed=5.0,
    )


class TestCloudConnectorInit:
    @patch("edge.cloud_connector.connector.mqtt.Client")
    def test_initial_state_not_connected(self, mock_client_class):
        settings = _make_settings()
        connector = CloudConnector(settings)
        assert connector.is_connected is False

    @patch("edge.cloud_connector.connector.mqtt.Client")
    def test_empty_message_buffer(self, mock_client_class):
        settings = _make_settings()
        connector = CloudConnector(settings)
        assert connector._message_buffer == []

    @patch("edge.cloud_connector.connector.mqtt.Client")
    def test_client_id_includes_drone_id(self, mock_client_class):
        settings = _make_settings(drone_id="alpha-007")
        CloudConnector(settings)
        mock_client_class.assert_called_once()
        call_kwargs = mock_client_class.call_args
        assert call_kwargs.kwargs["client_id"] == "drone-alpha-007"

    @patch("edge.cloud_connector.connector.mqtt.Client")
    def test_callbacks_registered(self, mock_client_class):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        settings = _make_settings()
        _connector = CloudConnector(settings)

        assert mock_client.on_connect is not None
        assert mock_client.on_disconnect is not None
        assert mock_client.on_message is not None


class TestCloudConnectorConnect:
    @patch("edge.cloud_connector.connector.mqtt.Client")
    def test_connect_mosquitto_mode(self, mock_client_class):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        settings = _make_settings(connectivity_mode=ConnectivityMode.MOSQUITTO)
        connector = CloudConnector(settings)
        connector.connect()

        mock_client.connect.assert_called_once_with(
            host="localhost",
            port=1883,
            keepalive=60,
        )
        mock_client.loop_start.assert_called_once()
        mock_client.tls_set.assert_not_called()

    @patch("edge.cloud_connector.connector.mqtt.Client")
    def test_connect_aws_iot_mode_configures_tls(self, mock_client_class):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        settings = _make_settings(
            connectivity_mode=ConnectivityMode.AWS_IOT,
            mqtt_endpoint="iot.example.com",
            mqtt_port=8883,
            certificate_path="/certs/cert.pem",
            private_key_path="/certs/key.pem",
            root_ca_path="/certs/ca.pem",
        )
        connector = CloudConnector(settings)
        connector.connect()

        mock_client.tls_set.assert_called_once()
        mock_client.connect.assert_called_once_with(
            host="iot.example.com",
            port=8883,
            keepalive=60,
        )

    @patch("edge.cloud_connector.connector.mqtt.Client")
    def test_connect_aws_iot_missing_cert_raises(self, mock_client_class):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        settings = _make_settings(
            connectivity_mode=ConnectivityMode.AWS_IOT,
            certificate_path="",
        )
        connector = CloudConnector(settings)

        with pytest.raises(FileNotFoundError, match="Certificate path"):
            connector.connect()

    @patch("edge.cloud_connector.connector.mqtt.Client")
    def test_connect_aws_iot_missing_key_raises(self, mock_client_class):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        settings = _make_settings(
            connectivity_mode=ConnectivityMode.AWS_IOT,
            certificate_path="/certs/cert.pem",
            private_key_path="",
        )
        connector = CloudConnector(settings)

        with pytest.raises(FileNotFoundError, match="Private key path"):
            connector.connect()

    @patch("edge.cloud_connector.connector.mqtt.Client")
    def test_connect_aws_iot_missing_ca_raises(self, mock_client_class):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        settings = _make_settings(
            connectivity_mode=ConnectivityMode.AWS_IOT,
            certificate_path="/certs/cert.pem",
            private_key_path="/certs/key.pem",
            root_ca_path="",
        )
        connector = CloudConnector(settings)

        with pytest.raises(FileNotFoundError, match="Root CA path"):
            connector.connect()

    @patch("edge.cloud_connector.connector.mqtt.Client")
    def test_connect_failure_raises_connection_error(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.connect.side_effect = OSError("Connection refused")
        mock_client_class.return_value = mock_client

        settings = _make_settings()
        connector = CloudConnector(settings)

        with pytest.raises(ConnectionError, match="Failed to connect to MQTT broker"):
            connector.connect()


class TestCloudConnectorDisconnect:
    @patch("edge.cloud_connector.connector.mqtt.Client")
    def test_disconnect(self, mock_client_class):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        settings = _make_settings()
        connector = CloudConnector(settings)
        connector._is_connected = True

        connector.disconnect()

        mock_client.loop_stop.assert_called_once()
        mock_client.disconnect.assert_called_once()
        assert connector.is_connected is False


class TestCloudConnectorPublishTelemetry:
    @patch("edge.cloud_connector.connector.mqtt.Client")
    def test_publish_when_connected(self, mock_client_class):
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.mid = 1
        mock_result.rc = 0
        mock_client.publish.return_value = mock_result
        mock_client_class.return_value = mock_client

        settings = _make_settings()
        connector = CloudConnector(settings)
        connector._is_connected = True

        telemetry = _make_telemetry_message()
        connector.publish_telemetry(telemetry)

        mock_client.publish.assert_called_once()
        call_kwargs = mock_client.publish.call_args.kwargs
        assert call_kwargs["topic"] == "drone/drone-test/telemetry/position"
        assert call_kwargs["qos"] == _QOS_AT_LEAST_ONCE

    @patch("edge.cloud_connector.connector.mqtt.Client")
    def test_publish_when_disconnected_buffers_message(self, mock_client_class):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        settings = _make_settings()
        connector = CloudConnector(settings)
        connector._is_connected = False

        telemetry = _make_telemetry_message()
        connector.publish_telemetry(telemetry)

        mock_client.publish.assert_not_called()
        assert len(connector._message_buffer) == 1
        topic, _payload = connector._message_buffer[0]
        assert topic == "drone/drone-test/telemetry/position"

    @patch("edge.cloud_connector.connector.mqtt.Client")
    def test_publish_topic_format(self, mock_client_class):
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.mid = 1
        mock_result.rc = 0
        mock_client.publish.return_value = mock_result
        mock_client_class.return_value = mock_client

        settings = _make_settings(drone_id="alpha-001")
        connector = CloudConnector(settings)
        connector._is_connected = True

        telemetry = _make_telemetry_message(
            drone_id="alpha-001",
            report_type="status",
        )
        connector.publish_telemetry(telemetry)

        call_kwargs = mock_client.publish.call_args.kwargs
        assert call_kwargs["topic"] == "drone/alpha-001/telemetry/status"


class TestCloudConnectorSubscribeCommands:
    @patch("edge.cloud_connector.connector.mqtt.Client")
    def test_subscribe_commands(self, mock_client_class):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        settings = _make_settings(drone_id="alpha-001")
        connector = CloudConnector(settings)

        callback = MagicMock()
        connector.subscribe_commands(callback)

        mock_client.subscribe.assert_called_once_with(
            topic="drone/alpha-001/command/#",
            qos=_QOS_AT_LEAST_ONCE,
        )
        assert connector._command_callback is callback


class TestCloudConnectorMessageBuffering:
    @patch("edge.cloud_connector.connector.mqtt.Client")
    def test_buffer_multiple_messages(self, mock_client_class):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        settings = _make_settings()
        connector = CloudConnector(settings)
        connector._is_connected = False

        for i in range(5):
            telemetry = _make_telemetry_message()
            telemetry.message_id = f"tel-{i:03d}"
            connector.publish_telemetry(telemetry)

        assert len(connector._message_buffer) == 5

    @patch("edge.cloud_connector.connector.mqtt.Client")
    def test_buffer_overflow_drops_oldest(self, mock_client_class):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        settings = _make_settings()
        connector = CloudConnector(settings)
        connector._is_connected = False

        # Fill the buffer to capacity
        for i in range(_MAX_BUFFER_SIZE):
            connector._buffer_message(
                topic=f"topic/{i}",
                payload=f"payload-{i}",
            )

        assert len(connector._message_buffer) == _MAX_BUFFER_SIZE

        # Add one more - should drop the oldest
        connector._buffer_message(topic="topic/overflow", payload="payload-overflow")

        assert len(connector._message_buffer) == _MAX_BUFFER_SIZE
        # The first message (topic/0) should be dropped
        assert connector._message_buffer[0][0] == "topic/1"
        assert connector._message_buffer[-1][0] == "topic/overflow"


class TestCloudConnectorDrainBuffer:
    @patch("edge.cloud_connector.connector.mqtt.Client")
    def test_drain_buffer_on_connect(self, mock_client_class):
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.mid = 1
        mock_result.rc = 0
        mock_client.publish.return_value = mock_result
        mock_client_class.return_value = mock_client

        settings = _make_settings()
        connector = CloudConnector(settings)
        connector._is_connected = False

        # Buffer some messages
        connector._buffer_message(topic="topic/1", payload="payload-1")
        connector._buffer_message(topic="topic/2", payload="payload-2")
        assert len(connector._message_buffer) == 2

        # Simulate reconnection by setting connected and draining directly
        connector._is_connected = True
        connector._drain_buffer()

        # Buffer should be drained
        assert len(connector._message_buffer) == 0
        assert mock_client.publish.call_count == 2

        # Verify messages were published in order
        expected_calls = [
            call(topic="topic/1", payload="payload-1", qos=_QOS_AT_LEAST_ONCE),
            call(topic="topic/2", payload="payload-2", qos=_QOS_AT_LEAST_ONCE),
        ]
        mock_client.publish.assert_has_calls(expected_calls)

    @patch("edge.cloud_connector.connector.mqtt.Client")
    def test_drain_empty_buffer_is_noop(self, mock_client_class):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        settings = _make_settings()
        connector = CloudConnector(settings)

        connector._drain_buffer()

        mock_client.publish.assert_not_called()


class TestCloudConnectorOnDisconnect:
    @patch("edge.cloud_connector.connector.mqtt.Client")
    def test_on_disconnect_sets_not_connected(self, mock_client_class):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        settings = _make_settings()
        connector = CloudConnector(settings)
        connector._is_connected = True

        connector._on_disconnect(
            mock_client, None, MagicMock(), MagicMock(), None,
        )

        assert connector.is_connected is False


class TestCloudConnectorOnMessage:
    @patch("edge.cloud_connector.connector.mqtt.Client")
    def test_on_message_dispatches_to_callback(self, mock_client_class):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        settings = _make_settings()
        connector = CloudConnector(settings)

        callback = MagicMock()
        connector._command_callback = callback

        mock_message = MagicMock()
        mock_message.topic = "drone/drone-test/command/mission"
        mock_message.payload = b'{"command": "go"}'

        connector._on_message(mock_client, None, mock_message)

        callback.assert_called_once_with(
            "drone/drone-test/command/mission",
            b'{"command": "go"}',
        )

    @patch("edge.cloud_connector.connector.mqtt.Client")
    def test_on_message_no_callback_does_not_raise(self, mock_client_class):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        settings = _make_settings()
        connector = CloudConnector(settings)
        connector._command_callback = None

        mock_message = MagicMock()
        mock_message.topic = "drone/drone-test/command/test"
        mock_message.payload = b"{}"

        # Should not raise
        connector._on_message(mock_client, None, mock_message)

    @patch("edge.cloud_connector.connector.mqtt.Client")
    def test_on_message_callback_exception_handled(self, mock_client_class):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        settings = _make_settings()
        connector = CloudConnector(settings)

        callback = MagicMock(side_effect=RuntimeError("Callback error"))
        connector._command_callback = callback

        mock_message = MagicMock()
        mock_message.topic = "test/topic"
        mock_message.payload = b"{}"

        # Should not raise even though callback throws
        connector._on_message(mock_client, None, mock_message)
