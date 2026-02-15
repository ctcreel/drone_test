"""Server error exceptions (HTTP 5xx)."""

from http import HTTPStatus
from typing import Any, ClassVar

from src.exceptions.base import DroneFleetError


class ServerError(DroneFleetError):
    """Base class for all server errors (5xx)."""

    error_code: ClassVar[str] = "SERVER_ERROR"
    http_status: ClassVar[int] = HTTPStatus.INTERNAL_SERVER_ERROR


class ProcessingError(ServerError):
    """Business logic processing failed."""

    error_code: ClassVar[str] = "PROCESSING_ERROR"
    http_status: ClassVar[int] = HTTPStatus.INTERNAL_SERVER_ERROR


class ExternalServiceError(ServerError):
    """External service call failed."""

    error_code: ClassVar[str] = "EXTERNAL_SERVICE_ERROR"
    http_status: ClassVar[int] = HTTPStatus.BAD_GATEWAY

    def __init__(
        self,
        message: str,
        *,
        service_name: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Initialize external service error.

        Args:
            message: Description of the failure.
            service_name: Name of the external service that failed.
            context: Additional context information.
        """
        context_dict = context or {}
        if service_name is not None:
            context_dict["service_name"] = service_name
        super().__init__(message, context=context_dict)


class DatabaseError(ServerError):
    """Database operation failed."""

    error_code: ClassVar[str] = "DATABASE_ERROR"
    http_status: ClassVar[int] = HTTPStatus.INTERNAL_SERVER_ERROR


class ConfigurationError(ServerError):
    """Configuration is invalid or missing."""

    error_code: ClassVar[str] = "CONFIGURATION_ERROR"
    http_status: ClassVar[int] = HTTPStatus.INTERNAL_SERVER_ERROR


class ServiceUnavailableError(ServerError):
    """Service temporarily unavailable."""

    error_code: ClassVar[str] = "SERVICE_UNAVAILABLE"
    http_status: ClassVar[int] = HTTPStatus.SERVICE_UNAVAILABLE


class TimeoutError(ServerError):
    """Operation timed out."""

    error_code: ClassVar[str] = "TIMEOUT"
    http_status: ClassVar[int] = HTTPStatus.GATEWAY_TIMEOUT
