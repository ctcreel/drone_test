"""Fail-safe state machine for connectivity loss handling.

Manages a deterministic state machine that transitions through
CONNECTED -> DEGRADED -> HOLDING -> RETURNING based on the duration
of connectivity loss. All thresholds are configurable via EdgeSettings.
"""

from __future__ import annotations

import logging
import time
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from edge.config import EdgeSettings

logger = logging.getLogger(__name__)


class FailSafeState(StrEnum):
    """Fail-safe connectivity state."""

    CONNECTED = "connected"
    DEGRADED = "degraded"
    HOLDING = "holding"
    RETURNING = "returning"


class FailSafeManager:
    """Manages fail-safe state transitions based on connectivity status.

    Implements a deterministic state machine that escalates through
    progressive fail-safe states as connectivity loss persists:

    - CONNECTED: Normal operation, cloud link active.
    - DEGRADED: Brief connectivity loss, continue mission with caution.
    - HOLDING: Extended loss, drone holds current position.
    - RETURNING: Prolonged loss, drone returns to launch point.

    State transitions are based on configurable time thresholds.
    """

    def __init__(self, settings: EdgeSettings) -> None:
        """Initialize the fail-safe manager.

        Args:
            settings: Edge tier configuration with fail-safe thresholds.
        """
        self._degraded_threshold_seconds = settings.degraded_threshold_seconds
        self._holding_threshold_seconds = settings.holding_threshold_seconds
        self._return_threshold_seconds = settings.return_threshold_seconds
        self._state = FailSafeState.CONNECTED
        self._disconnected_since: float | None = None

    @property
    def state(self) -> FailSafeState:
        """Return the current fail-safe state."""
        return self._state

    def update_connectivity(self, *, is_connected: bool) -> None:
        """Update fail-safe state based on current connectivity.

        Called periodically to assess connectivity and transition
        through fail-safe states based on elapsed disconnection time.

        Args:
            is_connected: Whether the cloud connection is currently active.
        """
        if is_connected:
            self._handle_connected()
            return

        self._handle_disconnected()

    def should_hold(self) -> bool:
        """Return whether the drone should hold its current position.

        Returns:
            True if the fail-safe state indicates the drone should hold.
        """
        return self._state == FailSafeState.HOLDING

    def should_return(self) -> bool:
        """Return whether the drone should return to launch.

        Returns:
            True if the fail-safe state indicates the drone should RTL.
        """
        return self._state == FailSafeState.RETURNING

    def reset(self) -> None:
        """Reset the fail-safe manager to CONNECTED state."""
        previous_state = self._state
        self._state = FailSafeState.CONNECTED
        self._disconnected_since = None

        if previous_state != FailSafeState.CONNECTED:
            logger.info(
                "Fail-safe reset from %s to %s",
                previous_state,
                FailSafeState.CONNECTED,
            )

    def _handle_connected(self) -> None:
        """Handle a connectivity-restored event."""
        if self._state != FailSafeState.CONNECTED:
            logger.info(
                "Connectivity restored (was in state %s for %.1f seconds)",
                self._state,
                self._elapsed_disconnection_seconds(),
            )

        self._state = FailSafeState.CONNECTED
        self._disconnected_since = None

    def _handle_disconnected(self) -> None:
        """Handle ongoing disconnection and manage state transitions."""
        current_time = time.monotonic()

        if self._disconnected_since is None:
            self._disconnected_since = current_time
            logger.warning("Connectivity lost, starting fail-safe timer")

        elapsed_seconds = current_time - self._disconnected_since
        previous_state = self._state

        if elapsed_seconds >= self._return_threshold_seconds:
            self._state = FailSafeState.RETURNING
        elif elapsed_seconds >= self._holding_threshold_seconds:
            self._state = FailSafeState.HOLDING
        elif elapsed_seconds >= self._degraded_threshold_seconds:
            self._state = FailSafeState.DEGRADED

        if self._state != previous_state:
            logger.warning(
                "Fail-safe state transition: %s -> %s (disconnected for %.1f seconds)",
                previous_state,
                self._state,
                elapsed_seconds,
            )

    def _elapsed_disconnection_seconds(self) -> float:
        """Return the elapsed time since disconnection began.

        Returns:
            Elapsed seconds since connectivity was lost, or 0.0 if connected.
        """
        if self._disconnected_since is None:
            return 0.0
        return time.monotonic() - self._disconnected_since
