"""Integration test orchestration runner.

Submits simulation scenarios to the test API, polls for results,
and generates a summary report. Designed to be invoked from the
Makefile or directly via ``python -m integration_tests.runner``.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

import requests
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from collections.abc import Sequence

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFINITIONS_DIRECTORY: Path = Path(__file__).parent / "scenarios" / "definitions"
RESULTS_DIRECTORY: Path = Path(__file__).parent / "results"
DEFAULT_POLL_INTERVAL_SECONDS: int = 5
DEFAULT_TIMEOUT_SECONDS: int = 900
REQUEST_TIMEOUT_SECONDS: int = 30


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ScenarioStatus(StrEnum):
    """Possible states of a submitted scenario."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class AssertionDefinition(BaseModel):
    """A single assertion from a scenario JSON file."""

    name: str
    threshold_seconds: int | None = None
    minimum: float | None = None
    maximum: float | None = None
    required: bool | None = None
    minimum_confidence: float | None = None
    target_drone: str | None = None
    expected_sequence: list[str] | None = None


class ScenarioDefinition(BaseModel):
    """Parsed scenario definition loaded from a JSON file."""

    scenario_name: str
    description: str
    drone_count: int = Field(ge=1)
    environment: str
    objective: str
    timeout_seconds: int = Field(default=DEFAULT_TIMEOUT_SECONDS, ge=1)
    assertions: list[AssertionDefinition]

    # Optional fields that only some scenarios use
    fault_injections: list[dict[str, object]] | None = None
    planted_targets: int | None = None
    search_area_dimensions: dict[str, float] | None = None


class AssertionResult(BaseModel):
    """Result of evaluating a single assertion."""

    name: str
    passed: bool
    message: str = ""
    actual_value: float | str | bool | None = None


class ScenarioResult(BaseModel):
    """Aggregated result of a completed scenario run."""

    scenario_name: str
    status: ScenarioStatus
    scenario_id: str = ""
    duration_seconds: float = 0.0
    assertion_results: list[AssertionResult] = Field(default_factory=list)
    error_message: str = ""


class RunReport(BaseModel):
    """Summary report for an entire integration test run."""

    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
    )
    total_scenarios: int = 0
    passed: int = 0
    failed: int = 0
    timed_out: int = 0
    scenario_results: list[ScenarioResult] = Field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        """Return True when every scenario passed."""
        return self.failed == 0 and self.timed_out == 0


# ---------------------------------------------------------------------------
# Scenario discovery
# ---------------------------------------------------------------------------


def discover_scenario_files(
    scenario_names: Sequence[str] | None = None,
) -> list[Path]:
    """Find scenario definition JSON files.

    Args:
        scenario_names: Optional list of scenario names to filter by.
            When ``None``, all JSON files in the definitions directory
            are returned.

    Returns:
        Sorted list of paths to scenario definition files.
    """
    all_files = sorted(DEFINITIONS_DIRECTORY.glob("*.json"))

    if scenario_names is None:
        return all_files

    requested = set(scenario_names)
    return [path for path in all_files if path.stem in requested]


def load_scenario_definition(path: Path) -> ScenarioDefinition:
    """Load and validate a scenario definition from a JSON file.

    Args:
        path: Path to the scenario JSON file.

    Returns:
        Validated scenario definition.
    """
    raw_text = path.read_text(encoding="utf-8")
    raw_data = json.loads(raw_text)
    return ScenarioDefinition.model_validate(raw_data)


# ---------------------------------------------------------------------------
# API interaction
# ---------------------------------------------------------------------------


def submit_scenario(
    api_endpoint: str,
    definition: ScenarioDefinition,
    auth_token: str | None = None,
) -> str:
    """Submit a scenario to the test API and return the scenario ID.

    Args:
        api_endpoint: Base URL of the API (no trailing slash).
        definition: The scenario definition to submit.
        auth_token: Optional authentication token.

    Returns:
        The server-assigned scenario ID.

    Raises:
        RuntimeError: If the API returns a non-200 status.
    """
    url = f"{api_endpoint}/api/v1/test/scenarios"
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if auth_token:
        headers["Authorization"] = auth_token

    payload = definition.model_dump(exclude_none=True)

    response = requests.post(
        url,
        json=payload,
        headers=headers,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )

    if response.status_code != 200:
        scenario_name = definition.scenario_name
        status_code = response.status_code
        message = f"Failed to submit scenario '{scenario_name}': HTTP {status_code}"
        raise RuntimeError(message)

    body = response.json()
    scenario_id: str = body.get("scenario_id", body.get("id", ""))
    return scenario_id


