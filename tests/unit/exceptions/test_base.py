"""Tests for base exception classes."""

from http import HTTPStatus

from src.exceptions.base import DroneFleetError
from src.exceptions.client_errors import ValidationError


class TestDroneFleetError:
    def test_default_error_code(self):
        error = DroneFleetError("something failed")
        assert error.error_code == "INTERNAL_ERROR"

    def test_default_http_status(self):
        error = DroneFleetError("something failed")
        assert error.http_status == HTTPStatus.INTERNAL_SERVER_ERROR

    def test_message_attribute(self):
        error = DroneFleetError("test message")
        assert error.message == "test message"

    def test_empty_context_by_default(self):
        error = DroneFleetError("test")
        assert error.context == {}

    def test_custom_context(self):
        context = {"mission_id": "123"}
        error = DroneFleetError("test", context=context)
        assert error.context == context

    def test_to_dict(self):
        error = DroneFleetError("test message", context={"key": "value"})
        result = error.to_dict()
        assert result["error_code"] == "INTERNAL_ERROR"
        assert result["message"] == "test message"
        assert result["context"] == {"key": "value"}

    def test_to_log_dict(self):
        error = DroneFleetError("test message")
        result = error.to_log_dict()
        assert result["error_code"] == "INTERNAL_ERROR"
        assert result["http_status"] == HTTPStatus.INTERNAL_SERVER_ERROR
        assert result["exception_type"] == "DroneFleetError"

    def test_str_without_context(self):
        error = DroneFleetError("test message")
        assert str(error) == "test message"

    def test_str_with_context(self):
        error = DroneFleetError("test", context={"id": "123"})
        assert "context" in str(error)

    def test_repr(self):
        error = DroneFleetError("test")
        result = repr(error)
        assert "DroneFleetError" in result
        assert "test" in result

    def test_inherits_from_exception(self):
        error = DroneFleetError("test")
        assert isinstance(error, Exception)


class TestExceptionRegistry:
    def test_base_not_in_registry(self):
        # Base class doesn't register itself - only subclasses auto-register
        result = DroneFleetError.get_by_error_code("INTERNAL_ERROR")
        assert result is None

    def test_unknown_code_returns_none(self):
        result = DroneFleetError.get_by_error_code("NONEXISTENT")
        assert result is None

    def test_subclass_auto_registers(self):
        result = DroneFleetError.get_by_error_code("VALIDATION_ERROR")
        assert result is ValidationError
