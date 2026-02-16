"""Integration tests for the detection API endpoints."""

import requests


class TestDetectionEndpoints:
    """Tests for detection endpoints under missions."""

    def test_unauthenticated_detection_returns_401(
        self,
        api_url: str,
    ) -> None:
        """Requests without auth token are rejected."""
        response = requests.get(
            f"{api_url}/api/v1/missions/test-mission/detections",
            timeout=10,
        )
        assert response.status_code == 401

    def test_list_detections_responds(
        self,
        api_url: str,
        auth_headers: dict[str, str],
    ) -> None:
        """GET /api/v1/missions/{id}/detections returns a response."""
        response = requests.get(
            f"{api_url}/api/v1/missions/nonexistent-id/detections",
            headers=auth_headers,
            timeout=10,
        )
        # Falls through to default handler, returns 200
        assert response.status_code == 200

    def test_review_detection_responds(
        self,
        api_url: str,
        auth_headers: dict[str, str],
    ) -> None:
        """POST /api/v1/missions/{id}/detections/{id}/review returns a response."""
        response = requests.post(
            f"{api_url}/api/v1/missions/nonexistent-id/detections/det-id/review",
            headers=auth_headers,
            json={"decision": "confirmed"},
            timeout=10,
        )
        # Falls through to default handler, returns 200
        assert response.status_code == 200
