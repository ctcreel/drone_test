"""Mission planner Lambda handler."""

import json
import os
import uuid
from typing import Any

from src.environment.repository import EnvironmentRepository
from src.exceptions.client_errors import BadRequestError, ValidationError
from src.exceptions.handlers import create_exception_handler, create_success_response
from src.mission.models import Mission, MissionObjective, MissionStatus
from src.mission.planner import plan_mission
from src.mission.repository import MissionRepository
from src.utils.dynamodb import DynamoDBClient
from src.utils.s3 import S3Client


def _get_repositories() -> tuple[MissionRepository, EnvironmentRepository]:
    """Get repository instances."""
    table_name = os.environ["TABLE_NAME"]
    bucket_name = os.environ["BUCKET_NAME"]
    db_client = DynamoDBClient(table_name)
    s3_client = S3Client(bucket_name)
    return (
        MissionRepository(db_client),
        EnvironmentRepository(db_client, s3_client),
    )


def _parse_body(event: dict[str, Any]) -> dict[str, Any]:
    """Parse the request body from API Gateway event.

    Args:
        event: API Gateway proxy event.

    Returns:
        Parsed body dictionary.

    Raises:
        BadRequestError: If body is missing or invalid JSON.
    """
    body = event.get("body")
    if not body:
        raise BadRequestError(message="Request body is required")
    try:
        parsed: dict[str, Any] = json.loads(body) if isinstance(body, str) else body
    except json.JSONDecodeError as error:
        raise BadRequestError(message=f"Invalid JSON: {error}") from error
    return parsed


@create_exception_handler
def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Handle mission creation with Bedrock AI planning.

    Args:
        event: API Gateway proxy event.
        context: Lambda context.

    Returns:
        API Gateway proxy response.
    """
    _ = context

    body = _parse_body(event)

    try:
        objective = MissionObjective(
            description=body.get("objective", ""),
            search_area=body.get("search_area", {}),
            environment_id=body.get("environment_id", ""),
        )
    except Exception as error:
        raise ValidationError(
            field="body",
            value=str(body),
            message=f"Invalid mission objective: {error}",
        ) from error

    mission_repo, environment_repo = _get_repositories()

    environment = environment_repo.get(objective.environment_id)

    mission_id = str(uuid.uuid4())
    mission = Mission(
        mission_id=mission_id,
        status=MissionStatus.CREATED,
        objective=objective,
        operator_id=_extract_operator_id(event),
    )
    mission_repo.create(mission)

    plan = plan_mission(
        objective=objective,
        environment=environment,
        available_drones=[],
    )

    mission = mission_repo.update_plan(mission_id, plan)

    return create_success_response(201, mission.model_dump())


def _extract_operator_id(event: dict[str, Any]) -> str:
    """Extract the operator ID from Cognito claims.

    Args:
        event: API Gateway proxy event.

    Returns:
        Operator ID from Cognito or empty string.
    """
    request_context = event.get("requestContext", {})
    authorizer = request_context.get("authorizer", {})
    claims = authorizer.get("claims", {})
    return str(claims.get("sub", ""))
