"""Tests for Lambda logging adapter."""

from unittest.mock import MagicMock

import pytest

from src.logging.adapters.lambda_adapter import set_lambda_context
from src.logging.context import clear_context, get_correlation_id, get_extra_context


@pytest.fixture(autouse=True)
def _clear_logging_context() -> None:
    """Clear logging context before each test."""
    clear_context()


class TestSetLambdaContext:
    """Tests for set_lambda_context function."""

    def test_sets_correlation_id_from_request_id(self) -> None:
        """Correlation ID is set from aws_request_id."""
        context = MagicMock()
        context.aws_request_id = "test-request-id-123"
        context.function_name = "test-function"
        context.function_version = "$LATEST"

        set_lambda_context({}, context)

        assert get_correlation_id() == "test-request-id-123"

    def test_sets_function_name_in_extra_context(self) -> None:
        """Function name is added to extra context."""
        context = MagicMock()
        context.aws_request_id = "req-456"
        context.function_name = "drone-fleet-dev-mission-controller"
        context.function_version = "1"

        set_lambda_context({}, context)

        extra = get_extra_context()
        assert extra["function_name"] == "drone-fleet-dev-mission-controller"
        assert extra["function_version"] == "1"

    def test_sets_api_request_id_from_event(self) -> None:
        """API request ID is extracted from API Gateway event."""
        context = MagicMock()
        context.aws_request_id = "req-789"
        context.function_name = "test-fn"
        context.function_version = "$LATEST"

        event = {
            "requestContext": {
                "requestId": "api-request-id-abc",
            },
        }

        set_lambda_context(event, context)

        extra = get_extra_context()
        assert extra["api_request_id"] == "api-request-id-abc"

    def test_no_api_request_id_without_request_context(self) -> None:
        """No API request ID when requestContext is missing."""
        context = MagicMock()
        context.aws_request_id = "req-000"
        context.function_name = "test-fn"
        context.function_version = "$LATEST"

        set_lambda_context({}, context)

        extra = get_extra_context()
        assert "api_request_id" not in extra

    def test_no_api_request_id_when_request_context_not_dict(self) -> None:
        """No API request ID when requestContext is not a dict."""
        context = MagicMock()
        context.aws_request_id = "req-111"
        context.function_name = "test-fn"
        context.function_version = "$LATEST"

        event = {"requestContext": "not-a-dict"}

        set_lambda_context(event, context)

        extra = get_extra_context()
        assert "api_request_id" not in extra
