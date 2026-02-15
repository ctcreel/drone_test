"""Tests for Bedrock Vision analyzer."""

import json
from io import BytesIO
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.analysis.analyzer import BedrockVisionAnalyzer
from src.exceptions.server_errors import ExternalServiceError, ProcessingError


def _make_analysis_response(detections: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    result = {
        "detections": detections or [],
        "scene_description": "Urban parking area",
        "search_relevant": bool(detections),
    }
    body_content = json.dumps({
        "content": [{"text": json.dumps(result)}],
    }).encode()
    return {"body": BytesIO(body_content)}


def _make_metadata() -> dict[str, Any]:
    return {
        "drone_id": "d-001",
        "latitude": 40.7128,
        "longitude": -74.0060,
        "altitude": 50.0,
        "heading": 180.0,
        "capture_time": "2024-01-01T12:00:00Z",
    }


class TestBedrockVisionAnalyzer:
    """Tests for BedrockVisionAnalyzer."""

    @patch("src.analysis.analyzer.boto3")
    def test_analyze_no_detections(self, mock_boto3: MagicMock) -> None:
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.invoke_model.return_value = _make_analysis_response()

        analyzer = BedrockVisionAnalyzer()
        result = analyzer.analyze_image(
            b"fake-image-bytes",
            "Find red vehicle",
            _make_metadata(),
        )
        assert result.detections == []
        assert not result.search_relevant

    @patch("src.analysis.analyzer.boto3")
    def test_analyze_with_detections(self, mock_boto3: MagicMock) -> None:
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client

        detections = [
            {
                "label": "red sedan",
                "confidence": 0.92,
                "bounding_box": {"x": 100, "y": 200, "width": 80, "height": 45},
                "reasoning": "Matches red vehicle description",
            },
        ]
        mock_client.invoke_model.return_value = _make_analysis_response(detections)

        analyzer = BedrockVisionAnalyzer()
        result = analyzer.analyze_image(
            b"fake-image-bytes",
            "Find red vehicle",
            _make_metadata(),
        )
        assert len(result.detections) == 1
        assert result.detections[0].label == "red sedan"
        assert result.search_relevant

    @patch("src.analysis.analyzer.boto3")
    def test_json_in_code_block(self, mock_boto3: MagicMock) -> None:
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client

        result_json = {
            "detections": [],
            "scene_description": "Forest area",
            "search_relevant": False,
        }
        wrapped = f"```json\n{json.dumps(result_json)}\n```"
        body = json.dumps({"content": [{"text": wrapped}]}).encode()
        mock_client.invoke_model.return_value = {"body": BytesIO(body)}

        analyzer = BedrockVisionAnalyzer()
        result = analyzer.analyze_image(b"img", "Search", _make_metadata())
        assert result.scene_description == "Forest area"

    @patch("src.analysis.analyzer.boto3")
    def test_bedrock_failure_raises(self, mock_boto3: MagicMock) -> None:
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.invoke_model.side_effect = Exception("Timeout")

        analyzer = BedrockVisionAnalyzer()
        with pytest.raises(ExternalServiceError):
            analyzer.analyze_image(b"img", "Search", _make_metadata())

    @patch("src.analysis.analyzer.boto3")
    def test_invalid_response_raises(self, mock_boto3: MagicMock) -> None:
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client

        body = json.dumps({"content": [{"text": "not json"}]}).encode()
        mock_client.invoke_model.return_value = {"body": BytesIO(body)}

        analyzer = BedrockVisionAnalyzer()
        with pytest.raises(ProcessingError):
            analyzer.analyze_image(b"img", "Search", _make_metadata())

    @patch("src.analysis.analyzer.boto3")
    def test_build_prompt_includes_metadata(self, mock_boto3: MagicMock) -> None:
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client

        analyzer = BedrockVisionAnalyzer()
        prompt = analyzer._build_prompt("Find hiker", _make_metadata())  # noqa: SLF001
        assert "Find hiker" in prompt
        assert "d-001" in prompt
        assert "40.7128" in prompt
