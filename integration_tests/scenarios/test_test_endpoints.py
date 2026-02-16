"""Integration tests for the test/diagnostic endpoints."""

import requests


class TestTestEndpoints:
    """Tests for unauthenticated test endpoints."""

    def test_post_scenarios_no_auth_required(
        self,
        api_url: str,
    ) -> None:
        """POST /api/v1/test/scenarios does not require auth."""
        response = requests.post(
            f"{api_url}/api/v1/test/scenarios",
            json={"test": True},
            timeout=10,
        )
        assert response.status_code == 200

    def test_scenario_results_no_auth_required(
        self,
        api_url: str,
    ) -> None:
        """GET /api/v1/test/scenarios/{id}/results does not require auth."""
        response = requests.get(
            f"{api_url}/api/v1/test/scenarios/test-123/results",
            timeout=10,
        )
        assert response.status_code == 200
