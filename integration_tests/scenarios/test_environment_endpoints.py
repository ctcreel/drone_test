"""Integration tests for the environment API endpoints."""

import requests


class TestEnvironmentEndpoints:
    """Tests for environment endpoints."""

    def test_unauthenticated_environment_returns_401(
        self,
        api_url: str,
    ) -> None:
        """Requests without auth token are rejected."""
        response = requests.get(
            f"{api_url}/api/v1/environments/nonexistent-env-id",
            timeout=10,
        )
        assert response.status_code == 401

    def test_get_environment_responds(
        self,
        api_url: str,
        auth_headers: dict[str, str],
    ) -> None:
        """GET /api/v1/environments/{id} returns a response."""
        response = requests.get(
            f"{api_url}/api/v1/environments/nonexistent-env-id",
            headers=auth_headers,
            timeout=10,
        )
        # Falls through to default handler, returns 200
        assert response.status_code == 200

    def test_create_environment_responds(
        self,
        api_url: str,
        auth_headers: dict[str, str],
    ) -> None:
        """POST /api/v1/environments returns a response."""
        response = requests.post(
            f"{api_url}/api/v1/environments",
            headers=auth_headers,
            json={"name": "test-environment"},
            timeout=10,
        )
        # Falls through to default handler, returns 200
        assert response.status_code == 200