def poll_scenario_results(
    api_endpoint: str,
    scenario_id: str,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    poll_interval_seconds: int = DEFAULT_POLL_INTERVAL_SECONDS,
    auth_token: str | None = None,
) -> dict[str, object]:
    """Poll the results endpoint until the scenario completes or times out.

    Args:
        api_endpoint: Base URL of the API (no trailing slash).
        scenario_id: The ID of the submitted scenario.
        timeout_seconds: Maximum seconds to wait for completion.
        poll_interval_seconds: Seconds between poll requests.
        auth_token: Optional authentication token.

    Returns:
        The raw results payload from the API.

    Raises:
        TimeoutError: If the scenario does not complete within the timeout.
    """
    url = f"{api_endpoint}/api/v1/test/scenarios/{scenario_id}/results"
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if auth_token:
        headers["Authorization"] = auth_token

    deadline = time.monotonic() + timeout_seconds

    while time.monotonic() < deadline:
        response = requests.get(
            url,
            headers=headers,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )

        if response.status_code != 200:
            time.sleep(poll_interval_seconds)
            continue

        body: dict[str, object] = response.json()
        status = str(body.get("status", ""))

        if status in {ScenarioStatus.COMPLETED, ScenarioStatus.FAILED}:
            return body

        time.sleep(poll_interval_seconds)

    message = f"Scenario '{scenario_id}' did not complete within {timeout_seconds}s"
    raise TimeoutError(message)


# ---------------------------------------------------------------------------
# Assertion evaluation
# ---------------------------------------------------------------------------


def evaluate_assertions(
    definition: ScenarioDefinition,
    raw_results: dict[str, object],
) -> list[AssertionResult]:
    """Evaluate scenario assertions against the raw API results.

    Args:
        definition: The original scenario definition.
        raw_results: The raw results payload from the API.

    Returns:
        List of assertion evaluation results.
    """
    results_data: dict[str, object] = dict(raw_results.get("results", {}) or {})  # type: ignore[arg-type]
    evaluated: list[AssertionResult] = []

    for assertion in definition.assertions:
        result = _evaluate_single_assertion(assertion, results_data)
        evaluated.append(result)

    return evaluated


def _evaluate_single_assertion(
    assertion: AssertionDefinition,
    results_data: dict[str, object],
) -> AssertionResult:
    """Evaluate a single assertion against the results data.

    Args:
        assertion: The assertion definition to evaluate.
        results_data: The results data from the completed scenario.

    Returns:
        The evaluation result for this assertion.
    """
    actual_value = results_data.get(assertion.name)

    if actual_value is None:
        return AssertionResult(
            name=assertion.name,
            passed=False,
            message=f"Assertion '{assertion.name}' not found in results",
        )

    passed, result_value, message = _check_assertion_value(assertion, actual_value)

    return AssertionResult(
        name=assertion.name,
        passed=passed,
        actual_value=result_value,
        message=message,
    )


