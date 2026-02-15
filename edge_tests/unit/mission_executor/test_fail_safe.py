"""Tests for FailSafeManager state machine."""

from unittest.mock import patch

import pytest

from edge.config import EdgeSettings
from edge.mission_executor.fail_safe import FailSafeManager, FailSafeState


def _make_settings(**overrides):
    """Create EdgeSettings for testing."""
    defaults = {
        "drone_id": "drone-test",
        "degraded_threshold_seconds": 10,
        "holding_threshold_seconds": 30,
        "return_threshold_seconds": 120,
    }
    defaults.update(overrides)
    return EdgeSettings(**defaults)


class TestFailSafeState:
    def test_connected_value(self):
        assert FailSafeState.CONNECTED.value == "connected"

    def test_degraded_value(self):
        assert FailSafeState.DEGRADED.value == "degraded"

    def test_holding_value(self):
        assert FailSafeState.HOLDING.value == "holding"

    def test_returning_value(self):
        assert FailSafeState.RETURNING.value == "returning"

    def test_all_states_count(self):
        assert len(FailSafeState) == 4

    def test_is_string_enum(self):
        assert isinstance(FailSafeState.CONNECTED, str)
        assert FailSafeState.CONNECTED == "connected"


class TestFailSafeManagerInit:
    def test_initial_state_is_connected(self):
        settings = _make_settings()
        manager = FailSafeManager(settings)
        assert manager.state == FailSafeState.CONNECTED

    def test_no_disconnection_timestamp(self):
        settings = _make_settings()
        manager = FailSafeManager(settings)
        assert manager._disconnected_since is None

    def test_thresholds_from_settings(self):
        settings = _make_settings(
            degraded_threshold_seconds=15,
            holding_threshold_seconds=45,
            return_threshold_seconds=180,
        )
        manager = FailSafeManager(settings)
        assert manager._degraded_threshold_seconds == 15
        assert manager._holding_threshold_seconds == 45
        assert manager._return_threshold_seconds == 180


class TestFailSafeManagerUpdateConnected:
    def test_stays_connected_when_connected(self):
        settings = _make_settings()
        manager = FailSafeManager(settings)

        manager.update_connectivity(is_connected=True)

        assert manager.state == FailSafeState.CONNECTED

    @patch("edge.mission_executor.fail_safe.time.monotonic")
    def test_restores_from_degraded(self, mock_monotonic):
        mock_monotonic.return_value = 100.0

        settings = _make_settings()
        manager = FailSafeManager(settings)

        # Simulate disconnection
        mock_monotonic.return_value = 100.0
        manager.update_connectivity(is_connected=False)

        # Move past degraded threshold
        mock_monotonic.return_value = 115.0
        manager.update_connectivity(is_connected=False)
        assert manager.state == FailSafeState.DEGRADED

        # Reconnect
        manager.update_connectivity(is_connected=True)
        assert manager.state == FailSafeState.CONNECTED
        assert manager._disconnected_since is None

    @patch("edge.mission_executor.fail_safe.time.monotonic")
    def test_restores_from_holding(self, mock_monotonic):
        settings = _make_settings()
        manager = FailSafeManager(settings)

        mock_monotonic.return_value = 100.0
        manager.update_connectivity(is_connected=False)

        mock_monotonic.return_value = 135.0
        manager.update_connectivity(is_connected=False)
        assert manager.state == FailSafeState.HOLDING

        manager.update_connectivity(is_connected=True)
        assert manager.state == FailSafeState.CONNECTED

    @patch("edge.mission_executor.fail_safe.time.monotonic")
    def test_restores_from_returning(self, mock_monotonic):
        settings = _make_settings()
        manager = FailSafeManager(settings)

        mock_monotonic.return_value = 100.0
        manager.update_connectivity(is_connected=False)

        mock_monotonic.return_value = 225.0
        manager.update_connectivity(is_connected=False)
        assert manager.state == FailSafeState.RETURNING

        manager.update_connectivity(is_connected=True)
        assert manager.state == FailSafeState.CONNECTED


