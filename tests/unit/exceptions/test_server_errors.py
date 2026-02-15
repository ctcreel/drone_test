"""Tests for server error exceptions."""

from http import HTTPStatus

from src.exceptions.server_errors import (
    ConfigurationError,
    DatabaseError,
    ExternalServiceError,
    ProcessingError,
    ServerError,
    ServiceUnavailableError,
    TimeoutError,
)


class TestServerError:
    def test_error_code(self):
        assert ServerError("failed").error_code == "SERVER_ERROR"

    def test_http_status(self):
        assert ServerError("failed").http_status == HTTPStatus.INTERNAL_SERVER_ERROR


class TestProcessingError:
    def test_error_code(self):
        assert ProcessingError("failed").error_code == "PROCESSING_ERROR"

    def test_http_status(self):
        assert ProcessingError("failed").http_status == HTTPStatus.INTERNAL_SERVER_ERROR


class TestExternalServiceError:
    def test_error_code(self):
        assert ExternalServiceError("failed").error_code == "EXTERNAL_SERVICE_ERROR"

    def test_http_status(self):
        assert ExternalServiceError("failed").http_status == HTTPStatus.BAD_GATEWAY

    def test_service_name_in_context(self):
        error = ExternalServiceError("failed", service_name="bedrock")
        assert error.context["service_name"] == "bedrock"

    def test_custom_context_merged(self):
        error = ExternalServiceError(
            "failed",
            service_name="iot",
            context={"operation": "publish"},
        )
        assert error.context["service_name"] == "iot"
        assert error.context["operation"] == "publish"


class TestDatabaseError:
    def test_error_code(self):
        assert DatabaseError("failed").error_code == "DATABASE_ERROR"

    def test_http_status(self):
        assert DatabaseError("failed").http_status == HTTPStatus.INTERNAL_SERVER_ERROR


class TestConfigurationError:
    def test_error_code(self):
        assert ConfigurationError("missing").error_code == "CONFIGURATION_ERROR"


class TestServiceUnavailableError:
    def test_error_code(self):
        assert ServiceUnavailableError("down").error_code == "SERVICE_UNAVAILABLE"

    def test_http_status(self):
        assert ServiceUnavailableError("down").http_status == HTTPStatus.SERVICE_UNAVAILABLE


class TestTimeoutError:
    def test_error_code(self):
        assert TimeoutError("timed out").error_code == "TIMEOUT"

    def test_http_status(self):
        assert TimeoutError("timed out").http_status == HTTPStatus.GATEWAY_TIMEOUT
