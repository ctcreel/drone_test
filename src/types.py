"""Type definitions for Lambda handlers and common structures."""

from typing import Protocol, TypedDict


class LambdaContext(Protocol):
    """AWS Lambda context object interface."""

    function_name: str
    function_version: str
    invoked_function_arn: str
    memory_limit_in_mb: int
    aws_request_id: str
    log_group_name: str
    log_stream_name: str

    def get_remaining_time_in_millis(self) -> int:
        """Return remaining execution time in milliseconds."""
        ...


class LambdaResponse(TypedDict):
    """Standard Lambda response structure."""

    statusCode: int
    body: str


# For truly dynamic JSON data
LambdaEvent = dict[str, object]
