"""Bedrock Vision analyzer for image detection."""

import base64
import json
import os
from typing import Any

import boto3

from src.analysis.models import AnalysisResult
from src.exceptions.server_errors import ExternalServiceError, ProcessingError


class BedrockVisionAnalyzer:
    """Analyzes drone images using Bedrock Claude Vision."""

    def __init__(self) -> None:
        """Initialize the Bedrock Vision analyzer."""
        self._model_id = os.environ.get(
            "BEDROCK_MODEL_ID",
            "anthropic.claude-sonnet-4-5-20250929-v1:0",
        )
        self._client = boto3.client(  # type: ignore[call-overload]
            "bedrock-runtime",
        )

    def analyze_image(
        self,
        image_bytes: bytes,
        search_objective: str,
        metadata: dict[str, Any],
    ) -> AnalysisResult:
        """Analyze an image using Bedrock Claude Vision.

        Args:
            image_bytes: Raw image bytes.
            search_objective: What we're looking for.
            metadata: Image metadata (position, heading, etc.).

        Returns:
            Analysis result with detections.

        Raises:
            ExternalServiceError: If Bedrock call fails.
            ProcessingError: If response parsing fails.
        """
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")
        prompt = self._build_prompt(search_objective, metadata)

        try:
            response = self._client.invoke_model(
                modelId=self._model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(
                    {
                        "anthropic_version": "bedrock-2023-05-31",
                        "max_tokens": 4096,
                        "messages": [
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "image",
                                        "source": {
                                            "type": "base64",
                                            "media_type": "image/jpeg",
                                            "data": image_base64,
                                        },
                                    },
                                    {"type": "text", "text": prompt},
                                ],
                            },
                        ],
                    }
                ),
            )
        except Exception as error:
            raise ExternalServiceError(
                f"Bedrock Vision invocation failed: {error}",
                service_name="bedrock",
            ) from error

        return self._parse_response(response)

    def _build_prompt(
        self,
        objective: str,
        metadata: dict[str, Any],
    ) -> str:
        """Build structured analysis prompt.

        Args:
            objective: Search objective description.
            metadata: Image capture metadata.

        Returns:
            Formatted prompt string.
        """
        return f"""Analyze this aerial drone image.

## Search Objective
{objective}

## Image Metadata
- Drone: {metadata.get("drone_id", "unknown")}
- Position: {metadata.get("latitude", 0)}, \
{metadata.get("longitude", 0)}, \
{metadata.get("altitude", 0)}m
- Heading: {metadata.get("heading", 0)} degrees
- Capture Time: {metadata.get("capture_time", "unknown")}

## Instructions
Identify any objects matching the search objective. \
Return ONLY valid JSON:
{{
  "detections": [
    {{
      "label": "description of detected object",
      "confidence": 0.87,
      "bounding_box": {{"x": 120, "y": 340, "width": 80, "height": 45}},
      "reasoning": "Why this matches the search objective"
    }}
  ],
  "scene_description": "Brief description of the scene",
  "search_relevant": true
}}"""

    def _parse_response(self, response: Any) -> AnalysisResult:
        """Parse Bedrock response into structured result.

        Args:
            response: Raw Bedrock response.

        Returns:
            Parsed analysis result.

        Raises:
            ProcessingError: If response parsing fails.
        """
        try:
            response_body = json.loads(response["body"].read())
            content_text: str = response_body["content"][0]["text"]

            json_text = content_text
            if "```json" in json_text:
                json_text = json_text.split("```json")[1].split("```")[0]
            elif "```" in json_text:
                json_text = json_text.split("```")[1].split("```")[0]

            result_data = json.loads(json_text.strip())
            return AnalysisResult(**result_data)
        except (json.JSONDecodeError, KeyError, IndexError) as error:
            raise ProcessingError(
                message=f"Failed to parse Vision response: {error}",
            ) from error
