"""Exception handling utilities following RFC 7807."""

import json
from collections.abc import Callable
from functools import wraps
from http import HTTPStatus
from typing import Any, TypeGuard

from src.exceptions.base import DroneFleetError

LambdaResponse = dict[str, Any]


def create_error_response(
    exception: DroneFleetError,
    *,
    include_context: bool = True,
    request_id: str | None = None,
) -> LambdaResponse:
    """Create an API Gateway error response from an exception.

    Args:
        exception: The DroneFleetError to convert.
        include_context: Whether to include context in response.
        request_id: Optional request ID for tracing.

    Returns:
        Lambda-compatible response dictionary.
    """
    body: dict[str, Any] = {
        "type": f"https://drone-fleet.io/errors/{exception.error_code}",
        "title": _format_error_title(exception.error_code),
        "status": exception.http_status,
        "detail": exception.message,
    }

    if request_id:
        body["instance"] = f"/requests/{request_id}"

    if include_context and exception.context:
        body["context"] = exception.context

    return {
        "statusCode": exception.http_status,
        "headers": {
            "Content-Type": "application/problem+json",
        },
        "body": json.dumps(body),
    }


def create_success_response(
    status_code: int,
    body: dict[str, Any],
) -> LambdaResponse:
    """Create an API Gateway success response.

    Args:
        status_code: HTTP status code (2xx).
        body: Response body dictionary.

    Returns:
        Lambda-compatible response dictionary.
    """
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
        },
        "body": json.dumps(body),
    }


def create_exception_handler[**P, T](
    func: Callable[P, T],
) -> Callable[P, T | LambdaResponse]:
    """Decorator that catches DroneFleetError and returns error responses.

    Args:
        func: The handler function to wrap.

    Returns:
        Wrapped function that handles exceptions.
    """

    @wraps(func)
    def handle_call(*args: P.args, **kwargs: P.kwargs) -> T | LambdaResponse:
        try:
            return func(*args, **kwargs)
        except DroneFleetError as error:
            request_id = _extract_request_id(args)
            return create_error_response(error, request_id=request_id)

    return handle_call


def _format_error_title(error_code: str) -> str:
    """Format error code as human-readable title."""
    return error_code.replace("_", " ").title()


def _is_string_dict(value: object) -> TypeGuard[dict[str, Any]]:
    """Type guard to check if value is a dict with string keys."""
    return isinstance(value, dict)


def _extract_request_id(args: tuple[object, ...]) -> str | None:
    """Extract request ID from Lambda event if present."""
    if not args:
        return None

    event = args[0]
    if not _is_string_dict(event):
        return None

    request_context = event.get("requestContext")
    if not _is_string_dict(request_context):
        return None

    request_id = request_context.get("requestId")
    if isinstance(request_id, str):
        return request_id

    return None


def get_http_status_for_error_code(error_code: str) -> int:
    """Get HTTP status code for an error code.

    Args:
        error_code: The error code to look up.

    Returns:
        HTTP status code, or 500 if not found.
    """
    exception_class = DroneFleetError.get_by_error_code(error_code)
    if exception_class is not None:
        return exception_class.http_status
    return HTTPStatus.INTERNAL_SERVER_ERROR
