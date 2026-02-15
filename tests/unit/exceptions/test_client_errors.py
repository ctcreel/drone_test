"""Tests for client error exceptions."""

from http import HTTPStatus

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


class TestClientError:
    def test_error_code(self):
        error = ClientError("bad request")
        assert error.error_code == "CLIENT_ERROR"

    def test_http_status(self):
        error = ClientError("bad request")
        assert error.http_status == HTTPStatus.BAD_REQUEST


class TestValidationError:
    def test_error_code(self):
        error = ValidationError("invalid input")
        assert error.error_code == "VALIDATION_ERROR"

    def test_http_status(self):
        error = ValidationError("invalid input")
        assert error.http_status == HTTPStatus.BAD_REQUEST

    def test_field_in_context(self):
        error = ValidationError("bad email", field="email")
        assert error.context["field"] == "email"

    def test_value_in_context(self):
        error = ValidationError("bad email", field="email", value="not-email")
        assert error.context["value"] == "not-email"

    def test_custom_context_merged(self):
        error = ValidationError("bad", field="name", context={"extra": "info"})
        assert error.context["field"] == "name"
        assert error.context["extra"] == "info"


class TestNotFoundError:
    def test_error_code(self):
        error = NotFoundError("not found")
        assert error.error_code == "NOT_FOUND"

    def test_http_status(self):
        error = NotFoundError("not found")
        assert error.http_status == HTTPStatus.NOT_FOUND

    def test_resource_type_in_context(self):
        error = NotFoundError("mission not found", resource_type="Mission")
        assert error.context["resource_type"] == "Mission"

    def test_resource_id_in_context(self):
        error = NotFoundError("not found", resource_id="mission-123")
        assert error.context["resource_id"] == "mission-123"


class TestConflictError:
    def test_error_code(self):
        assert ConflictError("conflict").error_code == "CONFLICT"

    def test_http_status(self):
        assert ConflictError("conflict").http_status == HTTPStatus.CONFLICT


class TestAuthenticationError:
    def test_error_code(self):
        assert AuthenticationError("bad token").error_code == "AUTHENTICATION_FAILED"

    def test_http_status(self):
        assert AuthenticationError("bad token").http_status == HTTPStatus.UNAUTHORIZED


class TestAuthorizationError:
    def test_error_code(self):
        assert AuthorizationError("forbidden").error_code == "AUTHORIZATION_FAILED"

    def test_http_status(self):
        assert AuthorizationError("forbidden").http_status == HTTPStatus.FORBIDDEN


class TestRateLimitError:
    def test_error_code(self):
        assert RateLimitError("too many").error_code == "RATE_LIMIT_EXCEEDED"

    def test_http_status(self):
        assert RateLimitError("too many").http_status == HTTPStatus.TOO_MANY_REQUESTS


class TestBadRequestError:
    def test_error_code(self):
        assert BadRequestError("bad").error_code == "BAD_REQUEST"

    def test_http_status(self):
        assert BadRequestError("bad").http_status == HTTPStatus.BAD_REQUEST