class TestFailSafeManagerUpdateDisconnected:
    @patch("edge.mission_executor.fail_safe.time.monotonic")
    def test_first_disconnect_starts_timer(self, mock_monotonic):
        mock_monotonic.return_value = 100.0

        settings = _make_settings()
        manager = FailSafeManager(settings)

        manager.update_connectivity(is_connected=False)

        assert manager._disconnected_since == 100.0

    @patch("edge.mission_executor.fail_safe.time.monotonic")
    def test_transitions_to_degraded(self, mock_monotonic):
        settings = _make_settings(degraded_threshold_seconds=10)
        manager = FailSafeManager(settings)

        mock_monotonic.return_value = 100.0
        manager.update_connectivity(is_connected=False)
        assert manager.state == FailSafeState.CONNECTED

        # At threshold (10 seconds later)
        mock_monotonic.return_value = 110.0
        manager.update_connectivity(is_connected=False)
        assert manager.state == FailSafeState.DEGRADED

    @patch("edge.mission_executor.fail_safe.time.monotonic")
    def test_transitions_to_holding(self, mock_monotonic):
        settings = _make_settings(
            degraded_threshold_seconds=10,
            holding_threshold_seconds=30,
        )
        manager = FailSafeManager(settings)

        mock_monotonic.return_value = 100.0
        manager.update_connectivity(is_connected=False)

        mock_monotonic.return_value = 130.0
        manager.update_connectivity(is_connected=False)
        assert manager.state == FailSafeState.HOLDING

    @patch("edge.mission_executor.fail_safe.time.monotonic")
    def test_transitions_to_returning(self, mock_monotonic):
        settings = _make_settings(
            degraded_threshold_seconds=10,
            holding_threshold_seconds=30,
            return_threshold_seconds=120,
        )
        manager = FailSafeManager(settings)

        mock_monotonic.return_value = 100.0
        manager.update_connectivity(is_connected=False)

        mock_monotonic.return_value = 220.0
        manager.update_connectivity(is_connected=False)
        assert manager.state == FailSafeState.RETURNING

    @patch("edge.mission_executor.fail_safe.time.monotonic")
    def test_stays_connected_before_degraded_threshold(self, mock_monotonic):
        settings = _make_settings(degraded_threshold_seconds=10)
        manager = FailSafeManager(settings)

        mock_monotonic.return_value = 100.0
        manager.update_connectivity(is_connected=False)

        # 5 seconds later -- still below threshold
        mock_monotonic.return_value = 105.0
        manager.update_connectivity(is_connected=False)
        assert manager.state == FailSafeState.CONNECTED

    @patch("edge.mission_executor.fail_safe.time.monotonic")
    def test_full_escalation_sequence(self, mock_monotonic):
        settings = _make_settings(
            degraded_threshold_seconds=10,
            holding_threshold_seconds=30,
            return_threshold_seconds=120,
        )
        manager = FailSafeManager(settings)

        # Start disconnected
        mock_monotonic.return_value = 0.0
        manager.update_connectivity(is_connected=False)
        assert manager.state == FailSafeState.CONNECTED

        # 5s: still connected
        mock_monotonic.return_value = 5.0
        manager.update_connectivity(is_connected=False)
        assert manager.state == FailSafeState.CONNECTED

        # 10s: degraded
        mock_monotonic.return_value = 10.0
        manager.update_connectivity(is_connected=False)
        assert manager.state == FailSafeState.DEGRADED

        # 20s: still degraded
        mock_monotonic.return_value = 20.0
        manager.update_connectivity(is_connected=False)
        assert manager.state == FailSafeState.DEGRADED

        # 30s: holding
        mock_monotonic.return_value = 30.0
        manager.update_connectivity(is_connected=False)
        assert manager.state == FailSafeState.HOLDING

        # 90s: still holding
        mock_monotonic.return_value = 90.0
        manager.update_connectivity(is_connected=False)
        assert manager.state == FailSafeState.HOLDING

        # 120s: returning
        mock_monotonic.return_value = 120.0
        manager.update_connectivity(is_connected=False)
        assert manager.state == FailSafeState.RETURNING

        # 200s: still returning
        mock_monotonic.return_value = 200.0
        manager.update_connectivity(is_connected=False)
        assert manager.state == FailSafeState.RETURNING


