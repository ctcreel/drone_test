"""Fleet coordinator Lambda handler."""

import logging
import os
from datetime import UTC, datetime, timedelta
from typing import Any

from src.constants import CONNECTIVITY_DEGRADED_THRESHOLD
from src.exceptions.handlers import create_exception_handler, create_success_response
from src.fleet.models import Drone, DroneStatus, FleetState
from src.fleet.repository import DroneRepository
from src.utils.dynamodb import DynamoDBClient

logger = logging.getLogger(__name__)

LOW_BATTERY_THRESHOLD = 20.0


def _get_repository() -> DroneRepository:
    """Get a drone repository instance."""
    table_name = os.environ["TABLE_NAME"]
    return DroneRepository(DynamoDBClient(table_name))


def _check_drone_health(drone: Drone) -> list[dict[str, str]]:
    """Check a single drone for health issues.

    Args:
        drone: Drone to check.

    Returns:
        List of alerts for this drone.
    """
    alerts: list[dict[str, str]] = []

    if drone.health and drone.health.battery_remaining_percent < LOW_BATTERY_THRESHOLD:
        alerts.append(
            {
                "drone_id": drone.drone_id,
                "type": "low_battery",
                "message": (f"Battery at {drone.health.battery_remaining_percent:.0f}%"),
            }
        )

    if drone.last_seen:
        try:
            last_seen_time = datetime.fromisoformat(drone.last_seen)
            threshold = timedelta(seconds=CONNECTIVITY_DEGRADED_THRESHOLD)
            if datetime.now(UTC) - last_seen_time > threshold:
                alerts.append(
                    {
                        "drone_id": drone.drone_id,
                        "type": "connection_lost",
                        "message": f"Last seen: {drone.last_seen}",
                    }
                )
        except ValueError:
            pass

    return alerts


def _build_fleet_state(drones: list[Drone]) -> FleetState:
    """Build a fleet state summary from a list of drones.

    Args:
        drones: List of all drones.

    Returns:
        Fleet state summary.
    """
    return FleetState(
        total_drones=len(drones),
        available_drones=sum(1 for d in drones if d.status == DroneStatus.AVAILABLE),
        active_drones=sum(1 for d in drones if d.status == DroneStatus.ACTIVE),
        maintenance_drones=sum(1 for d in drones if d.status == DroneStatus.MAINTENANCE),
    )


def _coordinate_fleet(repository: DroneRepository) -> dict[str, Any]:
    """Run fleet coordination cycle.

    Args:
        repository: Drone repository.

    Returns:
        Coordination result with fleet state and alerts.
    """
    drones = repository.list_all()
    fleet_state = _build_fleet_state(drones)

    all_alerts: list[dict[str, str]] = []
    for drone in drones:
        if drone.status in (DroneStatus.ACTIVE, DroneStatus.ASSIGNED):
            alerts = _check_drone_health(drone)
            all_alerts.extend(alerts)

    if all_alerts:
        logger.warning(
            "Fleet alerts detected: %d alerts for %d drones",
            len(all_alerts),
            len({a["drone_id"] for a in all_alerts}),
        )

    return {
        "fleet_state": fleet_state.model_dump(),
        "alerts": all_alerts,
        "checked_at": datetime.now(UTC).isoformat(),
    }


@create_exception_handler
def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Monitor fleet state and coordinate drones.

    Args:
        event: EventBridge scheduled event.
        context: Lambda context.

    Returns:
        Processing result.
    """
    _ = event
    _ = context
    repository = _get_repository()
    result = _coordinate_fleet(repository)
    return create_success_response(200, result)
