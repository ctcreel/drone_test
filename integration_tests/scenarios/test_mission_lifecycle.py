"""Integration tests for the mission lifecycle API endpoints."""

import requests


class TestMissionEndpoints:
    """Tests for mission CRUD and lifecycle endpoints."""

    def test_unauthenticated_request_returns_401(
        self, api_url: str,
    ) -> None:
        """Requests without auth token are rejected."""
        response = requests.get(
            f"{api_url}/api/v1/missions",
            timeout=10,
        )
        assert response.status_code == 401

    def test_list_missions(
        self, api_url: str, auth_headers: dict[str, str],
    ) -> None:
        """GET /api/v1/missions returns mission list."""
        response = requests.get(
            f"{api_url}/api/v1/missions",
            headers=auth_headers,
            timeout=10,
        )
        assert response.status_code == 200
        body = response.json()
        assert "missions" in body
        assert isinstance(body["missions"], list)

    def test_get_nonexistent_mission_returns_404(
        self, api_url: str, auth_headers: dict[str, str],
    ) -> None:
        """GET /api/v1/missions/{id} returns 404 for missing mission."""
        response = requests.get(
            f"{api_url}/api/v1/missions/nonexistent-id",
            headers=auth_headers,
            timeout=10,
        )
        assert response.status_code == 404

    def test_approve_nonexistent_mission_returns_404(
        self, api_url: str, auth_headers: dict[str, str],
    ) -> None:
        """POST /api/v1/missions/{id}/approve returns 404 for missing mission."""
        response = requests.post(
            f"{api_url}/api/v1/missions/nonexistent-id/approve",
            headers=auth_headers,
            timeout=10,
        )
        assert response.status_code == 404

    def test_abort_nonexistent_mission_returns_404(
        self, api_url: str, auth_headers: dict[str, str],
    ) -> None:
        """POST /api/v1/missions/{id}/abort returns 404 for missing mission."""
        response = requests.post(
            f"{api_url}/api/v1/missions/nonexistent-id/abort",
            headers=auth_headers,
            timeout=10,
        )
        assert response.status_code == 404

    def test_mission_status_nonexistent_returns_404(
        self, api_url: str, auth_headers: dict[str, str],
    ) -> None:
        """GET /api/v1/missions/{id}/status returns 404 for missing mission."""
        response = requests.get(
            f"{api_url}/api/v1/missions/nonexistent-id/status",
            headers=auth_headers,
            timeout=10,
        )
        assert response.status_code == 404

    def test_list_missions_with_status_filter(
        self, api_url: str, auth_headers: dict[str, str],
    ) -> None:
        """GET /api/v1/missions?status=created filters by status."""
        response = requests.get(
            f"{api_url}/api/v1/missions",
            headers=auth_headers,
            params={"status": "created"},
            timeout=10,
        )
        assert response.status_code == 200
        body = response.json()
        assert "missions" in body
