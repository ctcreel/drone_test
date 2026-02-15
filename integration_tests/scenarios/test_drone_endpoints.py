"""Integration tests for the drone API endpoints."""

import requests


class TestDroneEndpoints:
    """Tests for drone CRUD endpoints."""

    def test_unauthenticated_request_returns_401(
        self, api_url: str,
    ) -> None:
        """Requests without auth token are rejected."""
        response = requests.get(
            f"{api_url}/api/v1/drones",
            timeout=10,
        )
        assert response.status_code == 401

    def test_list_drones(
        self, api_url: str, auth_headers: dict[str, str],
    ) -> None:
        """GET /api/v1/drones returns drone list."""
        response = requests.get(
            f"{api_url}/api/v1/drones",
            headers=auth_headers,
            timeout=10,
        )
        assert response.status_code == 200
        body = response.json()
        assert "drones" in body
        assert isinstance(body["drones"], list)

    def test_get_nonexistent_drone_returns_404(
        self, api_url: str, auth_headers: dict[str, str],
    ) -> None:
        """GET /api/v1/drones/{id} returns 404 for missing drone."""
        response = requests.get(
            f"{api_url}/api/v1/drones/nonexistent-drone-id",
            headers=auth_headers,
            timeout=10,
        )
        assert response.status_code == 404
