"""Context variables for request-scoped logging data.

Uses Python's contextvars for thread-safe, async-compatible context.
"""

from contextvars import ContextVar
from typing import Any
from uuid import uuid4

correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")

_extra_context: ContextVar[dict[str, Any] | None] = ContextVar("extra_context", default=None)


def get_correlation_id() -> str:
    """Get the current correlation ID.

    Returns:
        The correlation ID for the current context.
    """
    return correlation_id.get()


def set_correlation_id(value: str) -> None:
    """Set the correlation ID for the current context.

    Args:
        value: The correlation ID.
    """
    correlation_id.set(value)


def generate_correlation_id() -> str:
    """Generate and set a new correlation ID.

    Returns:
        The generated correlation ID.
    """
    new_id = str(uuid4())
    correlation_id.set(new_id)
    return new_id


def get_extra_context() -> dict[str, Any]:
    """Get the current extra context.

    Returns:
        Dictionary of extra context fields.
    """
    context = _extra_context.get()
    if context is None:
        return {}
    return context.copy()


def set_extra_context(**kwargs: Any) -> None:
    """Set additional context fields to include in all log messages.

    Args:
        **kwargs: Key-value pairs to include in log messages.
    """
    current = _extra_context.get()
    current = {} if current is None else current.copy()
    current.update(kwargs)
    _extra_context.set(current)


def clear_context() -> None:
    """Clear all context (correlation ID and extra context)."""
    correlation_id.set("")
    _extra_context.set(None)
