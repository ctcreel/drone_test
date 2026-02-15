"""Drone fleet search exception hierarchy.

Architecture:
    DroneFleetError (base)
    ├── ClientError (4xx)
    │   ├── ValidationError (400)
    │   ├── BadRequestError (400)
    │   ├── AuthenticationError (401)
    │   ├── AuthorizationError (403)
    │   ├── NotFoundError (404)
    │   ├── ConflictError (409)
    │   └── RateLimitError (429)
    └── ServerError (5xx)
        ├── ProcessingError (500)
        ├── DatabaseError (500)
        ├── ConfigurationError (500)
        ├── ExternalServiceError (502)
        ├── ServiceUnavailableError (503)
        └── TimeoutError (504)

Usage:
    from src.exceptions import ValidationError, NotFoundError

    def get_mission(mission_id: str) -> Mission:
        mission = repository.get(mission_id)
        if mission is None:
            raise NotFoundError(
                f"Mission {mission_id} not found",
                resource_type="Mission",
                resource_id=mission_id,
            )
        return mission
"""

from src.exceptions.base import DroneFleetError
from src.exceptions.client_errors import (
    AuthenticationError,
    AuthorizationError,
    BadRequestError,
    ClientError,
    ConflictError,
    NotFoundError,
    RateLimitError,
    ValidationError,
)
from src.exceptions.handlers import (
    create_error_response,
    create_exception_handler,
    create_success_response,
    get_http_status_for_error_code,
)
from src.exceptions.server_errors import (
    ConfigurationError,
    DatabaseError,
    ExternalServiceError,
    ProcessingError,
    ServerError,
    ServiceUnavailableError,
    TimeoutError,
)

__all__ = [
    "AuthenticationError",
    "AuthorizationError",
    "BadRequestError",
    "ClientError",
    "ConfigurationError",
    "ConflictError",
    "DatabaseError",
    "DroneFleetError",
    "ExternalServiceError",
    "NotFoundError",
    "ProcessingError",
    "RateLimitError",
    "ServerError",
    "ServiceUnavailableError",
    "TimeoutError",
    "ValidationError",
    "create_error_response",
    "create_exception_handler",
    "create_success_response",
    "get_http_status_for_error_code",
]
