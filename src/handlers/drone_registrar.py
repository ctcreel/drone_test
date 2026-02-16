"""Drone registrar Lambda handler."""

import json
import os
import uuid
from typing import Any

from src.exceptions.client_errors import BadRequestError
from src.exceptions.handlers import create_exception_handler, create_success_response
from src.fleet.models import Drone, DroneStatus
from src.fleet.repository import DroneRepository
from src.utils.dynamodb import DynamoDBClient


def _get_repository() -> DroneRepository:
    """Get a drone repository instance."""
    table_name = os.environ["TABLE_NAME"]
    return DroneRepository(DynamoDBClient(table_name))


def _extract_path_parameter(event: dict[str, Any], parameter: str) -> str:
    """Extract a path parameter from API Gateway event."""
    path_params: dict[str, str] = event.get("pathParameters") or {}
    value: str | None = path_params.get(parameter)
    if not value:
        raise BadRequestError(message=f"Missing path parameter: {parameter}")
    return value


def _route_request(event: dict[str, Any]) -> dict[str, Any]:
    """Route request based on HTTP method and resource.

    Args:
        event: API Gateway proxy event.

    Returns:
        API Gateway proxy response.
    """
    http_method = event.get("httpMethod", "")
    resource = event.get("resource", "")
    repository = _get_repository()

    if resource == "/api/v1/drones" and http_method == "GET":
        return _list_drones(repository)

    if resource == "/api/v1/drones" and http_method == "POST":
        return _register_drone(repository, event)

    if resource == "/api/v1/drones/{drone_id}" and http_method == "GET":
        drone_id = _extract_path_parameter(event, "drone_id")
        return _get_drone(repository, drone_id)

    return create_success_response(
        200,
        {"status": "ok", "message": "drone registrar"},
    )


def _register_drone(
    repository: DroneRepository,
    event: dict[str, Any],
) -> dict[str, Any]:
    """Register a new drone."""
    body = event.get("body")
    if not body:
        raise BadRequestError(message="Request body is required")

    parsed: dict[str, Any] = json.loads(body) if isinstance(body, str) else body

    drone_id = str(uuid.uuid4())
    name: str = parsed.get("name", f"drone-{drone_id[:8]}")

    drone = Drone(
        drone_id=drone_id,
        name=name,
        iot_thing_name=f"drone-fleet-{drone_id}",
        status=DroneStatus.REGISTERED,
    )
    repository.create(drone)
    return create_success_response(201, drone.model_dump())


def _list_drones(repository: DroneRepository) -> dict[str, Any]:
    """List all registered drones."""
    drones = repository.list_all()
    return create_success_response(
        200,
        {"drones": [d.model_dump() for d in drones]},
    )


def _get_drone(
    repository: DroneRepository,
    drone_id: str,
) -> dict[str, Any]:
    """Get a single drone by ID."""
    drone = repository.get(drone_id)
    return create_success_response(200, drone.model_dump())


@create_exception_handler
def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Handle drone registration, listing, and lookup.

    Args:
        event: API Gateway proxy event.
        context: Lambda context.

    Returns:
        API Gateway proxy response.
    """
    _ = context
    return _route_request(event)
