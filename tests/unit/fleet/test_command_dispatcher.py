"""Tests for fleet command dispatcher."""

from unittest.mock import MagicMock, patch

import pytest

from src.exceptions.server_errors import ExternalServiceError
from src.fleet.command_dispatcher import CommandDispatcher


class TestCommandDispatcher:
    """Tests for CommandDispatcher."""

    @patch("src.fleet.command_dispatcher.boto3")
    def test_dispatch_mission_segment(self, mock_boto3: MagicMock) -> None:
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client

        dispatcher = CommandDispatcher()
        dispatcher.dispatch_mission_segment(
            drone_id="d-001",
            mission_id="m-001",
            segment_data={"waypoints": []},
        )
        mock_client.publish.assert_called_once()
        call_args = mock_client.publish.call_args
        assert "d-001/command/mission" in call_args.kwargs["topic"]

    @patch("src.fleet.command_dispatcher.boto3")
    def test_recall_drone(self, mock_boto3: MagicMock) -> None:
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client

        dispatcher = CommandDispatcher()
        dispatcher.recall_drone("d-002")
        mock_client.publish.assert_called_once()
        call_args = mock_client.publish.call_args
        assert "d-002/command/recall" in call_args.kwargs["topic"]

    @patch("src.fleet.command_dispatcher.boto3")
    def test_broadcast_fleet_recall(self, mock_boto3: MagicMock) -> None:
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client

        dispatcher = CommandDispatcher()
        dispatcher.broadcast_fleet_recall()
        mock_client.publish.assert_called_once()
        call_args = mock_client.publish.call_args
        assert "fleet/broadcast/recall" in call_args.kwargs["topic"]

    @patch("src.fleet.command_dispatcher.boto3")
    def test_publish_failure_raises(self, mock_boto3: MagicMock) -> None:
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.publish.side_effect = Exception("Connection refused")

        dispatcher = CommandDispatcher()
        with pytest.raises(ExternalServiceError):
            dispatcher.recall_drone("d-003")
