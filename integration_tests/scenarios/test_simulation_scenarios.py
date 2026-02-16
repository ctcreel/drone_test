"""Pytest-based simulation scenario tests.

Each test submits a scenario definition to the simulation API, waits
for completion, and validates the results against the JSON assertion
definitions. Tests are skipped when the simulation environment is not
available (controlled by the ``SIMULATION_RUNNING`` environment
variable or a connectivity probe).
"""

import os
from pathlib import Path

import pytest
import requests

from integration_tests.runner import (
    ScenarioStatus,
    load_scenario_definition,
    run_scenario,
)

# ---------------------------------------------------------------------------
# Markers & constants
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.simulation

DEFINITIONS_DIRECTORY = Path(__file__).parent / "definitions"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _simulation_is_available() -> bool:
    """Check whether the simulation environment is reachable.

    Returns ``True`` when the ``SIMULATION_RUNNING`` env var is set to
    a truthy value **or** the API base URL responds to a health-check
    probe within 5 seconds.
    """
    simulation_flag = os.environ.get("SIMULATION_RUNNING", "").lower()
    if simulation_flag in {"1", "true", "yes"}:
        return True

    api_base = os.environ.get("API_BASE_URL", "")
    if not api_base:
        return False

    try:
        response = requests.get(
            f"{api_base.rstrip('/')}/api/v1/test/scenarios",
            timeout=5,
        )
    except (requests.ConnectionError, requests.Timeout):
        return False
    else:
        return response.status_code < 500


def _load_definition(scenario_name: str):
    """Load a scenario definition by name from the definitions directory."""
    path = DEFINITIONS_DIRECTORY / f"{scenario_name}.json"
    assert path.exists(), f"Scenario definition not found: {path}"
    return load_scenario_definition(path)


def _get_api_endpoint():
    """Retrieve the API endpoint from the environment."""
    return os.environ.get("API_BASE_URL", "").rstrip("/")


def _get_auth_token():
    """Retrieve the auth token from the environment."""
    return os.environ.get("AUTH_TOKEN")


# ---------------------------------------------------------------------------
# Skip condition
# ---------------------------------------------------------------------------

simulation_required = pytest.mark.skipif(
    not _simulation_is_available(),
    reason="Simulation environment is not running or not reachable",
)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@simulation_required
class TestBasicAreaSearch:
    """Basic area search scenario: 3 drones in open area."""

    SCENARIO_NAME = "basic_area_search"

    def test_scenario_completes_successfully(self):
        definition = _load_definition(self.SCENARIO_NAME)
        result = run_scenario(_get_api_endpoint(), definition, _get_auth_token())

        assert result.status == ScenarioStatus.COMPLETED, (
            f"Scenario did not complete: {result.error_message}"
        )

    def test_all_assertions_pass(self):
        definition = _load_definition(self.SCENARIO_NAME)
        result = run_scenario(_get_api_endpoint(), definition, _get_auth_token())

        for assertion_result in result.assertion_results:
            assert assertion_result.passed, (
                f"Assertion '{assertion_result.name}' failed: {assertion_result.message}"
            )

    def test_definition_is_valid(self):
        """Verify the scenario definition loads without errors."""
        definition = _load_definition(self.SCENARIO_NAME)
        assert definition.drone_count == 3
        assert definition.environment == "open_area"
        assert len(definition.assertions) >= 5


@simulation_required
class TestObstacleAvoidance:
    """Obstacle avoidance scenario: 2 drones in urban block."""

    SCENARIO_NAME = "obstacle_avoidance"

    def test_scenario_completes_successfully(self):
        definition = _load_definition(self.SCENARIO_NAME)
        result = run_scenario(_get_api_endpoint(), definition, _get_auth_token())

        assert result.status == ScenarioStatus.COMPLETED, (
            f"Scenario did not complete: {result.error_message}"
        )

    def test_all_assertions_pass(self):
        definition = _load_definition(self.SCENARIO_NAME)
        result = run_scenario(_get_api_endpoint(), definition, _get_auth_token())

        for assertion_result in result.assertion_results:
            assert assertion_result.passed, (
                f"Assertion '{assertion_result.name}' failed: {assertion_result.message}"
            )

    def test_definition_is_valid(self):
        """Verify the scenario definition loads without errors."""
        definition = _load_definition(self.SCENARIO_NAME)
        assert definition.drone_count == 2
        assert definition.environment == "urban_block"
        assert any(assertion.name == "no_collisions" for assertion in definition.assertions)
        assert any(
            assertion.name == "minimum_obstacle_clearance_meters" and assertion.minimum == 10
            for assertion in definition.assertions
        )


