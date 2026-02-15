"""Tests for exception handler utilities."""

import json

from src.exceptions.base import DroneFleetError
from src.exceptions.client_errors import NotFoundError, ValidationError
from src.exceptions.handlers import (
    create_error_response,
    create_exception_handler,
    create_success_response,
    get_http_status_for_error_code,
)


class TestCreateErrorResponse:
    def test_status_code(self):
        error = ValidationError("invalid")
        response = create_error_response(error)
        assert response["statusCode"] == 400

    def test_content_type_header(self):
        error = ValidationError("invalid")
        response = create_error_response(error)
        assert response["headers"]["Content-Type"] == "application/problem+json"

    def test_body_contains_error_code(self):
        error = ValidationError("invalid")
        response = create_error_response(error)
        body = json.loads(response["body"])
        assert body["status"] == 400
        assert body["detail"] == "invalid"

    def test_body_contains_type_url(self):
        error = ValidationError("invalid")
        response = create_error_response(error)
        body = json.loads(response["body"])
        assert "VALIDATION_ERROR" in body["type"]

    def test_request_id_in_body(self):
        error = ValidationError("invalid")
        response = create_error_response(error, request_id="req-123")
        body = json.loads(response["body"])
        assert body["instance"] == "/requests/req-123"

    def test_context_included_by_default(self):
        error = ValidationError("invalid", field="email")
        response = create_error_response(error)
        body = json.loads(response["body"])
        assert body["context"]["field"] == "email"

    def test_context_excluded_when_disabled(self):
        error = ValidationError("invalid", field="email")
        response = create_error_response(error, include_context=False)
        body = json.loads(response["body"])
        assert "context" not in body

    def test_title_formatted(self):
        error = ValidationError("invalid")
        response = create_error_response(error)
        body = json.loads(response["body"])
        assert body["title"] == "Validation Error"


class TestCreateSuccessResponse:
    def test_status_code(self):
        response = create_success_response(200, {"status": "ok"})
        assert response["statusCode"] == 200

    def test_content_type_header(self):
        response = create_success_response(200, {"status": "ok"})
        assert response["headers"]["Content-Type"] == "application/json"

    def test_body_serialized(self):
        response = create_success_response(201, {"id": "123"})
        body = json.loads(response["body"])
        assert body["id"] == "123"


class TestCreateExceptionHandler:
    def test_returns_result_on_success(self):
        @create_exception_handler
        def handler(event, context):
            return {"statusCode": 200, "body": "ok"}

        result = handler({}, None)
        assert result["statusCode"] == 200

    def test_catches_drone_fleet_error(self):
        @create_exception_handler
        def handler(event, context):
            raise NotFoundError("mission not found")

        result = handler({}, None)
        assert result["statusCode"] == 404

    def test_extracts_request_id_from_event(self):
        @create_exception_handler
        def handler(event, context):
            raise ValidationError("invalid")

        event = {"requestContext": {"requestId": "abc-123"}}
        result = handler(event, None)
        body = json.loads(result["body"])
        assert body["instance"] == "/requests/abc-123"

    def test_handles_missing_request_context(self):
        @create_exception_handler
        def handler(event, context):
            raise ValidationError("invalid")

        result = handler({}, None)
        assert result["statusCode"] == 400

    def test_handles_non_dict_event(self):
        @create_exception_handler
        def handler(event, context):
            raise ValidationError("invalid")

        result = handler("not a dict", None)
        assert result["statusCode"] == 400


class TestGetHttpStatusForErrorCode:
    def test_known_error_code(self):
        status = get_http_status_for_error_code("VALIDATION_ERROR")
        assert status == 400

    def test_unknown_error_code(self):
        status = get_http_status_for_error_code("NONEXISTENT")
        assert status == 500

    def test_server_error_code(self):
        status = get_http_status_for_error_code("DATABASE_ERROR")
        assert status == 500

    def test_not_found_error_code(self):
        status = get_http_status_for_error_code("NOT_FOUND")
        assert status == 404
