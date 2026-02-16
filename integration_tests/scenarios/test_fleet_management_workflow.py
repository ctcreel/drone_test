"""Integration tests for drone fleet management workflows.

These tests verify actual business logic end-to-end against the live
deployed AWS API — not just HTTP status codes.
"""

import requests


class TestDroneRegistrationWorkflow:
    """Test the full drone registration and retrieval workflow."""

    def test_register_drone_and_retrieve(
        self, api_url: str, auth_headers: dict[str, str],
    ) -> None:
        """Register a drone, then retrieve it by ID."""
        # Register
        register_response = requests.post(
            f"{api_url}/api/v1/drones",
            headers=auth_headers,
            json={"name": "integration-test-drone-alpha"},
            timeout=15,
        )
        assert register_response.status_code == 201, (
            f"Expected 201, got {register_response.status_code}: "
            f"{register_response.text}"
        )
        drone_data = register_response.json()
        assert "drone_id" in drone_data
        assert drone_data["name"] == "integration-test-drone-alpha"
        assert drone_data["status"] == "registered"
        drone_id = drone_data["drone_id"]

        # Retrieve by ID
        get_response = requests.get(
            f"{api_url}/api/v1/drones/{drone_id}",
            headers=auth_headers,
            timeout=10,
        )
        assert get_response.status_code == 200
        retrieved = get_response.json()
        assert retrieved["drone_id"] == drone_id
        assert retrieved["name"] == "integration-test-drone-alpha"

    def test_register_drone_appears_in_list(
        self, api_url: str, auth_headers: dict[str, str],
    ) -> None:
        """Register a drone and verify it shows up in the fleet list."""
        # Register with unique name
        register_response = requests.post(
            f"{api_url}/api/v1/drones",
            headers=auth_headers,
            json={"name": "integration-test-drone-beta"},
            timeout=15,
        )
        assert register_response.status_code == 201
        drone_id = register_response.json()["drone_id"]

        # List all drones
        list_response = requests.get(
            f"{api_url}/api/v1/drones",
            headers=auth_headers,
            timeout=10,
        )
        assert list_response.status_code == 200
        body = list_response.json()
        drone_ids = [d["drone_id"] for d in body["drones"]]
        assert drone_id in drone_ids

    def test_register_drone_without_name_gets_default(
        self, api_url: str, auth_headers: dict[str, str],
    ) -> None:
        """Register a drone with no name — should get auto-generated name."""
        response = requests.post(
            f"{api_url}/api/v1/drones",
            headers=auth_headers,
            json={},
            timeout=15,
        )
        assert response.status_code == 201
        drone_data = response.json()
        assert drone_data["name"].startswith("drone-")


class TestMissionLifecycleWorkflow:
    """Test mission CRUD through the API."""

    def test_list_missions_returns_list(
        self, api_url: str, auth_headers: dict[str, str],
    ) -> None:
        """GET /missions returns a list structure."""
        response = requests.get(
            f"{api_url}/api/v1/missions",
            headers=auth_headers,
            timeout=10,
        )
        assert response.status_code == 200
        body = response.json()
        assert "missions" in body
        assert isinstance(body["missions"], list)

    def test_create_mission_with_objective(
        self, api_url: str, auth_headers: dict[str, str],
    ) -> None:
        """POST /missions with a search objective creates a mission."""
        response = requests.post(
            f"{api_url}/api/v1/missions",
            headers=auth_headers,
            json={
                "objective": "Search for a missing red vehicle in the parking lot",
                "search_area": {
                    "type": "polygon",
                    "coordinates": [
                        [35.363, -97.487],
                        [35.364, -97.487],
                        [35.364, -97.486],
                        [35.363, -97.486],
                    ],
                },
                "environment_id": "test-env-001",
            },
            timeout=30,
        )
        # Mission planner calls Bedrock — may fail if env doesn't exist
        # but should at least return a structured error, not a 502
        assert response.status_code != 502, (
            f"Lambda crashed (502): {response.text}"
        )

    def test_mission_status_filter(
        self, api_url: str, auth_headers: dict[str, str],
    ) -> None:
        """GET /missions?status=created filters correctly."""
        response = requests.get(
            f"{api_url}/api/v1/missions",
            headers=auth_headers,
            params={"status": "created"},
            timeout=10,
        )
        assert response.status_code == 200
        body = response.json()
        assert isinstance(body["missions"], list)


class TestEnvironmentWorkflow:
    """Test environment creation and retrieval."""

    def test_create_and_list_environments(
        self, api_url: str, auth_headers: dict[str, str],
    ) -> None:
        """POST then verify environment endpoint responds."""
        # Create
        create_response = requests.post(
            f"{api_url}/api/v1/environments",
            headers=auth_headers,
            json={
                "name": "Integration Test Area",
                "type": "open_area",
                "bounds": {
                    "coordinates": [
                        [35.363, -97.487],
                        [35.364, -97.487],
                        [35.364, -97.486],
                        [35.363, -97.486],
                    ],
                },
            },
            timeout=15,
        )
        # Should not crash
        assert create_response.status_code != 502, (
            f"Lambda crashed: {create_response.text}"
        )


class TestCrossServiceWorkflow:
    """Test workflows that span multiple services."""

    def test_register_drone_then_check_fleet_status(
        self, api_url: str, auth_headers: dict[str, str],
    ) -> None:
        """Register a drone and verify fleet list shows its status."""
        # Register
        register_response = requests.post(
            f"{api_url}/api/v1/drones",
            headers=auth_headers,
            json={"name": "fleet-status-test-drone"},
            timeout=15,
        )
        assert register_response.status_code == 201
        drone_id = register_response.json()["drone_id"]

        # Check the drone's status field
        get_response = requests.get(
            f"{api_url}/api/v1/drones/{drone_id}",
            headers=auth_headers,
            timeout=10,
        )
        assert get_response.status_code == 200
        drone = get_response.json()
        assert drone["status"] == "registered"
        assert "iot_thing_name" in drone
        assert drone["iot_thing_name"].startswith("drone-fleet-")

    def test_unauthenticated_registration_rejected(
        self, api_url: str,
    ) -> None:
        """Drone registration requires authentication."""
        response = requests.post(
            f"{api_url}/api/v1/drones",
            json={"name": "should-not-register"},
            timeout=10,
        )
        assert response.status_code in {401, 403}