@simulation_required
class TestConnectivityLoss:
    """Connectivity loss scenario: 3 drones, brief outage on drone-002."""

    SCENARIO_NAME = "connectivity_loss"

    def test_scenario_completes_successfully(self):
        definition = _load_definition(self.SCENARIO_NAME)
        result = run_scenario(_get_api_endpoint(), definition, _get_auth_token())

        assert result.status == ScenarioStatus.COMPLETED, (
            f"Scenario did not complete: {result.error_message}"
        )

    def test_all_assertions_pass(self):
        definition = _load_definition(self.SCENARIO_NAME)
        result = run_scenario(_get_api_endpoint(), definition, _get_auth_token())

        for assertion_result in result.assertion_results:
            assert assertion_result.passed, (
                f"Assertion '{assertion_result.name}' failed: {assertion_result.message}"
            )

    def test_definition_has_fault_injection(self):
        """Verify fault injection is configured."""
        definition = _load_definition(self.SCENARIO_NAME)
        assert definition.fault_injections is not None
        assert len(definition.fault_injections) == 1
        injection = definition.fault_injections[0]
        assert injection["target_drone"] == "drone-002"
        assert injection["duration_seconds"] == 30


@simulation_required
class TestExtendedConnectivityLoss:
    """Extended connectivity loss: drone-001 offline for 5 minutes."""

    SCENARIO_NAME = "extended_connectivity_loss"

    def test_scenario_completes_successfully(self):
        definition = _load_definition(self.SCENARIO_NAME)
        result = run_scenario(_get_api_endpoint(), definition, _get_auth_token())

        assert result.status == ScenarioStatus.COMPLETED, (
            f"Scenario did not complete: {result.error_message}"
        )

    def test_all_assertions_pass(self):
        definition = _load_definition(self.SCENARIO_NAME)
        result = run_scenario(_get_api_endpoint(), definition, _get_auth_token())

        for assertion_result in result.assertion_results:
            assert assertion_result.passed, (
                f"Assertion '{assertion_result.name}' failed: {assertion_result.message}"
            )

    def test_definition_has_state_transition_assertion(self):
        """Verify state transition sequence is defined."""
        definition = _load_definition(self.SCENARIO_NAME)
        state_assertion = next(
            (
                assertion
                for assertion in definition.assertions
                if assertion.name == "drone_state_transition"
            ),
            None,
        )
        assert state_assertion is not None
        assert state_assertion.expected_sequence == [
            "EXECUTING",
            "DEGRADED",
            "HOLDING",
            "RETURNING",
        ]


@simulation_required
class TestFleetCoordination:
    """Fleet coordination scenario: 5 drones over a large area."""

    SCENARIO_NAME = "fleet_coordination"

    def test_scenario_completes_successfully(self):
        definition = _load_definition(self.SCENARIO_NAME)
        result = run_scenario(_get_api_endpoint(), definition, _get_auth_token())

        assert result.status == ScenarioStatus.COMPLETED, (
            f"Scenario did not complete: {result.error_message}"
        )

    def test_all_assertions_pass(self):
        definition = _load_definition(self.SCENARIO_NAME)
        result = run_scenario(_get_api_endpoint(), definition, _get_auth_token())

        for assertion_result in result.assertion_results:
            assert assertion_result.passed, (
                f"Assertion '{assertion_result.name}' failed: {assertion_result.message}"
            )

    def test_definition_is_valid(self):
        """Verify the scenario definition loads without errors."""
        definition = _load_definition(self.SCENARIO_NAME)
        assert definition.drone_count == 5
        assert definition.search_area_dimensions is not None
        assert definition.search_area_dimensions["width_meters"] == 1000
        assert definition.search_area_dimensions["height_meters"] == 500
        assert any(
            assertion.name == "minimum_drone_separation_meters" and assertion.minimum == 20
            for assertion in definition.assertions
        )
        assert any(
            assertion.name == "area_coverage_percent" and assertion.minimum == 90
            for assertion in definition.assertions
        )


