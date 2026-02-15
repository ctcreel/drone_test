"""Lambda adapter for setting logging context from Lambda events."""

from typing import Any

from src.logging.context import set_correlation_id, set_extra_context
from src.types import LambdaContext


def set_lambda_context(
    event: dict[str, Any],
    context: LambdaContext,
) -> None:
    """Set logging context from Lambda event and context.

    Args:
        event: Lambda event dictionary.
        context: Lambda context object.
    """
    set_correlation_id(context.aws_request_id)
    set_extra_context(
        function_name=context.function_name,
        function_version=context.function_version,
    )

    if isinstance(event.get("requestContext"), dict):
        request_context: dict[str, Any] = event["requestContext"]
        if "requestId" in request_context:
            set_extra_context(api_request_id=str(request_context["requestId"]))
