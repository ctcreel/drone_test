"""Tests for type definitions."""

from src.types import LambdaEvent, LambdaResponse


class TestLambdaResponse:
    def test_response_structure(self):
        response: LambdaResponse = {"statusCode": 200, "body": '{"status": "ok"}'}
        assert response["statusCode"] == 200
        assert response["body"] == '{"status": "ok"}'


class TestLambdaEvent:
    def test_event_is_dict(self):
        event: LambdaEvent = {"key": "value"}
        assert isinstance(event, dict)