class TestFailSafeManagerShouldHold:
    def test_should_hold_in_holding_state(self):
        settings = _make_settings()
        manager = FailSafeManager(settings)
        manager._state = FailSafeState.HOLDING

        assert manager.should_hold() is True

    def test_should_not_hold_in_connected_state(self):
        settings = _make_settings()
        manager = FailSafeManager(settings)

        assert manager.should_hold() is False

    def test_should_not_hold_in_degraded_state(self):
        settings = _make_settings()
        manager = FailSafeManager(settings)
        manager._state = FailSafeState.DEGRADED

        assert manager.should_hold() is False

    def test_should_not_hold_in_returning_state(self):
        settings = _make_settings()
        manager = FailSafeManager(settings)
        manager._state = FailSafeState.RETURNING

        assert manager.should_hold() is False


class TestFailSafeManagerShouldReturn:
    def test_should_return_in_returning_state(self):
        settings = _make_settings()
        manager = FailSafeManager(settings)
        manager._state = FailSafeState.RETURNING

        assert manager.should_return() is True

    def test_should_not_return_in_connected_state(self):
        settings = _make_settings()
        manager = FailSafeManager(settings)

        assert manager.should_return() is False

    def test_should_not_return_in_degraded_state(self):
        settings = _make_settings()
        manager = FailSafeManager(settings)
        manager._state = FailSafeState.DEGRADED

        assert manager.should_return() is False

    def test_should_not_return_in_holding_state(self):
        settings = _make_settings()
        manager = FailSafeManager(settings)
        manager._state = FailSafeState.HOLDING

        assert manager.should_return() is False


class TestFailSafeManagerReset:
    def test_reset_from_connected(self):
        settings = _make_settings()
        manager = FailSafeManager(settings)

        manager.reset()

        assert manager.state == FailSafeState.CONNECTED
        assert manager._disconnected_since is None

    def test_reset_from_degraded(self):
        settings = _make_settings()
        manager = FailSafeManager(settings)
        manager._state = FailSafeState.DEGRADED
        manager._disconnected_since = 100.0

        manager.reset()

        assert manager.state == FailSafeState.CONNECTED
        assert manager._disconnected_since is None

    def test_reset_from_holding(self):
        settings = _make_settings()
        manager = FailSafeManager(settings)
        manager._state = FailSafeState.HOLDING
        manager._disconnected_since = 100.0

        manager.reset()

        assert manager.state == FailSafeState.CONNECTED
        assert manager._disconnected_since is None

    def test_reset_from_returning(self):
        settings = _make_settings()
        manager = FailSafeManager(settings)
        manager._state = FailSafeState.RETURNING
        manager._disconnected_since = 100.0

        manager.reset()

        assert manager.state == FailSafeState.CONNECTED
        assert manager._disconnected_since is None


class TestFailSafeManagerElapsedTime:
    @patch("edge.mission_executor.fail_safe.time.monotonic")
    def test_elapsed_zero_when_connected(self, mock_monotonic):
        settings = _make_settings()
        manager = FailSafeManager(settings)

        result = manager._elapsed_disconnection_seconds()
        assert result == 0.0

    @patch("edge.mission_executor.fail_safe.time.monotonic")
    def test_elapsed_time_when_disconnected(self, mock_monotonic):
        settings = _make_settings()
        manager = FailSafeManager(settings)
        manager._disconnected_since = 100.0

        mock_monotonic.return_value = 115.0

        result = manager._elapsed_disconnection_seconds()
        assert result == pytest.approx(15.0)
