"""Mission controller Lambda handler."""

import os
from typing import Any

from src.exceptions.client_errors import BadRequestError
from src.exceptions.handlers import create_exception_handler, create_success_response
from src.mission.models import MissionStatus
from src.mission.repository import MissionRepository
from src.utils.dynamodb import DynamoDBClient


def _get_repository() -> MissionRepository:
    """Get a mission repository instance."""
    table_name = os.environ["TABLE_NAME"]
    return MissionRepository(DynamoDBClient(table_name))


def _extract_path_parameter(event: dict[str, Any], parameter: str) -> str:
    """Extract a path parameter from API Gateway event.

    Args:
        event: API Gateway proxy event.
        parameter: Parameter name.

    Returns:
        Parameter value.

    Raises:
        BadRequestError: If parameter is missing.
    """
    path_params: dict[str, str] = event.get("pathParameters") or {}
    value: str | None = path_params.get(parameter)
    if not value:
        raise BadRequestError(message=f"Missing path parameter: {parameter}")
    return value


def _handle_mission_id_route(
    event: dict[str, Any],
    repository: MissionRepository,
) -> dict[str, Any] | None:
    """Handle routes that require a mission_id path parameter.

    Args:
        event: API Gateway proxy event.
        repository: Mission repository.

    Returns:
        Response dict if route matched, None otherwise.
    """
    http_method = event.get("httpMethod", "")
    resource = event.get("resource", "")

    routes: dict[tuple[str, str], str] = {
        ("/api/v1/missions/{mission_id}", "GET"): "get",
        ("/api/v1/missions/{mission_id}/approve", "POST"): "approve",
        ("/api/v1/missions/{mission_id}/abort", "POST"): "abort",
        ("/api/v1/missions/{mission_id}/status", "GET"): "status",
    }

    action = routes.get((resource, http_method))
    if not action:
        return None

    mission_id = _extract_path_parameter(event, "mission_id")

    handlers: dict[str, Any] = {
        "get": lambda: _get_mission(repository, mission_id),
        "approve": lambda: _approve_mission(repository, mission_id),
        "abort": lambda: _abort_mission(repository, mission_id),
        "status": lambda: _get_mission_status(repository, mission_id),
    }

    return handlers[action]()


def _route_request(event: dict[str, Any]) -> dict[str, Any]:
    """Route the request to the appropriate handler based on path and method.

    Args:
        event: API Gateway proxy event.

    Returns:
        API Gateway proxy response.
    """
    http_method = event.get("httpMethod", "")
    resource = event.get("resource", "")
    repository = _get_repository()

    if resource == "/api/v1/missions" and http_method == "GET":
        return _list_missions(repository, event)

    result = _handle_mission_id_route(event, repository)
    if result is not None:
        return result

    if "/test/scenarios" in resource:
        return create_success_response(
            200,
            {"status": "ok", "message": "test endpoint"},
        )

    return create_success_response(
        200,
        {"status": "ok", "message": "mission controller"},
    )


def _list_missions(
    repository: MissionRepository,
    event: dict[str, Any],
) -> dict[str, Any]:
    """List missions, optionally filtered by status."""
    query_params: dict[str, str] = event.get("queryStringParameters") or {}
    status_filter: str | None = query_params.get("status")

    if status_filter:
        missions = repository.list_by_status(MissionStatus(status_filter))
    else:
        missions = repository.list_all()

    return create_success_response(
        200,
        {"missions": [m.model_dump() for m in missions]},
    )


def _get_mission(
    repository: MissionRepository,
    mission_id: str,
) -> dict[str, Any]:
    """Get a single mission by ID."""
    mission = repository.get(mission_id)
    return create_success_response(200, mission.model_dump())


def _approve_mission(
    repository: MissionRepository,
    mission_id: str,
) -> dict[str, Any]:
    """Approve a planned mission for execution."""
    mission = repository.update_status(mission_id, MissionStatus.APPROVED)
    return create_success_response(200, mission.model_dump())


def _abort_mission(
    repository: MissionRepository,
    mission_id: str,
) -> dict[str, Any]:
    """Abort an active mission."""
    mission = repository.update_status(mission_id, MissionStatus.ABORTED)
    return create_success_response(200, mission.model_dump())


def _get_mission_status(
    repository: MissionRepository,
    mission_id: str,
) -> dict[str, Any]:
    """Get mission status with current progress."""
    mission = repository.get(mission_id)
    return create_success_response(
        200,
        {
            "mission_id": mission.mission_id,
            "status": mission.status,
            "updated_at": mission.updated_at,
        },
    )


@create_exception_handler
def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Handle mission CRUD, approve, abort, and status requests.

    Args:
        event: API Gateway proxy event.
        context: Lambda context.

    Returns:
        API Gateway proxy response.
    """
    _ = context
    return _route_request(event)