def _check_assertion_value(
    assertion: AssertionDefinition,
    actual_value: object,
) -> tuple[bool, float | str | bool | None, str]:
    """Check an assertion value against its definition criteria.

    Args:
        assertion: The assertion definition with thresholds/limits.
        actual_value: The actual value from scenario results.

    Returns:
        Tuple of (passed, actual_value_for_report, failure_message).
    """
    # Boolean required check
    if assertion.required is not None:
        passed = bool(actual_value) == assertion.required
        message = "" if passed else f"Expected required={assertion.required}, got {actual_value}"
        return passed, bool(actual_value), message

    # Numeric threshold (upper bound on time)
    if assertion.threshold_seconds is not None:
        numeric_value = float(str(actual_value))
        passed = numeric_value <= assertion.threshold_seconds
        message = (
            ""
            if passed
            else (f"Took {numeric_value}s, threshold is {assertion.threshold_seconds}s")
        )
        return passed, numeric_value, message

    # Numeric minimum or minimum confidence (both are lower-bound checks)
    lower_bound = (
        assertion.minimum if assertion.minimum is not None else assertion.minimum_confidence
    )
    if lower_bound is not None:
        numeric_value = float(str(actual_value))
        passed = numeric_value >= lower_bound
        label = "minimum" if assertion.minimum is not None else "minimum confidence"
        message = "" if passed else f"Got {numeric_value}, {label} is {lower_bound}"
        return passed, numeric_value, message

    # Numeric maximum
    if assertion.maximum is not None:
        numeric_value = float(str(actual_value))
        passed = numeric_value <= assertion.maximum
        message = "" if passed else f"Got {numeric_value}, maximum is {assertion.maximum}"
        return passed, numeric_value, message

    # Expected sequence (state transitions)
    if assertion.expected_sequence is not None:
        actual_sequence = list(actual_value) if isinstance(actual_value, list) else []
        passed = actual_sequence == assertion.expected_sequence
        message = (
            ""
            if passed
            else (f"Expected sequence {assertion.expected_sequence}, got {actual_sequence}")
        )
        return passed, str(actual_sequence), message

    # Fallback: treat as truthy check
    passed = bool(actual_value)
    message = "" if passed else f"Assertion '{assertion.name}' was falsy: {actual_value}"
    return passed, str(actual_value), message


# ---------------------------------------------------------------------------
# Scenario execution
# ---------------------------------------------------------------------------


def run_scenario(
    api_endpoint: str,
    definition: ScenarioDefinition,
    auth_token: str | None = None,
) -> ScenarioResult:
    """Execute a single scenario end-to-end.

    Submits the scenario, polls for completion, evaluates assertions,
    and returns the result.

    Args:
        api_endpoint: Base URL of the API (no trailing slash).
        definition: The scenario definition to execute.
        auth_token: Optional authentication token.

    Returns:
        The scenario result including assertion evaluations.
    """
    start_time = time.monotonic()

    try:
        scenario_id = submit_scenario(api_endpoint, definition, auth_token)
    except RuntimeError as error:
        return ScenarioResult(
            scenario_name=definition.scenario_name,
            status=ScenarioStatus.FAILED,
            duration_seconds=time.monotonic() - start_time,
            error_message=str(error),
        )

    try:
        raw_results = poll_scenario_results(
            api_endpoint=api_endpoint,
            scenario_id=scenario_id,
            timeout_seconds=definition.timeout_seconds,
            auth_token=auth_token,
        )
    except TimeoutError:
        return ScenarioResult(
            scenario_name=definition.scenario_name,
            status=ScenarioStatus.TIMED_OUT,
            scenario_id=scenario_id,
            duration_seconds=time.monotonic() - start_time,
            error_message=f"Timed out after {definition.timeout_seconds}s",
        )

    assertion_results = evaluate_assertions(definition, raw_results)
    all_assertions_passed = all(result.passed for result in assertion_results)

    return ScenarioResult(
        scenario_name=definition.scenario_name,
        status=ScenarioStatus.COMPLETED if all_assertions_passed else ScenarioStatus.FAILED,
        scenario_id=scenario_id,
        duration_seconds=time.monotonic() - start_time,
        assertion_results=assertion_results,
        error_message="" if all_assertions_passed else "One or more assertions failed",
    )


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------


def generate_report(scenario_results: list[ScenarioResult]) -> RunReport:
    """Generate a summary report from scenario results.

    Args:
        scenario_results: List of individual scenario results.

    Returns:
        Aggregated run report.
    """
    passed_count = sum(
        1 for result in scenario_results if result.status == ScenarioStatus.COMPLETED
    )
    failed_count = sum(1 for result in scenario_results if result.status == ScenarioStatus.FAILED)
    timed_out_count = sum(
        1 for result in scenario_results if result.status == ScenarioStatus.TIMED_OUT
    )

    return RunReport(
        total_scenarios=len(scenario_results),
        passed=passed_count,
        failed=failed_count,
        timed_out=timed_out_count,
        scenario_results=scenario_results,
    )