@simulation_required
class TestImagePipeline:
    """Image pipeline scenario: 2 drones, 3 planted targets."""

    SCENARIO_NAME = "image_pipeline"

    def test_scenario_completes_successfully(self):
        definition = _load_definition(self.SCENARIO_NAME)
        result = run_scenario(_get_api_endpoint(), definition, _get_auth_token())

        assert result.status == ScenarioStatus.COMPLETED, (
            f"Scenario did not complete: {result.error_message}"
        )

    def test_all_assertions_pass(self):
        definition = _load_definition(self.SCENARIO_NAME)
        result = run_scenario(_get_api_endpoint(), definition, _get_auth_token())

        for assertion_result in result.assertion_results:
            assert assertion_result.passed, (
                f"Assertion '{assertion_result.name}' failed: {assertion_result.message}"
            )

    def test_definition_is_valid(self):
        """Verify the scenario definition loads without errors."""
        definition = _load_definition(self.SCENARIO_NAME)
        assert definition.drone_count == 2
        assert definition.planted_targets == 3
        assert any(assertion.name == "images_captured" for assertion in definition.assertions)
        assert any(assertion.name == "targets_detected" for assertion in definition.assertions)


@simulation_required
class TestDynamicReplanning:
    """Dynamic replanning scenario: detection triggers reallocation."""

    SCENARIO_NAME = "dynamic_replanning"

    def test_scenario_completes_successfully(self):
        definition = _load_definition(self.SCENARIO_NAME)
        result = run_scenario(_get_api_endpoint(), definition, _get_auth_token())

        assert result.status == ScenarioStatus.COMPLETED, (
            f"Scenario did not complete: {result.error_message}"
        )

    def test_all_assertions_pass(self):
        definition = _load_definition(self.SCENARIO_NAME)
        result = run_scenario(_get_api_endpoint(), definition, _get_auth_token())

        for assertion_result in result.assertion_results:
            assert assertion_result.passed, (
                f"Assertion '{assertion_result.name}' failed: {assertion_result.message}"
            )

    def test_definition_is_valid(self):
        """Verify the scenario definition loads without errors."""
        definition = _load_definition(self.SCENARIO_NAME)
        assert definition.drone_count == 3
        assert definition.planted_targets == 1
        assert any(
            assertion.name == "reallocation_triggered" for assertion in definition.assertions
        )
        assert any(
            assertion.name == "drone_redirected_to_detection_area"
            for assertion in definition.assertions
        )


# ---------------------------------------------------------------------------
# All-scenarios parametrized test
# ---------------------------------------------------------------------------


def _all_scenario_names():
    """Discover all scenario names from the definitions directory."""
    return [path.stem for path in sorted(DEFINITIONS_DIRECTORY.glob("*.json"))]


@simulation_required
@pytest.mark.parametrize("scenario_name", _all_scenario_names())
def test_scenario_assertions_pass(scenario_name):
    """Run a scenario and verify all its assertions pass.

    This parametrized test provides a single entry point that executes
    every discovered scenario definition.
    """
    definition = _load_definition(scenario_name)
    result = run_scenario(_get_api_endpoint(), definition, _get_auth_token())

    assert result.status != ScenarioStatus.TIMED_OUT, (
        f"Scenario '{scenario_name}' timed out after {definition.timeout_seconds}s"
    )
    assert result.status == ScenarioStatus.COMPLETED, (
        f"Scenario '{scenario_name}' failed: {result.error_message}"
    )

    failed_assertions = [
        assertion_result
        for assertion_result in result.assertion_results
        if not assertion_result.passed
    ]
    assert not failed_assertions, (
        f"Scenario '{scenario_name}' had {len(failed_assertions)} failed assertion(s): "
        + ", ".join(
            f"{assertion_result.name}: {assertion_result.message}"
            for assertion_result in failed_assertions
        )
    )
