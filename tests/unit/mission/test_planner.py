"""Tests for mission planner (Bedrock integration)."""

import json
from io import BytesIO
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.environment.models import EnvironmentModel
from src.exceptions.server_errors import ExternalServiceError, ProcessingError
from src.mission.models import (
    Coordinate,
    MissionObjective,
    SearchArea,
    SearchPattern,
)
from src.mission.planner import _build_planning_prompt, plan_mission


def _make_objective() -> MissionObjective:
    return MissionObjective(
        description="Find missing hiker in forest area",
        search_area=SearchArea(
            coordinates=[[
                Coordinate(latitude=40.0, longitude=-74.0),
                Coordinate(latitude=40.1, longitude=-74.0),
                Coordinate(latitude=40.1, longitude=-73.9),
                Coordinate(latitude=40.0, longitude=-74.0),
            ]],
        ),
        environment_id="env-001",
    )


def _make_environment() -> EnvironmentModel:
    return EnvironmentModel(
        environment_id="env-001",
        name="Forest Area",
        bounds=[[40.0, -74.0], [40.1, -73.9]],
    )


def _make_plan_json() -> dict[str, Any]:
    return {
        "search_pattern": "parallel_tracks",
        "reasoning": "Open area best for parallel tracks",
        "drone_assignments": [
            {
                "drone_id": "drone-001",
                "role": "primary_search",
                "segments": [
                    {
                        "waypoints": [
                            {
                                "latitude": 40.0,
                                "longitude": -74.0,
                                "altitude": 50.0,
                                "speed": 5.0,
                                "camera_interval_seconds": 3,
                            },
                        ],
                        "altitude": 50.0,
                        "camera_interval_seconds": 3,
                    },
                ],
            },
        ],
        "estimated_duration_seconds": 600,
        "estimated_coverage_percent": 95.0,
        "safety_notes": ["Clear weather expected"],
    }


def _mock_bedrock_response(plan_json: dict[str, Any]) -> dict[str, Any]:
    body_content = json.dumps({
        "content": [{"text": json.dumps(plan_json)}],
    }).encode()
    return {"body": BytesIO(body_content)}


class TestBuildPlanningPrompt:
    """Tests for prompt construction."""

    def test_prompt_includes_objective(self) -> None:
        prompt = _build_planning_prompt(
            _make_objective(), _make_environment(), [],
        )
        assert "Find missing hiker" in prompt

    def test_prompt_includes_environment(self) -> None:
        prompt = _build_planning_prompt(
            _make_objective(), _make_environment(), [],
        )
        assert "Buildings: 0" in prompt
        assert "No-fly zones: 0" in prompt

    def test_prompt_with_drones(self) -> None:
        drones = [
            {
                "drone_id": "drone-001",
                "battery_percent": 80,
                "latitude": 40.05,
                "longitude": -73.95,
            },
        ]
        prompt = _build_planning_prompt(
            _make_objective(), _make_environment(), drones,
        )
        assert "drone-001" in prompt
        assert "battery=80%" in prompt

    def test_prompt_without_drones(self) -> None:
        prompt = _build_planning_prompt(
            _make_objective(), _make_environment(), [],
        )
        assert "No drones available" in prompt


class TestPlanMission:
    """Tests for plan_mission function."""

    @patch("src.mission.planner.boto3")
    def test_successful_planning(self, mock_boto3: MagicMock) -> None:
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client

        plan_json = _make_plan_json()
        mock_client.invoke_model.return_value = _mock_bedrock_response(plan_json)

        plan = plan_mission(
            _make_objective(), _make_environment(), [],
        )
        assert plan.search_pattern == SearchPattern.PARALLEL_TRACKS
        assert plan.estimated_duration_seconds == 600
        assert len(plan.drone_assignments) == 1
        assert plan.safety_notes == ["Clear weather expected"]

    @patch("src.mission.planner.boto3")
    def test_json_in_code_block(self, mock_boto3: MagicMock) -> None:
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client

        plan_json = _make_plan_json()
        wrapped = f"```json\n{json.dumps(plan_json)}\n```"
        body_content = json.dumps({
            "content": [{"text": wrapped}],
        }).encode()
        mock_client.invoke_model.return_value = {"body": BytesIO(body_content)}

        plan = plan_mission(
            _make_objective(), _make_environment(), [],
        )
        assert plan.search_pattern == SearchPattern.PARALLEL_TRACKS

    @patch("src.mission.planner.boto3")
    def test_json_in_plain_code_block(self, mock_boto3: MagicMock) -> None:
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client

        plan_json = _make_plan_json()
        wrapped = f"```\n{json.dumps(plan_json)}\n```"
        body_content = json.dumps({
            "content": [{"text": wrapped}],
        }).encode()
        mock_client.invoke_model.return_value = {"body": BytesIO(body_content)}

        plan = plan_mission(
            _make_objective(), _make_environment(), [],
        )
        assert plan.search_pattern == SearchPattern.PARALLEL_TRACKS

    @patch("src.mission.planner.boto3")
    def test_bedrock_failure_raises_external_error(
        self, mock_boto3: MagicMock,
    ) -> None:
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.invoke_model.side_effect = Exception("Connection timeout")

        with pytest.raises(ExternalServiceError):
            plan_mission(_make_objective(), _make_environment(), [])

    @patch("src.mission.planner.boto3")
    def test_invalid_json_response_raises_processing_error(
        self, mock_boto3: MagicMock,
    ) -> None:
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client

        body_content = json.dumps({
            "content": [{"text": "not valid json at all"}],
        }).encode()
        mock_client.invoke_model.return_value = {"body": BytesIO(body_content)}

        with pytest.raises(ProcessingError):
            plan_mission(_make_objective(), _make_environment(), [])