def write_report(report: RunReport) -> Path:
    """Write the run report to the results directory as JSON.

    Args:
        report: The run report to persist.

    Returns:
        Path to the written report file.
    """
    RESULTS_DIRECTORY.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    report_path = RESULTS_DIRECTORY / f"run_{timestamp}.json"
    report_path.write_text(
        report.model_dump_json(indent=2),
        encoding="utf-8",
    )
    return report_path


def print_report_summary(report: RunReport) -> None:
    """Print a human-readable summary of the run report to stdout.

    Args:
        report: The run report to summarize.
    """
    print("\n" + "=" * 70)  # noqa: T201
    print("INTEGRATION TEST REPORT")  # noqa: T201
    print("=" * 70)  # noqa: T201
    print(f"Timestamp: {report.timestamp}")  # noqa: T201
    print(f"Total:     {report.total_scenarios}")  # noqa: T201
    print(f"Passed:    {report.passed}")  # noqa: T201
    print(f"Failed:    {report.failed}")  # noqa: T201
    print(f"Timed Out: {report.timed_out}")  # noqa: T201
    print("-" * 70)  # noqa: T201

    for scenario_result in report.scenario_results:
        status_indicator = "PASS" if scenario_result.status == ScenarioStatus.COMPLETED else "FAIL"
        print(  # noqa: T201
            f"  [{status_indicator}] {scenario_result.scenario_name} "
            f"({scenario_result.duration_seconds:.1f}s)"
        )

        if scenario_result.error_message:
            print(f"         Error: {scenario_result.error_message}")  # noqa: T201

        for assertion_result in scenario_result.assertion_results:
            if not assertion_result.passed:
                print(f"         FAIL: {assertion_result.name} - {assertion_result.message}")  # noqa: T201

    print("=" * 70)  # noqa: T201
    overall = "ALL PASSED" if report.all_passed else "FAILURES DETECTED"
    print(f"Result: {overall}")  # noqa: T201
    print("=" * 70 + "\n")  # noqa: T201


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main(
    scenario_names: Sequence[str] | None = None,
    api_endpoint: str | None = None,
    auth_token: str | None = None,
) -> int:
    """Run integration test scenarios and return an exit code.

    Args:
        scenario_names: Optional list of scenario names to run. When
            ``None``, all discovered scenarios are executed.
        api_endpoint: Base URL of the API. Falls back to the
            ``API_BASE_URL`` environment variable.
        auth_token: Authentication token. Falls back to the
            ``AUTH_TOKEN`` environment variable.

    Returns:
        Exit code: 0 if all scenarios pass, 1 otherwise.
    """
    resolved_endpoint = api_endpoint or os.environ.get("API_BASE_URL", "")
    resolved_token = auth_token or os.environ.get("AUTH_TOKEN")

    if not resolved_endpoint:
        print("ERROR: API_BASE_URL environment variable is not set")  # noqa: T201
        return 1

    resolved_endpoint = resolved_endpoint.rstrip("/")

    # Discover and load scenario definitions
    scenario_files = discover_scenario_files(scenario_names)
    if not scenario_files:
        print("ERROR: No scenario definitions found")  # noqa: T201
        return 1

    definitions: list[ScenarioDefinition] = []
    for path in scenario_files:
        definition = load_scenario_definition(path)
        definitions.append(definition)

    print(f"Running {len(definitions)} scenario(s)...")  # noqa: T201

    # Execute each scenario
    all_results: list[ScenarioResult] = []
    for definition in definitions:
        print(f"  Submitting: {definition.scenario_name} ...")  # noqa: T201
        result = run_scenario(resolved_endpoint, definition, resolved_token)
        all_results.append(result)
        print(f"  Completed:  {definition.scenario_name} -> {result.status}")  # noqa: T201

    # Generate and output report
    report = generate_report(all_results)
    report_path = write_report(report)
    print_report_summary(report)
    print(f"Report written to: {report_path}")  # noqa: T201

    return 0 if report.all_passed else 1


if __name__ == "__main__":
    scenario_arguments = sys.argv[1:] or None
    exit_code = main(scenario_names=scenario_arguments)
    sys.exit(exit_code)
