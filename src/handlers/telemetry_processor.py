"""Telemetry processor Lambda handler."""

import logging
import os
from datetime import UTC, datetime
from typing import Any

from src.exceptions.handlers import create_exception_handler, create_success_response
from src.fleet.repository import DroneRepository
from src.telemetry.models import BatteryReport, ObstacleEvent, PositionReport
from src.utils.dynamodb import DynamoDBClient

logger = logging.getLogger(__name__)


def _get_repository() -> DroneRepository:
    """Get a drone repository instance."""
    table_name = os.environ["TABLE_NAME"]
    return DroneRepository(DynamoDBClient(table_name))


def _get_db_client() -> DynamoDBClient:
    """Get a DynamoDB client for telemetry writes."""
    table_name = os.environ["TABLE_NAME"]
    return DynamoDBClient(table_name)


def _process_telemetry(
    event: dict[str, Any],
    db_client: DynamoDBClient,
    drone_repo: DroneRepository,
) -> dict[str, Any]:
    """Process a single telemetry event.

    Args:
        event: IoT Rule event with telemetry data.
        db_client: DynamoDB client for telemetry storage.
        drone_repo: Drone repository for status updates.

    Returns:
        Processing result summary.
    """
    drone_id: str = event.get("drone_id", "")
    message_type: str = event.get("message_type", "")
    payload: dict[str, Any] = event.get("payload", {})
    timestamp = event.get(
        "timestamp",
        datetime.now(UTC).isoformat(),
    )

    if not drone_id:
        logger.warning("Telemetry event missing drone_id")
        return {"processed": False, "reason": "missing drone_id"}

    # Update drone last_seen
    drone_repo.update_last_seen(drone_id)

    if message_type == "position_report":
        report = PositionReport(
            drone_id=drone_id,
            timestamp=timestamp,
            latitude=payload.get("latitude", 0.0),
            longitude=payload.get("longitude", 0.0),
            altitude=payload.get("altitude", 0.0),
            heading=payload.get("heading", 0.0),
            speed=payload.get("speed", 0.0),
        )
        db_client.put_item(report.to_dynamodb_item())
        return {"processed": True, "type": "position"}

    if message_type == "battery_report":
        report = BatteryReport(
            drone_id=drone_id,
            timestamp=timestamp,
            voltage=payload.get("voltage", 0.0),
            remaining_percent=payload.get(
                "battery_remaining_percent",
                payload.get("remaining_percent", 0.0),
            ),
            estimated_flight_time_seconds=payload.get(
                "estimated_flight_time_seconds", 0,
            ),
        )
        db_client.put_item(report.to_dynamodb_item())

        # Update drone health if battery is reported
        drone_repo.update_health(drone_id, {
            "battery_voltage": report.voltage,
            "battery_remaining_percent": report.remaining_percent,
            "estimated_flight_time_seconds": report.estimated_flight_time_seconds,
        })
        return {"processed": True, "type": "battery"}

    if message_type == "obstacle_event":
        obstacle = ObstacleEvent(
            drone_id=drone_id,
            timestamp=timestamp,
            obstacle_type=payload.get("obstacle_type", "unknown"),
            distance_meters=payload.get("distance_meters", 0.0),
            avoidance_action=payload.get("avoidance_action", "none"),
        )
        db_client.put_item(obstacle.to_dynamodb_item())
        return {"processed": True, "type": "obstacle"}

    logger.info("Unknown message type: %s from drone %s", message_type, drone_id)
    return {"processed": False, "reason": f"unknown type: {message_type}"}


@create_exception_handler
def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Process telemetry data from IoT Rule.

    Args:
        event: IoT Rule event with telemetry data.
        context: Lambda context.

    Returns:
        Processing result.
    """
    _ = context
    db_client = _get_db_client()
    drone_repo = _get_repository()
    result = _process_telemetry(event, db_client, drone_repo)
    return create_success_response(200, result)
