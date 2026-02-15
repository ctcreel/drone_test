"""Client error exceptions (HTTP 4xx)."""

from http import HTTPStatus
from typing import Any, ClassVar

from src.exceptions.base import DroneFleetError


class ClientError(DroneFleetError):
    """Base class for all client errors (4xx)."""

    error_code: ClassVar[str] = "CLIENT_ERROR"
    http_status: ClassVar[int] = HTTPStatus.BAD_REQUEST


class ValidationError(ClientError):
    """Input validation failed.

    Raise when request data fails validation rules.
    """

    error_code: ClassVar[str] = "VALIDATION_ERROR"
    http_status: ClassVar[int] = HTTPStatus.BAD_REQUEST

    def __init__(
        self,
        message: str,
        *,
        field: str | None = None,
        value: Any = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Initialize validation error with optional field info.

        Args:
            message: Description of the validation failure.
            field: Name of the field that failed validation.
            value: The invalid value.
            context: Additional context information.
        """
        context_dict = context or {}
        if field is not None:
            context_dict["field"] = field
        if value is not None:
            context_dict["value"] = value
        super().__init__(message, context=context_dict)


class NotFoundError(ClientError):
    """Requested resource not found."""

    error_code: ClassVar[str] = "NOT_FOUND"
    http_status: ClassVar[int] = HTTPStatus.NOT_FOUND

    def __init__(
        self,
        message: str,
        *,
        resource_type: str | None = None,
        resource_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Initialize not found error with optional resource info.

        Args:
            message: Description of what was not found.
            resource_type: Type of resource (e.g., "Mission", "Drone").
            resource_id: ID of the resource that was not found.
            context: Additional context information.
        """
        context_dict = context or {}
        if resource_type is not None:
            context_dict["resource_type"] = resource_type
        if resource_id is not None:
            context_dict["resource_id"] = resource_id
        super().__init__(message, context=context_dict)


class ConflictError(ClientError):
    """Resource state conflict."""

    error_code: ClassVar[str] = "CONFLICT"
    http_status: ClassVar[int] = HTTPStatus.CONFLICT


class AuthenticationError(ClientError):
    """Authentication failed."""

    error_code: ClassVar[str] = "AUTHENTICATION_FAILED"
    http_status: ClassVar[int] = HTTPStatus.UNAUTHORIZED


class AuthorizationError(ClientError):
    """Authorization failed."""

    error_code: ClassVar[str] = "AUTHORIZATION_FAILED"
    http_status: ClassVar[int] = HTTPStatus.FORBIDDEN


class RateLimitError(ClientError):
    """Rate limit exceeded."""

    error_code: ClassVar[str] = "RATE_LIMIT_EXCEEDED"
    http_status: ClassVar[int] = HTTPStatus.TOO_MANY_REQUESTS


class BadRequestError(ClientError):
    """Generic bad request."""

    error_code: ClassVar[str] = "BAD_REQUEST"
    http_status: ClassVar[int] = HTTPStatus.BAD_REQUEST
