"""Base exception classes for the drone fleet search system.

Uses Template Method + Registry pattern for structured error handling.
"""

from http import HTTPStatus
from typing import Any, ClassVar


class DroneFleetError(Exception):
    """Base exception for all drone fleet search errors.

    All custom exceptions inherit from this class, enabling:
    - Single catch block for all application errors
    - Consistent error response structure
    - Automatic HTTP status code mapping

    Attributes:
        message: Human-readable error description.
        error_code: Machine-readable error code.
        http_status: HTTP status code for API responses.
        context: Additional debugging information.
    """

    error_code: ClassVar[str] = "INTERNAL_ERROR"
    http_status: ClassVar[int] = HTTPStatus.INTERNAL_SERVER_ERROR

    _registry: ClassVar[dict[str, type["DroneFleetError"]]] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Register subclass in the exception registry."""
        super().__init_subclass__(**kwargs)
        cls._registry[cls.error_code] = cls

    def __init__(
        self,
        message: str,
        *,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the exception.

        Args:
            message: Human-readable error description.
            context: Additional key-value pairs for debugging.
        """
        super().__init__(message)
        self.message = message
        self.context = context or {}

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for API responses.

        Returns:
            Dictionary with error details suitable for JSON serialization.
        """
        return {
            "error_code": self.error_code,
            "message": self.message,
            "context": self.context,
        }

    def to_log_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for structured logging.

        Returns:
            Dictionary with full error details for logging.
        """
        return {
            "error_code": self.error_code,
            "http_status": self.http_status,
            "message": self.message,
            "context": self.context,
            "exception_type": self.__class__.__name__,
        }

    @classmethod
    def get_by_error_code(cls, error_code: str) -> type["DroneFleetError"] | None:
        """Look up exception class by error code.

        Args:
            error_code: The error code to look up.

        Returns:
            The exception class, or None if not found.
        """
        return cls._registry.get(error_code)

    def __str__(self) -> str:
        """Return string representation."""
        if self.context:
            return f"{self.message} (context: {self.context})"
        return self.message

    def __repr__(self) -> str:
        """Return detailed representation."""
        return (
            f"{self.__class__.__name__}("
            f"message={self.message!r}, "
            f"error_code={self.error_code!r}, "
            f"context={self.context!r})"
        )
