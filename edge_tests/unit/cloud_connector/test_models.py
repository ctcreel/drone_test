"""Tests for cloud connector data models."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from edge.cloud_connector.models import (
    CloudMessage,
    CommandMessage,
    CommandType,
    MessageDirection,
    TelemetryMessage,
)


class TestMessageDirection:
    def test_inbound_value(self):
        assert MessageDirection.INBOUND.value == "inbound"

    def test_outbound_value(self):
        assert MessageDirection.OUTBOUND.value == "outbound"

    def test_all_directions_count(self):
        assert len(MessageDirection) == 2

    def test_is_string_enum(self):
        assert isinstance(MessageDirection.INBOUND, str)
        assert MessageDirection.INBOUND == "inbound"


class TestCommandType:
    def test_mission_segment_value(self):
        assert CommandType.MISSION_SEGMENT.value == "mission_segment"

    def test_recall_value(self):
        assert CommandType.RECALL.value == "recall"

    def test_abort_value(self):
        assert CommandType.ABORT.value == "abort"

    def test_update_config_value(self):
        assert CommandType.UPDATE_CONFIG.value == "update_config"

    def test_all_command_types_count(self):
        assert len(CommandType) == 4

    def test_is_string_enum(self):
        assert isinstance(CommandType.ABORT, str)
        assert CommandType.ABORT == "abort"


class TestCloudMessage:
    def test_valid_message(self):
        message = CloudMessage(
            message_id="msg-001",
            drone_id="drone-alpha",
            direction=MessageDirection.OUTBOUND,
        )
        assert message.message_id == "msg-001"
        assert message.drone_id == "drone-alpha"
        assert message.direction == MessageDirection.OUTBOUND
        assert isinstance(message.timestamp, datetime)

    def test_custom_timestamp(self):
        custom_time = datetime(2025, 6, 15, 12, 0, 0)
        message = CloudMessage(
            message_id="msg-002",
            drone_id="drone-beta",
            direction=MessageDirection.INBOUND,
            timestamp=custom_time,
        )
        assert message.timestamp == custom_time

    def test_default_timestamp_is_set(self):
        message = CloudMessage(
            message_id="msg-003",
            drone_id="drone-gamma",
            direction=MessageDirection.OUTBOUND,
        )
        assert message.timestamp is not None
        assert isinstance(message.timestamp, datetime)

    def test_serialization_roundtrip(self):
        message = CloudMessage(
            message_id="msg-004",
            drone_id="drone-delta",
            direction=MessageDirection.INBOUND,
        )
        data = message.model_dump()
        restored = CloudMessage(**data)
        assert restored.message_id == message.message_id
        assert restored.drone_id == message.drone_id
        assert restored.direction == message.direction


class TestCommandMessage:
    def test_valid_command_message(self):
        message = CommandMessage(
            message_id="cmd-001",
            drone_id="drone-alpha",
            direction=MessageDirection.INBOUND,
            command_type=CommandType.MISSION_SEGMENT,
        )
        assert message.command_type == CommandType.MISSION_SEGMENT
        assert message.payload == {}

    def test_command_with_payload(self):
        message = CommandMessage(
            message_id="cmd-002",
            drone_id="drone-alpha",
            direction=MessageDirection.INBOUND,
            command_type=CommandType.UPDATE_CONFIG,
            payload={"key": "value", "count": 5, "enabled": True},
        )
        assert message.payload["key"] == "value"
        assert message.payload["count"] == 5
        assert message.payload["enabled"] is True

    def test_command_with_list_in_payload(self):
        message = CommandMessage(
            message_id="cmd-003",
            drone_id="drone-alpha",
            direction=MessageDirection.INBOUND,
            command_type=CommandType.MISSION_SEGMENT,
            payload={"waypoint_ids": ["wp-1", "wp-2"]},
        )
        assert message.payload["waypoint_ids"] == ["wp-1", "wp-2"]

    def test_inherits_cloud_message_fields(self):
        message = CommandMessage(
            message_id="cmd-004",
            drone_id="drone-beta",
            direction=MessageDirection.INBOUND,
            command_type=CommandType.RECALL,
        )
        assert isinstance(message.timestamp, datetime)
        assert message.message_id == "cmd-004"

    def test_all_command_types(self):
        for command_type in CommandType:
            message = CommandMessage(
                message_id=f"cmd-{command_type.value}",
                drone_id="drone-test",
                direction=MessageDirection.INBOUND,
                command_type=command_type,
            )
            assert message.command_type == command_type

    def test_payload_default_is_empty_dict(self):
        msg1 = CommandMessage(
            message_id="cmd-a",
            drone_id="drone-a",
            direction=MessageDirection.INBOUND,
            command_type=CommandType.ABORT,
        )
        msg2 = CommandMessage(
            message_id="cmd-b",
            drone_id="drone-b",
            direction=MessageDirection.INBOUND,
            command_type=CommandType.ABORT,
        )
        assert msg1.payload is not msg2.payload


class TestTelemetryMessage:
    def test_valid_telemetry_message(self):
        message = TelemetryMessage(
            message_id="tel-001",
            drone_id="drone-alpha",
            direction=MessageDirection.OUTBOUND,
            report_type="position",
            latitude=40.7128,
            longitude=-74.0060,
            altitude=50.0,
            heading=180.0,
            battery_remaining=80,
            ground_speed=5.0,
        )
        assert message.report_type == "position"
        assert message.latitude == 40.7128
        assert message.longitude == -74.0060
        assert message.altitude == 50.0
        assert message.heading == 180.0
        assert message.battery_remaining == 80
        assert message.ground_speed == 5.0

    def test_inherits_cloud_message_fields(self):
        message = TelemetryMessage(
            message_id="tel-002",
            drone_id="drone-beta",
            direction=MessageDirection.OUTBOUND,
            report_type="status",
            latitude=0.0,
            longitude=0.0,
            altitude=0.0,
            heading=0.0,
            battery_remaining=100,
            ground_speed=0.0,
        )
        assert isinstance(message.timestamp, datetime)
        assert message.direction == MessageDirection.OUTBOUND

    def test_serialization_to_json(self):
        message = TelemetryMessage(
            message_id="tel-003",
            drone_id="drone-gamma",
            direction=MessageDirection.OUTBOUND,
            report_type="position",
            latitude=40.7128,
            longitude=-74.0060,
            altitude=50.0,
            heading=180.0,
            battery_remaining=80,
            ground_speed=5.0,
        )
        json_str = message.model_dump_json()
        assert "tel-003" in json_str
        assert "drone-gamma" in json_str
        assert "position" in json_str

    def test_missing_required_field_raises(self):
        with pytest.raises(ValidationError):
            TelemetryMessage(
                message_id="tel-bad",
                drone_id="drone-bad",
                direction=MessageDirection.OUTBOUND,
                # Missing report_type and other fields
            )
